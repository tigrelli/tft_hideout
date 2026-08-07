"""CHAT-08 pytest(WBS 테스트 요구사항: 첫턴 캐시 hit, 후속턴 캐시 미적용,
패치갱신 후 캐시 무효화 확인)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.models import ChatLog, MetaDocumentEmbedding, Patch
from services.chat_cache import (
    compute_cache_key,
    get_cached_answer,
    store_answer_in_cache,
)
from services.chat_stream import generate_answer_stream
from services.intent_classification import INTENT_COMP_RECOMMENDATION


@pytest.fixture
def seeded_patch_session(migrated_engine: Engine) -> Session:
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
        session.commit()
        yield session


def _fail_if_called(name: str):
    def _fn(*args, **kwargs):
        raise AssertionError(f"{name}가 호출되면 안 됨(캐시 hit이어야 함)")

    return _fn


# ---- compute_cache_key / get_cached_answer / store_answer_in_cache -------------


def test_compute_cache_key_differs_by_patch_version() -> None:
    key_a = compute_cache_key("지금 메타 조합", "17.8")
    key_b = compute_cache_key("지금 메타 조합", "17.9")
    assert key_a != key_b


def test_compute_cache_key_same_input_same_key() -> None:
    assert compute_cache_key("질문", "17.8") == compute_cache_key("질문", "17.8")


def test_get_cached_answer_returns_none_when_no_entry(
    seeded_patch_session: Session,
) -> None:
    assert get_cached_answer(seeded_patch_session, "질문", "17.8") is None


def test_store_then_get_cached_answer_round_trip(
    seeded_patch_session: Session,
) -> None:
    store_answer_in_cache(seeded_patch_session, "질문", "17.8", "답변입니다")
    assert get_cached_answer(seeded_patch_session, "질문", "17.8") == "답변입니다"


def test_store_answer_upserts_on_same_cache_key(seeded_patch_session: Session) -> None:
    store_answer_in_cache(seeded_patch_session, "질문", "17.8", "첫 답변")
    store_answer_in_cache(seeded_patch_session, "질문", "17.8", "갱신된 답변")
    assert get_cached_answer(seeded_patch_session, "질문", "17.8") == "갱신된 답변"


# ---- WBS #1: 첫 턴 캐시 hit -> 파이프라인 전체 스킵 ------------------------------


def test_first_turn_cache_hit_skips_pipeline_entirely(
    seeded_patch_session: Session,
) -> None:
    store_answer_in_cache(
        seeded_patch_session, "지금 메타 조합 추천해줘", "17.8", "캐시된 답변입니다"
    )

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "지금 메타 조합 추천해줘",
            embed_fn=_fail_if_called("embed_fn"),
            classify_fn=_fail_if_called("classify_fn"),
            search_fn=_fail_if_called("search_fn"),
            stream_fn=_fail_if_called("stream_fn"),
        )
    )

    assert "".join(f"{t} " for t in tokens).strip() == "캐시된 답변입니다"


def test_first_turn_cache_miss_generates_and_stores(
    seeded_patch_session: Session,
) -> None:
    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "새로 생성된 답변"

    session_id = "11111111-1111-1111-1111-111111111111"
    list(
        generate_answer_stream(
            seeded_patch_session,
            session_id,
            "지금 메타 조합 추천해줘",
            embed_fn=lambda text: [0.0],
            classify_fn=lambda text: INTENT_COMP_RECOMMENDATION,
            # retrieved_docs가 비어 있으면 2026-08-07 변경으로 캐시되지 않으므로
            # (근거 없는 답변은 후속질문 무의미 문제 재발 방지), 이 테스트가
            # 검증하려는 "정상 캐시 저장" 시나리오에는 문서가 하나 이상 있어야 함.
            search_fn=lambda db, intent, patch, emb: [MetaDocumentEmbedding()],
            stream_fn=fake_stream_fn,
        )
    )

    cached = get_cached_answer(seeded_patch_session, "지금 메타 조합 추천해줘", "17.8")
    assert cached == "새로 생성된 답변"


def test_groq_fallback_message_is_not_cached(seeded_patch_session: Session) -> None:
    """캐시 키가 session_id가 아니라 질문 문장+패치 버전이라, 폴백 메시지를
    캐시하면 그 문장을 묻는 모든 세션이 다음 패치까지 계속 폴백만 받게 된다
    (CHAT-11 배포 검증 중 실제로 재현된 버그, 2026-08-06 수정)."""

    def always_failing_stream_fn(system_prompt: str, user_message: str):
        raise TimeoutError("mock Groq 완전 실패")
        yield  # pragma: no cover - 제너레이터 형태 유지용

    list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "지금 메타 조합 추천해줘",
            embed_fn=lambda text: [0.0],
            classify_fn=lambda text: INTENT_COMP_RECOMMENDATION,
            search_fn=lambda db, intent, patch, emb: [],
            stream_fn=always_failing_stream_fn,
        )
    )

    assert (
        get_cached_answer(seeded_patch_session, "지금 메타 조합 추천해줘", "17.8")
        is None
    )


# ---- WBS #2: 후속 턴은 캐시 미적용(hit이 있어도 무시하고 파이프라인 실행) -------


def test_subsequent_turn_ignores_cache_even_if_entry_exists(
    seeded_patch_session: Session,
) -> None:
    session_id = "11111111-1111-1111-1111-111111111111"
    store_answer_in_cache(
        seeded_patch_session, "그 조합 더 알려줘", "17.8", "이건 절대 반환되면 안 됨"
    )
    # 이 세션에 이미 대화 이력이 있다고 만들어 후속 턴 상황을 재현
    seeded_patch_session.execute(
        insert(ChatLog).values(
            session_id=session_id,
            patch_version="17.8",
            user_query="이전 질문",
            intent=INTENT_COMP_RECOMMENDATION,
            retrieved_doc_ids=[],
            answer="이전 답변",
            latency_ms=100,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    seeded_patch_session.commit()

    calls = {"stream_called": False}

    def fake_stream_fn(system_prompt: str, user_message: str):
        calls["stream_called"] = True
        yield "실제로 생성된 후속 답변"

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            session_id,
            "그 조합 더 알려줘",
            embed_fn=lambda text: [0.0],
            classify_fn=lambda text: INTENT_COMP_RECOMMENDATION,
            search_fn=lambda db, intent, patch, emb: [],
            stream_fn=fake_stream_fn,
        )
    )

    assert calls["stream_called"] is True
    assert "이건" not in " ".join(tokens)
    assert "실제로" in " ".join(tokens)


# ---- WBS #3: 패치 갱신 후 캐시 무효화(자연 무효화 — cache_key가 달라짐) --------


def test_cache_invalidated_after_patch_update(seeded_patch_session: Session) -> None:
    store_answer_in_cache(
        seeded_patch_session, "지금 메타 조합 추천해줘", "17.8", "17.8 시절 답변"
    )

    # 패치 갱신: 새 버전을 is_current로 승격(DATA-13과 동일한 형태의 상태 변화)
    seeded_patch_session.execute(
        insert(Patch).values(
            version="17.9",
            set_number=17,
            released_at=datetime(2026, 2, 1, tzinfo=UTC),
            is_current=True,
            detected_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
    )
    seeded_patch_session.execute(
        Patch.__table__.update().where(Patch.version == "17.8").values(is_current=False)
    )
    seeded_patch_session.commit()

    assert (
        get_cached_answer(seeded_patch_session, "지금 메타 조합 추천해줘", "17.8")
        == "17.8 시절 답변"
    )
    # 새 패치 버전으로는 캐시가 없음(자연 무효화)
    assert (
        get_cached_answer(seeded_patch_session, "지금 메타 조합 추천해줘", "17.9")
        is None
    )
