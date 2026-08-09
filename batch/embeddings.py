"""DATA-11: 정규화 레코드(DATA-10) -> 자연어 chunk 변환 -> BGE-M3 임베딩 -> upsert.

HF Inference API 엔드포인트: 레거시 `api-inference.huggingface.co`는 DNS 자체가
뜨지 않음(2026-08-04 실호출로 확인, HF가 라우터 방식으로 이전한 것으로 보임).
신규 엔드포인트 사용:
`https://router.huggingface.co/hf-inference/models/{model}/pipeline/feature-extraction`
— `inputs`에 문자열 리스트를 보내면 항상 `list[list[float]]`(배치, 원소 1개여도
바깥이 리스트)로 응답한다(실호출로 확인).
"""

from __future__ import annotations

import time
from typing import Any, Self

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

import db_session as batch_db
from normalize import format_item_stats

models = batch_db.models

DEFAULT_HF_BASE_URL = "https://router.huggingface.co/hf-inference/models"
DEFAULT_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024

# backend/routers/catalog.py의 TOP_BUILDS_PER_CHAMPION과 반드시 같은 값으로
# 유지한다(챗봇이 인용하는 빌드 범위가 /items/builds 화면에 보이는 범위와
# 같아야 함). 2026-08-07 실측: champion_item_builds가 패치당 54,289행(챔피언당
# 수백~천 단위 조합)이라 전부 임베딩하면 HuggingFace 무료 티어를 순식간에
# 소진하고 RAG 품질도 떨어짐 — play_rate 상위 N개만 임베딩 대상으로 좁힌다.
TOP_BUILDS_PER_CHAMPION = 10


class EmbeddingError(Exception):
    """HF Inference API 호출 실패(HTTP 오류, 콜드스타트 재시도 소진 등)."""


class HuggingFaceEmbeddingClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_HF_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 2.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = f"{base_url}/{model}/pipeline/feature-extraction"
        self._api_key = api_key
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._http = httpx.Client(timeout=timeout, transport=transport)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """texts 순서 그대로 임베딩 벡터 리스트를 반환한다. 빈 입력은 빈 리스트."""
        if not texts:
            return []

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._http.post(
                    self._url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"inputs": texts, "options": {"wait_for_model": True}},
                )
                if response.status_code == 503:
                    # 무료 인프라 콜드스타트(모델 로딩 중) 대응(policies.md 9번)
                    last_error = EmbeddingError(f"모델 로딩 중(503): {response.text}")
                    if attempt < self._max_retries:
                        time.sleep(self._retry_backoff_seconds)
                        continue
                    raise last_error
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(self._retry_backoff_seconds)
        raise EmbeddingError(
            f"HF Inference API 요청 실패: {last_error}"
        ) from last_error

    def embed_one(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]


# ---- 순수 chunk 텍스트 생성 함수(DB 미접근) -------------------------------------


def comp_chunk_text(comp: Any, member_names: list[tuple[str, bool]]) -> str:
    """member_names: [(챔피언 이름, is_carry), ...]."""
    members = ", ".join(
        f"{name}(캐리)" if is_carry else name for name, is_carry in member_names
    )
    win_rate_text = f"{comp.win_rate:.1%}" if comp.win_rate is not None else "정보 없음"
    return (
        f"{comp.name} 조합(티어 {comp.tier_rank}): 평균 등수 {comp.avg_place:.2f}, "
        f"승률 {win_rate_text}, 픽률 {comp.play_rate:.1%}. "
        f"구성: {members}. {comp.playstyle_text}"
    )


def playstyle_chunk_text(comp: Any) -> str:
    return f"{comp.name} 조합 플레이 스타일: {comp.playstyle_text}"


def augment_chunk_text(augment: Any) -> str:
    return f"{augment.name_kr}({augment.tier} 등급) 증강체: {augment.description}"


_NON_CHAMPION_ID_MARKERS = ("fakeunit", "enemy")


