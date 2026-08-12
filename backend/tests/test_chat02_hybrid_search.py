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
from services.hybrid_search import (
    filter_by_name_overlap,
    hybrid_search,
    lookup_item_builds_by_champion_ids,
)
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


# CHAT-14: 아이템 효과 자체를 묻는 질문("보석 건틀릿 아이템 효과 알려줘")에
# 답할 수 있도록 item_recommendation이 item_build와 함께 item(DATA-19 description
# 기반) 문서도 검색하는지 확인.
def test_item_recommendation_also_searches_item_doc_type(seeded_docs: Engine) -> None:
    with Session(seeded_docs) as session:
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="item",
                source_table="items",
                source_id=1,
                content_text="보석 건틀릿: 치명타 확률이 증가합니다.",
                embedding=_one_hot(EMBEDDING_DIM, 0, 1.0),
                doc_metadata={"name": "보석 건틀릿"},
            )
        )
        session.commit()

        results = hybrid_search(
            session,
            INTENT_ITEM_RECOMMENDATION,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )
    assert "item" in {r.doc_type for r in results}
    assert "item_build" in {r.doc_type for r in results}


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


# CHAT-14: "보석 건틀릿 효과가 뭐야?"처럼 "아이템" 키워드 없이 묻는 질문은
# item_recommendation이 아니라 general_strategy로 분류되므로(intent_
# classification.py의 키워드 정규식 기준) 여기서도 item 문서를 찾을 수 있어야 함.
def test_general_strategy_includes_item_doc_type(seeded_docs: Engine) -> None:
    with Session(seeded_docs) as session:
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="item",
                source_table="items",
                source_id=1,
                content_text="보석 건틀릿: 치명타 확률이 증가합니다.",
                embedding=_one_hot(EMBEDDING_DIM, 0, 1.0),
                doc_metadata={"name": "보석 건틀릿"},
            )
        )
        session.commit()

        results = hybrid_search(
            session,
            INTENT_GENERAL_STRATEGY,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )
    assert "item" in {r.doc_type for r in results}


# ---- CHAT-15: 검색 결과 최소 유사도 신뢰도 임계값(2026-08-09 PM 제보) -------------
# "죽무 효과는?"처럼 사전에 없는 줄임말이 전혀 다른 아이템('절멸자')으로
# 오검색된 사례 — item/augment doc_type은 코사인 거리가 임계값(_DOC_TYPE_
# MAX_DISTANCE)을 넘으면(=너무 멀면) 애초에 후보에서 빠져야 한다. champion/comp는
# 실측상 정상 케이스도 거리가 멀 수 있어(설계 주석 참고) 의도적으로 임계값을
# 적용하지 않는다 — 회귀 확인용 테스트도 함께 둔다.


def test_item_recommendation_excludes_item_doc_too_far_from_query(
    seeded_docs: Engine,
) -> None:
    with Session(seeded_docs) as session:
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="item",
                source_table="items",
                source_id=99,
                content_text="먼 아이템 문서",
                embedding=_one_hot(EMBEDDING_DIM, 5, 1.0),  # 질의와 직교(거리 1.0)
                doc_metadata={"name": "먼아이템"},
            )
        )
        session.commit()

        results = hybrid_search(
            session,
            INTENT_ITEM_RECOMMENDATION,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )
    assert "item" not in {r.doc_type for r in results}


def test_general_strategy_excludes_item_doc_too_far_from_query(
    seeded_docs: Engine,
) -> None:
    with Session(seeded_docs) as session:
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="item",
                source_table="items",
                source_id=99,
                content_text="먼 아이템 문서",
                embedding=_one_hot(EMBEDDING_DIM, 5, 1.0),
                doc_metadata={"name": "먼아이템"},
            )
        )
        session.commit()

        results = hybrid_search(
            session,
            INTENT_GENERAL_STRATEGY,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )
    assert "item" not in {r.doc_type for r in results}


def test_augment_recommendation_excludes_augment_doc_too_far_from_query(
    seeded_docs: Engine,
) -> None:
    """base seeded_docs의 augment 문서는 질의와 거리 0(포함돼야 함), 여기서
    추가하는 문서는 직교(거리 1.0, 제외돼야 함) — 같은 doc_type 안에서
    가까운/먼 문서가 실제로 갈리는지 확인한다."""
    with Session(seeded_docs) as session:
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="augment",
                source_table="augments",
                source_id=99,
                content_text="먼 증강체 문서",
                embedding=_one_hot(EMBEDDING_DIM, 5, 1.0),
                doc_metadata={"name": "먼증강체"},
            )
        )
        session.commit()

        results = hybrid_search(
            session,
            INTENT_AUGMENT_RECOMMENDATION,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )
    names = {r.doc_metadata.get("name") for r in results}
    assert "먼증강체" not in names
    assert len(results) == 1  # base fixture의 가까운 augment 문서 1개만 남음


def test_item_recommendation_returns_no_item_docs_when_all_too_far(
    seeded_docs: Engine,
) -> None:
    """item doc_type 후보가 전부 임계값 밖이면 에러 없이 빈 결과여야 한다
    (item_build 결과는 별개 경로라 영향 없음, 이 경우 전체 흐름은 CHAT-14의
    "정보 없음" 답변 경로로 자연스럽게 이어진다)."""
    with Session(seeded_docs) as session:
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="item",
                source_table="items",
                source_id=99,
                content_text="먼 아이템 문서",
                embedding=_one_hot(EMBEDDING_DIM, 5, 1.0),
                doc_metadata={"name": "먼아이템"},
            )
        )
        session.commit()

        results = hybrid_search(
            session,
            INTENT_ITEM_RECOMMENDATION,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )
    assert results  # item_build 결과는 남아있음(임계값 미적용 doc_type)
    assert "item" not in {r.doc_type for r in results}


