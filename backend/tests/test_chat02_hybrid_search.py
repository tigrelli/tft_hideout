"""CHAT-02 pytest(WBS 테스트 요구사항: 의도별 SQL 필터 조건 반영 여부,
mock pgvector top-k 결과 병합 확인). HF Inference API는 mock으로 대체
(policies.md 10.2/11, DATA-11과 동일 정책)."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.models import EMBEDDING_DIM, Champion, MetaDocumentEmbedding, Patch
from services.embedding_client import EmbeddingError, HuggingFaceEmbeddingClient
from services.hybrid_search import hybrid_search, lookup_item_builds_by_champion_ids
from services.intent_classification import (
    INTENT_AUGMENT_RECOMMENDATION,
    INTENT_COMP_RECOMMENDATION,
    INTENT_GENERAL_STRATEGY,
    INTENT_ITEM_RECOMMENDATION,
)


def _one_hot(dim: int, index: int, value: float = 1.0) -> list[float]:
    vec = [0.0] * dim
    vec[index] = value
    return vec


# ---- HuggingFaceEmbeddingClient(embed_query 용) ----------------------------------


def test_embed_batch_returns_vectors_from_mock_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Bearer fake-key"
        return httpx.Response(200, json=[_one_hot(EMBEDDING_DIM, 0)])

    client = HuggingFaceEmbeddingClient(
        api_key="fake-key", transport=httpx.MockTransport(handler)
    )
    vectors = client.embed_batch(["증강체 추천해줘"])

    assert len(vectors) == 1
    assert len(vectors[0]) == EMBEDDING_DIM


def test_embed_one_returns_single_vector() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_one_hot(EMBEDDING_DIM, 3)])

    client = HuggingFaceEmbeddingClient(
        api_key="fake-key", transport=httpx.MockTransport(handler)
    )
    assert client.embed_one("텍스트") == _one_hot(EMBEDDING_DIM, 3)


def test_embed_batch_retries_on_503_cold_start_then_succeeds() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(503, json={"error": "loading"})
        return httpx.Response(200, json=[_one_hot(EMBEDDING_DIM, 0)])

    client = HuggingFaceEmbeddingClient(
        api_key="fake-key",
        transport=httpx.MockTransport(handler),
        retry_backoff_seconds=0,
    )
    vectors = client.embed_batch(["텍스트"])

    assert attempts["n"] == 2
    assert vectors == [_one_hot(EMBEDDING_DIM, 0)]


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


# ---- hybrid_search: 의도별 SQL 필터 + pgvector top-k -----------------------------


@pytest.fixture
def seeded_docs(migrated_engine: Engine) -> Engine:
    with Session(migrated_engine) as session:
        session.execute(
            insert(Patch).values(
                version="17.8",
                set_number=17,
                released_at=datetime(2026, 1, 1, tzinfo=UTC),
                is_current=True,
                detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.execute(
            insert(Patch).values(
                version="17.7",
                set_number=17,
                released_at=datetime(2025, 12, 1, tzinfo=UTC),
                is_current=False,
                detected_at=datetime(2025, 12, 1, tzinfo=UTC),
            )
        )
        session.commit()

        # doc_type별 1개씩 + item_build은 거리가 다른 2개(top-k 정렬 검증용)
        # source_id는 doc_type 내에서만 의미 있는 값이라 겹쳐도 무방(실제 스키마의
        # UNIQUE 제약은 (patch_version, doc_type, source_table, source_id))
        docs = [
            ("17.8", "comp", 1, _one_hot(EMBEDDING_DIM, 0, 1.0)),
            ("17.8", "playstyle", 1, _one_hot(EMBEDDING_DIM, 0, 0.9)),
            ("17.8", "augment", 1, _one_hot(EMBEDDING_DIM, 0, 1.0)),
            ("17.8", "item_build", 1, _one_hot(EMBEDDING_DIM, 0, 1.0)),  # 가장 가까움
            ("17.8", "item_build", 2, _one_hot(EMBEDDING_DIM, 1, 1.0)),  # 직교(더 멂)
            # 이전 패치 문서 — patch_version 필터로 제외돼야 함
            ("17.7", "item_build", 3, _one_hot(EMBEDDING_DIM, 0, 1.0)),
        ]
        for patch_version, doc_type, source_id, vector in docs:
            session.execute(
                insert(MetaDocumentEmbedding).values(
                    patch_version=patch_version,
                    doc_type=doc_type,
                    source_table=f"{doc_type}s",
                    source_id=source_id,
                    content_text=f"{doc_type} mock 문서 {source_id}",
                    embedding=vector,
                    doc_metadata={},
                )
            )
        session.commit()
    return migrated_engine


def test_comp_recommendation_only_searches_comp_and_playstyle(
    seeded_docs: Engine,
) -> None:
    with Session(seeded_docs) as session:
        results = hybrid_search(
            session,
            INTENT_COMP_RECOMMENDATION,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )
    assert {r.doc_type for r in results} == {"comp", "playstyle"}


def test_item_recommendation_only_searches_item_build(seeded_docs: Engine) -> None:
    with Session(seeded_docs) as session:
        results = hybrid_search(
            session,
            INTENT_ITEM_RECOMMENDATION,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )
    assert {r.doc_type for r in results} == {"item_build"}
    # patch_version 필터: 17.7의 item_build(source_id=3)는 제외돼야 함
    assert all(r.patch_version == "17.8" for r in results)


def test_item_recommendation_caps_builds_per_champion_for_breadth(
    seeded_docs: Engine,
) -> None:
    """2026-08-07 PM 피드백: 여러 챔피언의 아이템 빌드를 한꺼번에 물어보는
    후속질문("이 챔피언들을 조합에 넣을 때...")에서, 순수 거리순 top-k만
    쓰면 가장 가까운 챔피언 1명의 빌드만 여러 개 뽑히고 나머지 챔피언은
    아예 안 뽑히는 문제가 실제로 확인됨(5코스트 9명 중 1명만 답변에 등장).
    챔피언별로 캡을 걸어 여러 챔피언이 함께 뽑히는지 검증한다."""
    with Session(seeded_docs) as session:
        # 챔피언A: 쿼리와 완전히 같은 방향(최단거리)인 빌드 5개 — 캡 없으면
        # top-k를 전부 독식함.
        for i in range(5):
            session.execute(
                insert(MetaDocumentEmbedding).values(
                    patch_version="17.8",
                    doc_type="item_build",
                    source_table="champion_item_builds",
                    source_id=100 + i,
                    content_text=f"챔피언A 빌드 {i}",
                    embedding=_one_hot(EMBEDDING_DIM, 0, 1.0),
                    doc_metadata={"champion": "챔피언A"},
                )
            )
        # 챔피언 B/C/D: 약간 먼(직교) 빌드 1개씩 — 캡이 없으면 안 뽑힘.
        for i, name in enumerate(["챔피언B", "챔피언C", "챔피언D"]):
            session.execute(
                insert(MetaDocumentEmbedding).values(
                    patch_version="17.8",
                    doc_type="item_build",
                    source_table="champion_item_builds",
                    source_id=200 + i,
                    content_text=f"{name} 빌드",
                    embedding=_one_hot(EMBEDDING_DIM, i + 1, 1.0),
                    doc_metadata={"champion": name},
                )
            )
        session.commit()

        results = hybrid_search(
            session,
            INTENT_ITEM_RECOMMENDATION,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )

    champion_a_count = sum(
        1 for r in results if r.doc_metadata.get("champion") == "챔피언A"
    )
    champions_in_results = {
        r.doc_metadata["champion"] for r in results if "champion" in r.doc_metadata
    }

    assert champion_a_count == 2
    assert {"챔피언B", "챔피언C", "챔피언D"}.issubset(champions_in_results)


def test_augment_recommendation_only_searches_augment(seeded_docs: Engine) -> None:
    with Session(seeded_docs) as session:
        results = hybrid_search(
            session,
            INTENT_AUGMENT_RECOMMENDATION,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )
    assert {r.doc_type for r in results} == {"augment"}


def test_general_strategy_searches_all_doc_types(seeded_docs: Engine) -> None:
    with Session(seeded_docs) as session:
        results = hybrid_search(
            session,
            INTENT_GENERAL_STRATEGY,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )
    assert {r.doc_type for r in results} == {
        "comp",
        "playstyle",
        "augment",
        "item_build",
    }


def test_general_strategy_includes_champion_doc_type(seeded_docs: Engine) -> None:
    """2026-08-07 PM 피드백: "3코스트 챔피언은?" 질의가 champion 문서를
    찾을 수 있어야 한다(신규 doc_type)."""
    with Session(seeded_docs) as session:
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="champion",
                source_table="champions",
                source_id=1,
                content_text="가짜챔프(3코스트) 챔피언. 특성: 학살자.",
                embedding=_one_hot(EMBEDDING_DIM, 0, 1.0),
                doc_metadata={"name": "가짜챔프", "cost": 3},
            )
        )
        session.commit()

        results = hybrid_search(
            session,
            INTENT_GENERAL_STRATEGY,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )
    assert "champion" in {r.doc_type for r in results}


def test_general_strategy_champion_allocation_ignores_top_k(
    seeded_docs: Engine,
) -> None:
    """2026-08-07 PM 피드백: "3코스트 챔피언은?"에 챔피언 1명만 나오던 문제 —
    champion은 top_k를 다른 doc_type과 나누지 않고 GENERAL_STRATEGY_CHAMPION_TOP_K
    만큼 고정으로 가져와야 한다(코스트 하나에 최대 18명까지 있어 균등 배분이면
    1명만 뽑힘). top_k=1로 호출해도 15명이 전부 반환되는지 확인한다."""
    with Session(seeded_docs) as session:
        for i in range(15):
            session.execute(
                insert(MetaDocumentEmbedding).values(
                    patch_version="17.8",
                    doc_type="champion",
                    source_table="champions",
                    source_id=i,
                    content_text=f"챔프{i}(3코스트) 챔피언. 특성: 학살자.",
                    embedding=_one_hot(EMBEDDING_DIM, 0, 1.0),
                    doc_metadata={"name": f"챔프{i}", "cost": 3},
                )
            )
        session.commit()

        results = hybrid_search(
            session,
            INTENT_GENERAL_STRATEGY,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
            top_k=1,
        )
    champion_results = [r for r in results if r.doc_type == "champion"]
    assert len(champion_results) == 15


def test_comp_recommendation_does_not_search_champion_doc_type(
    seeded_docs: Engine,
) -> None:
    with Session(seeded_docs) as session:
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="champion",
                source_table="champions",
                source_id=1,
                content_text="가짜챔프(3코스트) 챔피언. 특성: 학살자.",
                embedding=_one_hot(EMBEDDING_DIM, 0, 1.0),
                doc_metadata={"name": "가짜챔프", "cost": 3},
            )
        )
        session.commit()

        results = hybrid_search(
            session,
            INTENT_COMP_RECOMMENDATION,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )
    assert "champion" not in {r.doc_type for r in results}


def test_top_k_orders_by_cosine_distance_ascending(seeded_docs: Engine) -> None:
    with Session(seeded_docs) as session:
        results = hybrid_search(
            session,
            INTENT_ITEM_RECOMMENDATION,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
            top_k=5,
        )
    # source_id=1(동일 방향)이 source_id=2(직교)보다 먼저 나와야 함
    assert [r.source_id for r in results] == [1, 2]


def test_top_k_limit_is_respected(seeded_docs: Engine) -> None:
    with Session(seeded_docs) as session:
        results = hybrid_search(
            session,
            INTENT_GENERAL_STRATEGY,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
            top_k=2,
        )
    assert len(results) == 2


# ---- general_strategy doc_type 균형 배분(2026-08-07 운영 관측 버그 회귀) ---------


def test_general_strategy_guarantees_comp_representation_even_when_augments_are_closer(
    seeded_docs: Engine,
) -> None:
    """운영에서 재현된 문제: "메타" 같은 추상 질의는 코사인 거리상 augment
    청크가 comp보다 훨씬 가까울 수 있어, 순수 top-k만 쓰면 comp가 결과에서
    아예 빠진다(실측: 상위 8개 전부 augment, 최상위 comp는 377개 중 112위).
    doc_type별 최소 배분으로 comp가 항상 포함되는지 검증한다."""
    with Session(seeded_docs) as session:
        # augment 문서를 comp/playstyle과 동일하게 가장 가까운 거리로 4개 추가
        # 시딩해, 순수 top-5 정렬이라면 comp가 밀려날 수 있는 상황을 재현한다.
        for i in range(4):
            session.execute(
                insert(MetaDocumentEmbedding).values(
                    patch_version="17.8",
                    doc_type="augment",
                    source_table="augments",
                    source_id=100 + i,
                    content_text=f"augment mock {i}",
                    embedding=_one_hot(EMBEDDING_DIM, 0, 1.0),
                    doc_metadata={},
                )
            )
        session.commit()

        results = hybrid_search(
            session,
            INTENT_GENERAL_STRATEGY,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )
    assert "comp" in {r.doc_type for r in results}


def test_general_strategy_allocates_remainder_to_earlier_doc_types_first(
    seeded_docs: Engine,
) -> None:
    """top_k가 doc_type 개수(4)로 나누어떨어지지 않으면(기본 5), 나머지는
    INTENT_DOC_TYPES 순서상 앞쪽 타입(comp)부터 1개씩 더 배정된다."""
    with Session(seeded_docs) as session:
        results = hybrid_search(
            session,
            INTENT_GENERAL_STRATEGY,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
            top_k=5,
        )
    comp_count = sum(1 for r in results if r.doc_type == "comp")
    # fixture에는 comp 문서가 1개뿐이라 배정된 2개 중 실제로는 1개만 반환됨
    assert comp_count == 1


# ---- tier_rank 우선순위 정렬(2026-08-07 PM 피드백 회귀) --------------------------


def test_comp_recommendation_orders_higher_tier_before_closer_lower_tier(
    seeded_docs: Engine,
) -> None:
    """티어가 1차 정렬 기준이어야 한다 — 코사인 거리가 더 가까운 A티어보다
    티어가 높은 OP가 항상 먼저 나와야 한다(2026-08-07 PM 피드백: "메타" 질의에
    A티어만 나오고 OP/S티어 조합이 검색조차 안 됨)."""
    with Session(seeded_docs) as session:
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="comp",
                source_table="comps",
                source_id=201,
                content_text="A티어 조합(거리 가까움)",
                embedding=_one_hot(EMBEDDING_DIM, 0, 1.0),  # 쿼리와 동일 방향(최단거리)
                doc_metadata={"tier_rank": "A"},
            )
        )
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="comp",
                source_table="comps",
                source_id=202,
                content_text="OP티어 조합(거리 멂)",
                embedding=_one_hot(EMBEDDING_DIM, 1, 1.0),  # 직교(더 먼 거리)
                doc_metadata={"tier_rank": "OP"},
            )
        )
        session.commit()

        results = hybrid_search(
            session,
            INTENT_COMP_RECOMMENDATION,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
            top_k=1,
        )
    # 거리만 보면 201(A)이 훨씬 가깝지만, 티어가 더 높은 202(OP)가 나와야 함
    assert [r.source_id for r in results] == [202]


def test_general_strategy_balanced_search_orders_comp_allocation_by_tier(
    seeded_docs: Engine,
) -> None:
    """doc_type 균형 배분(comp 슬롯) 안에서도 티어 우선순위가 적용돼야 한다."""
    with Session(seeded_docs) as session:
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="comp",
                source_table="comps",
                source_id=301,
                content_text="B티어 조합(거리 가까움)",
                embedding=_one_hot(EMBEDDING_DIM, 0, 1.0),
                doc_metadata={"tier_rank": "B"},
            )
        )
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="comp",
                source_table="comps",
                source_id=302,
                content_text="S티어 조합(거리 멂)",
                embedding=_one_hot(EMBEDDING_DIM, 1, 1.0),
                doc_metadata={"tier_rank": "S"},
            )
        )
        session.commit()

        results = hybrid_search(
            session,
            INTENT_GENERAL_STRATEGY,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
            top_k=4,
        )
    comp_results = [r for r in results if r.doc_type == "comp"]
    assert comp_results[0].source_id == 302


# ---- lookup_item_builds_by_champion_ids: 구조화 조회(2026-08-07 PM 요청) --------


def test_lookup_item_builds_by_champion_ids_returns_only_requested_champions(
    seeded_docs: Engine,
) -> None:
    """의미 검색을 완전히 우회해 정확히 요청한 champion_id들의 빌드만
    반환해야 한다 — "이 챔피언들" 후속질문에 무관한 챔피언이 섞이던 문제의
    근본 해결책."""
    with Session(seeded_docs) as session:
        session.execute(
            insert(Champion).values(
                id=1001,
                patch_version="17.8",
                riot_champion_id="TFT17_Bard",
                name_kr="바드",
                name_en="Bard",
                cost=5,
            )
        )
        session.execute(
            insert(Champion).values(
                id=1002,
                patch_version="17.8",
                riot_champion_id="TFT17_Shen",
                name_kr="쉔",
                name_en="Shen",
                cost=5,
            )
        )
        # 요청하지 않을 챔피언(아리) — 결과에 섞이면 안 됨
        session.execute(
            insert(Champion).values(
                id=1003,
                patch_version="17.8",
                riot_champion_id="TFT17_Ahri",
                name_kr="아리",
                name_en="Ahri",
                cost=4,
            )
        )
        for name, source_id in [("바드", 500), ("쉔", 501), ("아리", 502)]:
            session.execute(
                insert(MetaDocumentEmbedding).values(
                    patch_version="17.8",
                    doc_type="item_build",
                    source_table="champion_item_builds",
                    source_id=source_id,
                    content_text=f"{name} 아이템 빌드",
                    embedding=_one_hot(EMBEDDING_DIM, 0, 1.0),
                    doc_metadata={"champion": name},
                )
            )
        session.commit()

        results = lookup_item_builds_by_champion_ids(session, "17.8", [1001, 1002])

    champion_names = {r.doc_metadata["champion"] for r in results}
    assert champion_names == {"바드", "쉔"}


def test_lookup_item_builds_by_champion_ids_caps_per_champion(
    seeded_docs: Engine,
) -> None:
    with Session(seeded_docs) as session:
        session.execute(
            insert(Champion).values(
                id=1001,
                patch_version="17.8",
                riot_champion_id="TFT17_Bard",
                name_kr="바드",
                name_en="Bard",
                cost=5,
            )
        )
        for i in range(5):
            session.execute(
                insert(MetaDocumentEmbedding).values(
                    patch_version="17.8",
                    doc_type="item_build",
                    source_table="champion_item_builds",
                    source_id=600 + i,
                    content_text=f"바드 아이템 빌드 {i}",
                    embedding=_one_hot(EMBEDDING_DIM, 0, 1.0),
                    doc_metadata={"champion": "바드"},
                )
            )
        session.commit()

        results = lookup_item_builds_by_champion_ids(session, "17.8", [1001])

    assert len(results) == 2


def test_lookup_item_builds_by_champion_ids_returns_empty_for_empty_input(
    seeded_docs: Engine,
) -> None:
    with Session(seeded_docs) as session:
        assert lookup_item_builds_by_champion_ids(session, "17.8", []) == []


def test_lookup_item_builds_by_champion_ids_returns_empty_for_unknown_ids(
    seeded_docs: Engine,
) -> None:
    with Session(seeded_docs) as session:
        assert lookup_item_builds_by_champion_ids(session, "17.8", [999999]) == []