def is_real_champion(riot_champion_id: str, set_number: int) -> bool:
    """Community Dragon의 세트 챔피언 목록엔 PVE/보스/플레이스홀더 유닛도
    함께 들어있다(2026-08-07 실측 — 골렘/협곡 바위 게/훈련 봇은 현재 세트
    접두어 "TFT{set}_"가 아니라 접두어 없음("TFT_BlueGolem")이거나 다른(옛)
    세트 번호("TFT9_SLIME_Crab")를 쓰고, 소형 블랙홀은 "FakeUnit"이, 태고족
    우두머리는 세트 접두어는 맞지만 "TFT17_Enemy_Aatrox"처럼 "Enemy"가
    명시적으로 붙어있음 — 아트록스 스킬을 재사용하는 별도 보스 유닛이라
    5코스트로 구매 가능한 챔피언이 아님, PM 피드백). 챗봇이 "3코스트
    챔피언은?" 같은 질문에 이런 유닛을 실제 챔피언으로 인용하지 않도록
    챔피언 문서 생성 시 걸러낸다."""
    lowered = riot_champion_id.lower()
    if any(marker in lowered for marker in _NON_CHAMPION_ID_MARKERS):
        return False
    return riot_champion_id.startswith(f"TFT{set_number}_")


def champion_chunk_text(champion: Any, trait_names: list[str]) -> str:
    """2026-08-07 PM 피드백: "3코스트 챔피언은?" 같은 챔피언 자체(코스트·특성)를
    묻는 질문에 검색 문서가 아예 없어 항상 "정보 없음"으로만 답하던 문제 —
    champions 테이블엔 이미 있는 정보를 새 doc_type("champion")으로 임베딩한다."""
    traits = ", ".join(trait_names) if trait_names else "정보 없음"
    return f"{champion.name_kr}({champion.cost}코스트) 챔피언. 특성: {traits}."


def item_chunk_text(item: Any) -> str:
    """CHAT-14: DATA-19가 채운 items.description을 새 doc_type("item")으로
    임베딩해, 아이템 효과 자체를 묻는 질문("보석 건틀릿 효과가 뭐야?")에
    답할 근거 문서를 마련한다(champion doc_type과 동일 패턴, 2026-08-07 신설분
    참고). DATA-20: description은 정성적 설명뿐이라 "치명타 확률이 얼마나
    증가하나요?" 같은 수치 질문에 항상 "정보 없음"으로만 답하던 문제(CHAT-14
    PM 검증 중 발견) — items.stats의 화이트리스트 핵심 스탯을 덧붙여 근거
    문서에 실제 수치가 포함되게 한다. 화이트리스트에 해당하는 값이 하나도
    없으면(스탯 자체가 없거나 전부 어빌리티 변수인 아이템) 기존 문장 그대로
    유지한다."""
    stats_text = format_item_stats(item.stats)
    if not stats_text:
        return f"{item.name_kr}: {item.description}"
    return f"{item.name_kr}: {item.description} (스탯: {stats_text})"


def is_charge_variant_item(name_kr: str) -> bool:
    """PM 실사용 검증 중 발견(2026-08-09): op.gg/Community Dragon 원본이 '재조합기'
    ·'자석 제거기'·'그웬의 가위' 같은 소모품을 "N회 사용 가능" 잔여 횟수별로
    별도 아이템 행 9~10개씩(예: `name_kr`가 "재조합기 <rules>(8회 사용 가능!)</rules>")
    만들어둔다 — 실제로는 같은 아이템의 잔여 사용 횟수 상태일 뿐 서로 다른
    아이템이 아닌데, 이걸 그대로 "item" doc_type으로 임베딩하면 같은 패치 안에
    공존하는 여러 변형(8회/7회 등)을 LLM이 서로 다른 시점의 데이터로 착각해
    "17.8 패치에서 사용 횟수가 8회에서 7회로 바뀌었다" 같은 완전한 허구를
    만들어내는 실제 사례가 확인됨(패치 변경이력 자체를 이 서비스가 갖고 있지
    않은데도, 공존하는 변형들을 비교해 그럴듯한 오답을 만든 것). 태그 없는
    기본 행(예: "재조합기")이 이미 같은 설명을 담고 있어 정보 손실 없이
    제외 가능하다."""
    return "<rules>" in name_kr


