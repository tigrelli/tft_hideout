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

from db.models import EMBEDDING_DIM, MetaDocumentEmbedding, Patch
from services.embedding_client import EmbeddingError, HuggingFaceEmbeddingClient
from services.hybrid_search import hybrid_search
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