def test_general_strategy_still_includes_far_champion_doc(
    seeded_docs: Engine,
) -> None:
    """champion doc_type은 CHAT-15 임계값을 의도적으로 적용하지 않는다(실측:
    정상적인 특정 챔피언 이름 질의도 거리 0.5대라 item의 "나쁜 매칭" 구간과
    겹침, 위 hybrid_search 모듈 주석 참고) — 먼 champion 문서도 그대로 남아야
    회귀가 아니다."""
    with Session(seeded_docs) as session:
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="champion",
                source_table="champions",
                source_id=1,
                content_text="먼챔프(3코스트) 챔피언. 특성: 학살자.",
                embedding=_one_hot(EMBEDDING_DIM, 5, 1.0),  # 직교(거리 1.0)
                doc_metadata={"name": "먼챔프", "cost": 3},
            )
        )
        session.commit()

        results = hybrid_search(
            session,
            INTENT_GENERAL_STRATEGY,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )
    assert "먼챔프" in {
        r.doc_metadata.get("name") for r in results if r.doc_type == "champion"
    }


def test_comp_recommendation_still_includes_far_comp_doc(seeded_docs: Engine) -> None:
    """comp doc_type도 CHAT-15 임계값을 의도적으로 적용하지 않는다(실측: 특정
    조합명이 아닌 일반 "메타 추천" 질의가 정상인데도 거리 0.48~0.49로 나옴)."""
    with Session(seeded_docs) as session:
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="comp",
                source_table="comps",
                source_id=99,
                content_text="먼 조합 문서",
                embedding=_one_hot(EMBEDDING_DIM, 5, 1.0),
                doc_metadata={"name": "먼조합"},
            )
        )
        session.commit()

        results = hybrid_search(
            session,
            INTENT_COMP_RECOMMENDATION,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
        )
    assert "먼조합" in {
        r.doc_metadata.get("name") for r in results if r.doc_type == "comp"
    }


# ---- CHAT-15 2차 보정: filter_by_name_overlap() (2026-08-09 PM 검증 중 발견) ------
# 거리 임계값 회색지대(0.45~0.55)를 문자 겹침 비율로 추가 방어. 실측 사례
# 재현: "광폭검 효과는?"(존재하지 않는 아이템)이 '포악한 절단검'과 거리 0.49로
# 임계값(0.5)은 통과했지만 이름 글자는 '검' 1개만 겹침(6개 중 1개, 비율 0.167).


class _FakeDoc:
    def __init__(self, doc_type: str, name: str) -> None:
        self.doc_type = doc_type
        self.doc_metadata = {"name": name}


def test_filter_by_name_overlap_keeps_item_when_name_fully_present_in_query() -> None:
    docs = [_FakeDoc("item", "보석 건틀릿")]
    assert filter_by_name_overlap(docs, "보석 건틀릿 효과는?") == docs


def test_filter_by_name_overlap_drops_item_when_name_barely_overlaps_query() -> None:
    """실측 재현: '포악한 절단검'과 "광폭검 효과는?"은 '검' 1글자만 겹침(비율
    0.167, 기준 0.5 미달)."""
    docs = [_FakeDoc("item", "포악한 절단검")]
    assert filter_by_name_overlap(docs, "광폭검 효과는?") == []


def test_filter_by_name_overlap_ignores_doc_types_outside_item_and_augment() -> None:
    docs = [_FakeDoc("comp", "전혀 안 겹치는 조합명"), _FakeDoc("champion", "무관챔프")]
    assert filter_by_name_overlap(docs, "지금 메타 조합 추천해줘") == docs


def test_filter_by_name_overlap_applies_to_augment_too() -> None:
    docs = [_FakeDoc("augment", "동물특공대 지휘관")]
    assert filter_by_name_overlap(docs, "동물특공대 지휘관 효과는?") == docs
    assert filter_by_name_overlap(docs, "전혀 무관한 질문") == []


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
    """top_k가 champion 제외 doc_type 개수(CHAT-14로 5: comp/playstyle/augment/
    item_build/item)로 나누어떨어지지 않으면, 나머지는 INTENT_DOC_TYPES 순서상
    앞쪽 타입(comp)부터 1개씩 더 배정된다."""
    with Session(seeded_docs) as session:
        results = hybrid_search(
            session,
            INTENT_GENERAL_STRATEGY,
            "17.8",
            _one_hot(EMBEDDING_DIM, 0, 1.0),
            top_k=6,
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


# CHAT-18(PM 제보 2026-08-12): DATA-17 소프트 삭제(is_active=false)된 조합은
# op.gg 상위 10위에서 밀려난 이후 tier_rank가 갱신 없이 얼어붙는다 — 활성
# 조합보다 항상 뒤로 밀려야 한다(얼어붙은 옛 "S"가 지금 활성인 "A"를 이기면 안 됨).
def test_comp_recommendation_ranks_active_comp_before_inactive_even_if_lower_tier(
    seeded_docs: Engine,
) -> None:
    with Session(seeded_docs) as session:
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="comp",
                source_table="comps",
                source_id=401,
                content_text="비활성 S티어 조합(거리 가까움)",
                embedding=_one_hot(EMBEDDING_DIM, 0, 1.0),
                doc_metadata={"tier_rank": "S", "is_active": False},
            )
        )
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="comp",
                source_table="comps",
                source_id=402,
                content_text="활성 A티어 조합(거리 멂)",
                embedding=_one_hot(EMBEDDING_DIM, 1, 1.0),
                doc_metadata={"tier_rank": "A", "is_active": True},
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
    # 티어(S>A)·거리 모두 401이 유리하지만, 비활성이라 활성인 402가 먼저 나와야 함
    assert [r.source_id for r in results] == [402]


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