def item_build_chunk_text(build: Any, champion_name: str, item_names: list[str]) -> str:
    """item_names: build.item_combination(op.gg 원본 apiName 리스트, 예:
    "TFT_Item_Deathblade")를 표시 이름으로 변환한 리스트(호출부가 items 테이블
    조회 후 전달 — catalog.py GET /catalog/items/builds와 동일한 변환 규칙,
    2026-08-07 수정: 원래 apiName을 그대로 임베딩해 챗봇이 "TFT_Item_..."
    같은 내부 ID를 그대로 답변에 인용하던 문제)."""
    items = ", ".join(item_names) if item_names else "정보 없음"
    return (
        f"{champion_name} 아이템 빌드: {items}. "
        f"승률 {build.win_rate:.1%}, 픽률 {build.play_rate:.1%}, "
        f"평균 등수 {build.avg_place:.2f}"
    )


# ---- DB 조회 -> chunk dict 목록 -------------------------------------------------


def collect_comp_and_playstyle_chunks(
    session: Session, patch_version: str
) -> list[dict[str, Any]]:
    """comps/comp_champions만 조회해 comp+playstyle 청크를 만든다(전체 배치의
    collect_chunks()에서 분리 — DATA-18 comps_refresh.py가 patch_version이
    안 바뀐 날에도 comps만 가볍게 재임베딩할 수 있도록 독립 호출 가능해야
    한다. augments/item_builds는 그 날 안 건드리므로 포함하지 않는다)."""
    chunks: list[dict[str, Any]] = []

    comps = session.scalars(
        select(models.Comp).where(models.Comp.patch_version == patch_version)
    ).all()
    champion_by_id = {
        c.id: c
        for c in session.scalars(
            select(models.Champion).where(
                models.Champion.patch_version == patch_version
            )
        )
    }
    for comp in comps:
        links = session.scalars(
            select(models.CompChampion).where(models.CompChampion.comp_id == comp.id)
        ).all()
        member_names = [
            (champion_by_id[link.champion_id].name_kr, link.is_carry)
            for link in links
            if link.champion_id in champion_by_id
        ]
        chunks.append(
            {
                "doc_type": "comp",
                "source_table": "comps",
                "source_id": comp.id,
                "content_text": comp_chunk_text(comp, member_names),
                "metadata": {"name": comp.name, "tier_rank": comp.tier_rank},
            }
        )
        chunks.append(
            {
                "doc_type": "playstyle",
                "source_table": "comps",
                "source_id": comp.id,
                "content_text": playstyle_chunk_text(comp),
                "metadata": {"name": comp.name},
            }
        )

    return chunks


