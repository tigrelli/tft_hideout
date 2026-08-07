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
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

import db_session as batch_db

models = batch_db.models

DEFAULT_HF_BASE_URL = "https://router.huggingface.co/hf-inference/models"
DEFAULT_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024


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


def item_build_chunk_text(build: Any, champion_name: str) -> str:
    items = ", ".join(build.item_combination) if build.item_combination else "정보 없음"
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
    builds = session.scalars(
        select(models.ChampionItemBuild).where(
            models.ChampionItemBuild.patch_version == patch_version
        )
    ).all()
    for build in builds:
        champion = champion_by_id.get(build.champion_id)
        champion_name = champion.name_kr if champion else "알 수 없는 챔피언"
        chunks.append(
            {
                "doc_type": "item_build",
                "source_table": "champion_item_builds",
                "source_id": build.id,
                "content_text": item_build_chunk_text(build, champion_name),
                "metadata": {"champion": champion_name},
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
