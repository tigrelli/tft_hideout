"""DATA-11 pytest: mock 임베딩 클라이언트로 chunk->embedding upsert 동작,
임베딩 차원(1024) 검증. HF Inference API는 mock으로 대체(policies.md 10.2/11).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db_session import models
from embeddings import (
    EMBEDDING_DIM,
    EmbeddingError,
    HuggingFaceEmbeddingClient,
    augment_chunk_text,
    champion_chunk_text,
    collect_chunks,
    is_real_champion,
    comp_chunk_text,
    item_build_chunk_text,
    playstyle_chunk_text,
    upsert_embeddings,
)

# ---- 순수 텍스트 생성 함수(가벼운 fake 객체로 속성만 흉내) -----------------------


@dataclass
class _FakeComp:
    name: str
    tier_rank: str
    avg_place: float
    win_rate: float | None
    play_rate: float
    playstyle_text: str


@dataclass
class _FakeAugment:
    name_kr: str
    tier: str
    description: str


@dataclass
class _FakeBuild:
    item_combination: list[str]
    win_rate: float
    play_rate: float
    avg_place: float


@dataclass
class _FakeChampion:
    name_kr: str
    cost: int


def test_comp_chunk_text_includes_core_fields_and_carry_marker() -> None:
    comp = _FakeComp(
        name="가짜 조합",
        tier_rank="OP",
        avg_place=3.1,
        win_rate=0.19,
        play_rate=0.02,
        playstyle_text="리롤 성향 강함",
    )
    text = comp_chunk_text(comp, [("아칼리", True), ("징크스", False)])

    assert "가짜 조합" in text
    assert "OP" in text
    assert "아칼리(캐리)" in text
    assert "징크스" in text and "징크스(캐리)" not in text
    assert "19.0%" in text
    assert "리롤 성향 강함" in text


def test_comp_chunk_text_handles_missing_win_rate() -> None:
    comp = _FakeComp(
        name="승률없음",
        tier_rank="A",
        avg_place=4.0,
        win_rate=None,
        play_rate=0.01,
        playstyle_text="설명",
    )
    text = comp_chunk_text(comp, [])

    assert "정보 없음" in text


def test_playstyle_chunk_text() -> None:
    comp = _FakeComp(
        name="가짜 조합",
        tier_rank="S",
        avg_place=3.5,
        win_rate=0.2,
        play_rate=0.03,
        playstyle_text="AP 캐리 조합",
    )
    assert playstyle_chunk_text(comp) == "가짜 조합 조합 플레이 스타일: AP 캐리 조합"


def test_augment_chunk_text_does_not_include_win_rate() -> None:
    augment = _FakeAugment(name_kr="가짜 증강체", tier="gold", description="가짜 설명")
    text = augment_chunk_text(augment)

    assert "가짜 증강체" in text
    assert "gold" in text
    assert "가짜 설명" in text
    assert "%" not in text  # augments 테이블엔 win_rate 자체가 없음(DATA-10 결정)


def test_item_build_chunk_text() -> None:
    build = _FakeBuild(
        item_combination=["TFT_Item_A", "TFT_Item_B"],
        win_rate=0.2,
        play_rate=0.25,
        avg_place=3.5,
    )
    text = item_build_chunk_text(build, "가짜챔프", ["검", "갑옷"])

    assert "가짜챔프" in text
    assert "검, 갑옷" in text
    assert "TFT_Item_A" not in text
    assert "20.0%" in text
    assert "25.0%" in text


def test_item_build_chunk_text_no_op_when_item_names_empty() -> None:
    build = _FakeBuild(item_combination=[], win_rate=0.2, play_rate=0.25, avg_place=3.5)
    text = item_build_chunk_text(build, "가짜챔프", [])
    assert "정보 없음" in text


def test_champion_chunk_text_includes_cost_and_traits() -> None:
    champion = _FakeChampion(name_kr="가짜챔프", cost=3)
    text = champion_chunk_text(champion, ["학살자", "N.O.V.A."])

    assert "가짜챔프" in text
    assert "3코스트" in text
    assert "학살자, N.O.V.A." in text


def test_champion_chunk_text_no_op_when_traits_empty() -> None:
    champion = _FakeChampion(name_kr="가짜챔프", cost=1)
    text = champion_chunk_text(champion, [])
    assert "정보 없음" in text


# ---- is_real_champion(): PVE/플레이스홀더 유닛 필터(2026-08-07 PM 피드백) -------


def test_is_real_champion_true_for_current_set_prefix() -> None:
    assert is_real_champion("TFT17_Akali", 17) is True


def test_is_real_champion_false_for_no_set_prefix() -> None:
    # 골렘: "TFT_BlueGolem"(세트 번호 없음, 실측 2026-08-07)
    assert is_real_champion("TFT_BlueGolem", 17) is False


def test_is_real_champion_false_for_other_set_prefix() -> None:
    # 협곡 바위 게: "TFT9_SLIME_Crab"(다른 세트 번호가 그대로 남아있음)
    assert is_real_champion("TFT9_SLIME_Crab", 17) is False


def test_is_real_champion_false_for_fake_unit_suffix() -> None:
    # 소형 블랙홀: "TFT17_DarkStar_FakeUnit"(현재 세트 접두어지만 FakeUnit 표시)
    assert is_real_champion("TFT17_DarkStar_FakeUnit", 17) is False


def test_is_real_champion_false_for_enemy_boss_unit() -> None:
    # 태고족 우두머리: "TFT17_Enemy_Aatrox"(현재 세트 접두어지만 아트록스 스킬을
    # 재사용하는 별도 보스 유닛 — 5코스트로 구매 가능한 챔피언이 아님, PM 피드백)
    assert is_real_champion("TFT17_Enemy_Aatrox", 17) is False


# ---- HuggingFaceEmbeddingClient(mock transport) ---------------------------------


def _one_hot_vector(index: int) -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    vec[index] = 1.0
    return vec


def test_embed_batch_returns_vectors_in_input_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Bearer fake-key"
        return httpx.Response(200, json=[_one_hot_vector(0), _one_hot_vector(1)])

    client = HuggingFaceEmbeddingClient(
        api_key="fake-key", transport=httpx.MockTransport(handler)
    )
    vectors = client.embed_batch(["첫문장", "둘째문장"])

    assert len(vectors) == 2
    assert len(vectors[0]) == EMBEDDING_DIM
    assert vectors[0] == _one_hot_vector(0)


def test_embed_batch_empty_input_returns_empty_list() -> None:
    client = HuggingFaceEmbeddingClient(api_key="fake-key")
    assert client.embed_batch([]) == []


def test_embed_batch_retries_on_503_cold_start_then_succeeds() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(503, json={"error": "loading", "estimated_time": 20})
        return httpx.Response(200, json=[_one_hot_vector(0)])

    client = HuggingFaceEmbeddingClient(
        api_key="fake-key",
        transport=httpx.MockTransport(handler),
        retry_backoff_seconds=0,
    )
    vectors = client.embed_batch(["텍스트"])

    assert attempts["n"] == 2
    assert vectors == [_one_hot_vector(0)]


def test_embed_batch_raises_after_exhausting_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "loading"})

    client = HuggingFaceEmbeddingClient(
        api_key="fake-key",
        transport=httpx.MockTransport(handler),
        max_retries=1,
        retry_backoff_seconds=0,
    )
    with pytest.raises(EmbeddingError):
        client.embed_batch(["텍스트"])


def test_embed_one_returns_single_vector() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_one_hot_vector(3)])

    client = HuggingFaceEmbeddingClient(
        api_key="fake-key", transport=httpx.MockTransport(handler)
    )
    assert client.embed_one("텍스트") == _one_hot_vector(3)


# ---- collect_chunks / upsert_embeddings(실제 마이그레이션 DB) -------------------


@pytest.fixture
def seeded_session(migrated_engine: Engine) -> Session:
    with Session(migrated_engine) as session:
        session.add(
            models.Patch(
                version="17.8",
                set_number=17,
                released_at=datetime(2026, 1, 1, tzinfo=UTC),
                is_current=False,
                detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.flush()

        champion = models.Champion(
            patch_version="17.8",
            riot_champion_id="TFT17_X",
            name_kr="엑스",
            name_en="X",
            cost=1,
        )
        session.add(champion)
        session.flush()

        comp = models.Comp(
            patch_version="17.8",
            riot_comp_id="comp-1",
            name="가짜조합",
            tier_rank="S",
            avg_place=3.0,
            play_rate=0.1,
            win_rate=0.2,
            playstyle_text="설명",
            updated_at=datetime.now(UTC),
        )
        session.add(comp)
        session.flush()

        session.add(
            models.CompChampion(
                comp_id=comp.id,
                champion_id=champion.id,
                is_carry=True,
                recommended_items=[],
            )
        )
        session.add(
            models.Augment(
                patch_version="17.8",
                riot_augment_id="aug-1",
                name_kr="가짜증강",
                name_en="FakeAug",
                tier="gold",
                description="설명",
                is_legend_related=False,
            )
        )
        session.add(
            models.ChampionItemBuild(
                champion_id=champion.id,
                patch_version="17.8",
                item_combination=["A"],
                play_rate=0.1,
                avg_place=3.0,
                win_rate=0.2,
            )
        )
        session.commit()
        yield session


def test_collect_chunks_builds_all_doc_types(seeded_session: Session) -> None:
    chunks = collect_chunks(seeded_session, "17.8")
    doc_types = {c["doc_type"] for c in chunks}

    assert doc_types == {"comp", "playstyle", "augment", "item_build", "champion"}
    comp_chunk = next(c for c in chunks if c["doc_type"] == "comp")
    assert "엑스(캐리)" in comp_chunk["content_text"]


def test_collect_chunks_champion_includes_cost_and_traits(
    seeded_session: Session,
) -> None:
    chunks = collect_chunks(seeded_session, "17.8")
    champion_chunk = next(c for c in chunks if c["doc_type"] == "champion")

    assert "엑스" in champion_chunk["content_text"]
    assert "1코스트" in champion_chunk["content_text"]
    assert champion_chunk["metadata"] == {"name": "엑스", "cost": 1}


def test_collect_chunks_excludes_champions_outside_1_to_5_cost(
    seeded_session: Session,
) -> None:
    seeded_session.add(
        models.Champion(
            patch_version="17.8",
            riot_champion_id="TFT17_Anvil",
            name_kr="아이템 모루",
            name_en="ItemAnvil",
            cost=8,
        )
    )
    seeded_session.commit()

    chunks = collect_chunks(seeded_session, "17.8")
    champion_names = {
        c["metadata"]["name"] for c in chunks if c["doc_type"] == "champion"
    }

    assert "아이템 모루" not in champion_names


def test_collect_chunks_excludes_pve_units_with_1_to_5_cost(
    seeded_session: Session,
) -> None:
    """PVE 유닛(골렘 등)은 코스트가 1~5 범위 안에 들어와 위 코스트 필터만으로는
    안 걸러진다 — apiName 패턴(is_real_champion)까지 함께 확인해야 한다."""
    seeded_session.add(
        models.Champion(
            patch_version="17.8",
            riot_champion_id="TFT_BlueGolem",
            name_kr="골렘",
            name_en="Golem",
            cost=1,
        )
    )
    seeded_session.commit()

    chunks = collect_chunks(seeded_session, "17.8")
    champion_names = {
        c["metadata"]["name"] for c in chunks if c["doc_type"] == "champion"
    }

    assert "골렘" not in champion_names


def test_collect_chunks_caps_item_build_at_top_n_by_play_rate_per_champion(
    seeded_session: Session,
) -> None:
    """2026-08-07 운영에서 확인된 문제: champion_item_builds가 챔피언당 수백~천
    단위라 전부 임베딩하면 안 됨(HuggingFace 무료 티어 소진 + 실제로는 0건만
    임베딩돼 챗봇이 "아이템 빌드는 확인 안 됨"으로만 답하던 원인). champion_id별
    play_rate 상위 TOP_BUILDS_PER_CHAMPION개만 남는지 검증한다."""
    from embeddings import TOP_BUILDS_PER_CHAMPION

    champion = seeded_session.scalars(
        select(models.Champion).where(models.Champion.riot_champion_id == "TFT17_X")
    ).one()
    for i in range(TOP_BUILDS_PER_CHAMPION + 5):
        seeded_session.add(
            models.ChampionItemBuild(
                champion_id=champion.id,
                patch_version="17.8",
                item_combination=[f"Item{i}"],
                play_rate=0.5 - i * 0.01,  # 내림차순 — 낮은 i일수록 상위권
                avg_place=3.0,
                win_rate=0.2,
            )
        )
    seeded_session.commit()

    chunks = collect_chunks(seeded_session, "17.8")
    item_build_chunks = [c for c in chunks if c["doc_type"] == "item_build"]

    # 기존 seeded_session fixture의 1건 + 이번에 추가한 TOP_BUILDS_PER_CHAMPION+5건
    # 중 play_rate 상위 TOP_BUILDS_PER_CHAMPION개만 남아야 함(기존 1건은
    # play_rate=0.1로 가장 낮아 컷오프됨).
    assert len(item_build_chunks) == TOP_BUILDS_PER_CHAMPION
    assert all("Item" in c["content_text"] for c in item_build_chunks)


def test_upsert_embeddings_validates_dimension(seeded_session: Session) -> None:
    chunks = [
        {
            "doc_type": "augment",
            "source_table": "augments",
            "source_id": 1,
            "content_text": "x",
            "metadata": {},
        }
    ]
    with pytest.raises(ValueError, match="차원"):
        upsert_embeddings(seeded_session, "17.8", chunks, [[0.1, 0.2]])


def test_upsert_embeddings_same_patch_updates_not_duplicates(
    seeded_session: Session,
) -> None:
    chunks = collect_chunks(seeded_session, "17.8")
    vectors = [_one_hot_vector(i % EMBEDDING_DIM) for i in range(len(chunks))]

    upsert_embeddings(seeded_session, "17.8", chunks, vectors)
    seeded_session.commit()
    upsert_embeddings(seeded_session, "17.8", chunks, vectors)
    seeded_session.commit()

    rows = seeded_session.scalars(
        select(models.MetaDocumentEmbedding).where(
            models.MetaDocumentEmbedding.patch_version == "17.8"
        )
    ).all()
    assert len(rows) == len(chunks)
    assert all(len(r.embedding) == EMBEDDING_DIM for r in rows)