def collect_chunks(session: Session, patch_version: str) -> list[dict[str, Any]]:
    """해당 패치의 comps/augments/champion_item_builds를 조회해 embed 대상
    chunk(doc_type/source_table/source_id/content_text/metadata) 목록을 만든다.
    임베딩 벡터는 아직 없음(embed_batch로 별도 계산 후 upsert_embeddings에 전달)."""
    chunks: list[dict[str, Any]] = collect_comp_and_playstyle_chunks(
        session, patch_version
    )

    augments = session.scalars(
        select(models.Augment).where(models.Augment.patch_version == patch_version)
    ).all()
    for augment in augments:
        chunks.append(
            {
                "doc_type": "augment",
                "source_table": "augments",
                "source_id": augment.id,
                "content_text": augment_chunk_text(augment),
                "metadata": {"name": augment.name_kr, "tier": augment.tier},
            }
        )

    champion_by_id = {
        c.id: c
        for c in session.scalars(
            select(models.Champion).where(
                models.Champion.patch_version == patch_version
            )
        )
    }
    # champion: "3코스트 챔피언은?" 같은 챔피언 자체(코스트·특성)를 묻는
    # 질문에 검색 문서가 아예 없어 항상 "정보 없음"으로만 답하던 문제
    # (2026-08-07 PM 피드백) — champions 테이블은 이미 있는데 doc_type이
    # 없어서 못 쓰고 있었다. champions 테이블에 실제 소환 불가능한 PVE/특수
    # 유닛(관측: 코스트 8·11, is_real_champion() 참고)이 섞여 있어 걸러낸다.
    set_number = session.scalar(
        select(models.Patch.set_number).where(models.Patch.version == patch_version)
    )
    trait_by_champion_id: dict[int, list[str]] = {}
    if champion_by_id:
        for champion_id, trait_name in session.execute(
            select(models.ChampionTrait.champion_id, models.Trait.name_kr)
            .join(models.Trait, models.Trait.id == models.ChampionTrait.trait_id)
            .where(models.ChampionTrait.champion_id.in_(champion_by_id.keys()))
        ):
            trait_by_champion_id.setdefault(champion_id, []).append(trait_name)
    for champion in champion_by_id.values():
        if not (1 <= champion.cost <= 5):
            continue
        if not is_real_champion(champion.riot_champion_id, set_number):
            continue
        chunks.append(
            {
                "doc_type": "champion",
                "source_table": "champions",
                "source_id": champion.id,
                "content_text": champion_chunk_text(
                    champion, trait_by_champion_id.get(champion.id, [])
                ),
                "metadata": {"name": champion.name_kr, "cost": champion.cost},
            }
        )

    # CHAT-14: DATA-19가 채운 description이 있는 아이템만 "item" doc_type으로
    # 임베딩한다(설명이 없으면 근거 없는 빈 문서만 늘리는 셈이라 제외). 2026-08-09:
    # "N회 사용 가능" 잔여 횟수 변형(is_charge_variant_item)도 같은 이유로 제외
    # (위 함수 docstring 참고 — 허구의 "패치 변경" 답변을 유발한 실제 원인).
    for item in session.scalars(
        select(models.Item).where(
            models.Item.patch_version == patch_version,
            models.Item.description.isnot(None),
            models.Item.description != "",
        )
    ):
        if is_charge_variant_item(item.name_kr):
            continue
        chunks.append(
            {
                "doc_type": "item",
                "source_table": "items",
                "source_id": item.id,
                "content_text": item_chunk_text(item),
                "metadata": {"name": item.name_kr},
            }
        )

    # champion_item_builds는 챔피언당 수백~천 단위 조합이 쌓여있어(op.gg 원본
    # 응답 그대로 저장) 전부 임베딩하면 안 됨 — catalog.py GET /catalog/items/builds와
    # 동일하게 champion_id별 play_rate 상위 TOP_BUILDS_PER_CHAMPION개만 SQL
    # 레벨에서 걸러 가져온다.
    build_rank = func.row_number().over(
        partition_by=models.ChampionItemBuild.champion_id,
        order_by=models.ChampionItemBuild.play_rate.desc(),
    )
    ranked_builds = (
        select(
            models.ChampionItemBuild.id,
            models.ChampionItemBuild.champion_id,
            models.ChampionItemBuild.item_combination,
            models.ChampionItemBuild.play_rate,
            models.ChampionItemBuild.avg_place,
            models.ChampionItemBuild.win_rate,
            build_rank.label("build_rank"),
        )
        .where(models.ChampionItemBuild.patch_version == patch_version)
        .subquery()
    )
    builds = session.execute(
        select(ranked_builds).where(
            ranked_builds.c.build_rank <= TOP_BUILDS_PER_CHAMPION
        )
    ).all()
    # item_combination은 op.gg 원본 apiName 리스트라(catalog.py GET
    # /catalog/items/builds와 동일한 이유) items 테이블에서 표시 이름을
    # 조회해야 챗봇이 "TFT_Item_Deathblade" 같은 내부 ID를 그대로 답변에
    # 인용하지 않는다.
    item_ids = {item_id for build in builds for item_id in build.item_combination}
    item_name_by_id = (
        {
            item.riot_item_id: item.name_kr
            for item in session.scalars(
                select(models.Item).where(
                    models.Item.patch_version == patch_version,
                    models.Item.riot_item_id.in_(item_ids),
                )
            )
        }
        if item_ids
        else {}
    )
    for build in builds:
        champion = champion_by_id.get(build.champion_id)
        champion_name = champion.name_kr if champion else "알 수 없는 챔피언"
        item_names = [
            item_name_by_id.get(item_id, item_id) for item_id in build.item_combination
        ]
        chunks.append(
            {
                "doc_type": "item_build",
                "source_table": "champion_item_builds",
                "source_id": build.id,
                "content_text": item_build_chunk_text(build, champion_name, item_names),
                # CHAT-13: 챔피언 이름만 있으면 verify_grounding()이 이 빌드에 등장하는
                # 아이템 이름을 "알려진 이름"으로 인식하지 못해 정상 인용도 근거검증
                # 경고를 유발했다(PM 제보 2026-08-08) — 아이템 이름 목록도 함께 싣는다
                # (링크 대상은 아님, chat_links.py 참고). champion_id는 CHAT-13 후속
                # 수정으로 추가 — 이게 없으면 챗봇이 만드는 챔피언 링크가 필터 없는
                # `/items/builds`로만 가서 클릭해도 챔피언이 선택되지 않았다(PM 제보).
                "metadata": {
                    "champion": champion_name,
                    "champion_id": build.champion_id,
                    "items": item_names,
                },
            }
        )

    return chunks


# ---- upsert ---------------------------------------------------------------------


def upsert_embeddings(
    session: Session,
    patch_version: str,
    chunks: list[dict[str, Any]],
    embeddings: list[list[float]],
) -> None:
    """chunks[i]에 embeddings[i]를 붙여 upsert한다(같은 (patch_version, doc_type,
    source_table, source_id)는 갱신, 다르면 새 행 — DATA-10과 동일 원칙)."""
    if not chunks:
        return
    if len(chunks) != len(embeddings):
        raise ValueError("chunks와 embeddings 길이가 다릅니다")
    for vector in embeddings:
        if len(vector) != EMBEDDING_DIM:
            raise ValueError(
                f"임베딩 차원 불일치: {len(vector)} (기대값 {EMBEDDING_DIM}, BGE-M3)"
            )

    values = [
        {
            "patch_version": patch_version,
            "doc_type": chunk["doc_type"],
            "source_table": chunk["source_table"],
            "source_id": chunk["source_id"],
            "content_text": chunk["content_text"],
            "embedding": vector,
            "metadata": chunk["metadata"],
        }
        for chunk, vector in zip(chunks, embeddings, strict=True)
    ]
    # ORM 클래스(models.MetaDocumentEmbedding)로 바로 insert()하면 SQLAlchemy가
    # dict 키 "metadata"를 컬럼이 아니라 상속받은 DeclarativeBase.metadata(레지스트리)로
    # 오인해 깨진다(모델의 Python 속성명은 doc_metadata인 이유). Core 레벨 __table__로
    # insert하면 실제 컬럼명("metadata")을 그대로 키로 써도 안전하다.
    stmt = pg_insert(models.MetaDocumentEmbedding.__table__).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["patch_version", "doc_type", "source_table", "source_id"],
        set_={
            "content_text": stmt.excluded.content_text,
            "embedding": stmt.excluded.embedding,
            "metadata": stmt.excluded.metadata,
        },
    )
    session.execute(stmt)
