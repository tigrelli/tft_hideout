"""CHAT-05 pytest(WBS 테스트 요구사항: mock Groq 클라이언트로 SSE 스트리밍 조립
확인, 타임아웃 예외 처리 확인). 외부 API(Groq/HF)는 전부 주입식 fake로 대체
(policies.md 10.2/11)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.models import ChatLog, Patch
from services.chat_stream import (
    CLARIFICATION_MESSAGE,
    FALLBACK_MESSAGE,
    NO_CURRENT_PATCH_MESSAGE,
    OFF_TOPIC_MESSAGE,
    build_sse_stream,
    generate_answer_stream,
    stream_llm_answer,
)
from services.intent_classification import INTENT_COMP_RECOMMENDATION

# ---- build_sse_stream(토큰 제너레이터 -> SSE 포맷) -------------------------------


def test_build_sse_stream_emits_data_events_then_done_event() -> None:
    def tokens():
        yield from ["가장", "좋은", "덱은"]

    events = list(build_sse_stream(tokens()))

    assert events[:-1] == ["data: 가장\n\n", "data: 좋은\n\n", "data: 덱은\n\n"]
    assert events[-1] == "event: done\ndata: [DONE]\n\n"


# ---- stream_llm_answer: 재시도 + 폴백(WBS 핵심 요구사항) -------------------------


def test_stream_llm_answer_succeeds_on_first_try() -> None:
    def stream_fn(system_prompt: str, user_message: str):
        yield from ["안녕", "하세요"]

    tokens = list(stream_llm_answer("sys", "user", stream_fn))
    assert tokens == ["안녕", "하세요"]


def test_stream_llm_answer_retries_once_on_failure_before_any_token() -> None:
    attempts = {"n": 0}

    def stream_fn(system_prompt: str, user_message: str):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise TimeoutError("mock 타임아웃")
        yield from ["재시도", "성공"]

    tokens = list(stream_llm_answer("sys", "user", stream_fn))

    assert attempts["n"] == 2
    assert tokens == ["재시도", "성공"]


def test_stream_llm_answer_falls_back_after_exhausting_retries() -> None:
    def stream_fn(system_prompt: str, user_message: str):
        raise TimeoutError("mock 타임아웃")
        yield  # pragma: no cover - 제너레이터 형태 유지용

    tokens = list(stream_llm_answer("sys", "user", stream_fn))

    assert tokens == [FALLBACK_MESSAGE]


def test_stream_llm_answer_falls_back_without_retry_if_partial_tokens_already_sent() -> (
    None
):
    """스트림 도중 실패하면(이미 일부 토큰을 보낸 뒤) 재시도하지 않고
    폴백 메시지를 이어 붙인다(중복 전송 방지)."""
    attempts = {"n": 0}

    def stream_fn(system_prompt: str, user_message: str):
        attempts["n"] += 1
        yield "일부"
        raise TimeoutError("mock 도중 실패")

    tokens = list(stream_llm_answer("sys", "user", stream_fn))

    assert attempts["n"] == 1  # 재시도 안 함
    assert tokens == ["일부", FALLBACK_MESSAGE]


# ---- generate_answer_stream: 전처리 분기 + 전체 배선 -----------------------------


def _fail_if_called(name: str):
    def _fn(*args, **kwargs):
        raise AssertionError(f"{name}가 호출되면 안 됨(범위 밖/명확화 분기여야 함)")

    return _fn


def test_needs_clarification_short_circuits_without_calling_pipeline(
    migrated_engine: Engine,
) -> None:
    with Session(migrated_engine) as session:
        tokens = list(
            generate_answer_stream(
                session,
                "11111111-1111-1111-1111-111111111111",
                "   ",  # 공백만 -> needs_clarification
                embed_fn=_fail_if_called("embed_fn"),
                classify_fn=_fail_if_called("classify_fn"),
                search_fn=_fail_if_called("search_fn"),
                stream_fn=_fail_if_called("stream_fn"),
            )
        )
    assert tokens == [CLARIFICATION_MESSAGE]


def test_off_topic_short_circuits_without_calling_pipeline(
    migrated_engine: Engine,
) -> None:
    with Session(migrated_engine) as session:
        tokens = list(
            generate_answer_stream(
                session,
                "11111111-1111-1111-1111-111111111111",
                "오늘 점심 뭐 먹지",  # TFT 무관
                embed_fn=_fail_if_called("embed_fn"),
                classify_fn=_fail_if_called("classify_fn"),
                search_fn=_fail_if_called("search_fn"),
                stream_fn=_fail_if_called("stream_fn"),
            )
        )
    assert tokens == [OFF_TOPIC_MESSAGE]


def test_no_current_patch_returns_fixed_message(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        tokens = list(
            generate_answer_stream(
                session,
                "11111111-1111-1111-1111-111111111111",
                "지금 메타 조합 추천해줘",
                embed_fn=_fail_if_called("embed_fn"),
                classify_fn=_fail_if_called("classify_fn"),
                search_fn=_fail_if_called("search_fn"),
                stream_fn=_fail_if_called("stream_fn"),
            )
        )
    assert tokens == [NO_CURRENT_PATCH_MESSAGE]


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


def test_normal_flow_wires_intent_search_and_prompt_into_stream_fn(
    seeded_patch_session: Session,
) -> None:
    calls: dict = {}

    def fake_embed_fn(text: str) -> list[float]:
        calls["embed_text"] = text
        return [0.1, 0.2]

    def fake_classify_fn(text: str) -> str:
        calls["classify_text"] = text
        return INTENT_COMP_RECOMMENDATION

    def fake_search_fn(db, intent, patch_version, embedding):
        calls["search_args"] = (intent, patch_version, embedding)
        return []

    def fake_stream_fn(system_prompt: str, user_message: str):
        calls["system_prompt"] = system_prompt
        calls["user_message"] = user_message
        # CHAT-06부터 generate_answer_stream이 전체 응답을 버퍼링("".join)한 뒤
        # 공백 기준으로 다시 쪼개 내보내므로, 실제 Groq 델타처럼 두 번째 토큰에
        # 선행 공백을 포함시켜야 "안녕 하세요"로 정확히 복원된다.
        yield from ["안녕", " 하세요"]

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "지금 메타 조합 추천해줘",
            embed_fn=fake_embed_fn,
            classify_fn=fake_classify_fn,
            search_fn=fake_search_fn,
            stream_fn=fake_stream_fn,
        )
    )

    assert tokens == ["안녕", "하세요"]
    assert calls["classify_text"] == "지금 메타 조합 추천해줘"
    assert calls["embed_text"] == "지금 메타 조합 추천해줘"
    assert calls["search_args"] == (INTENT_COMP_RECOMMENDATION, "17.8", [0.1, 0.2])
    assert "[사용자 메시지]" in calls["user_message"]
    assert "지금 메타 조합 추천해줘" in calls["user_message"]
    assert "티어" in calls["system_prompt"]  # 조합 추천 의도별 추가지시 포함


def test_normal_flow_includes_conversation_history_in_prompt(
    seeded_patch_session: Session,
) -> None:
    seeded_patch_session.execute(
        insert(ChatLog).values(
            session_id="11111111-1111-1111-1111-111111111111",
            patch_version="17.8",
            user_query="이전 질문",
            intent=INTENT_COMP_RECOMMENDATION,
            retrieved_doc_ids={},
            answer="이전 답변",
            latency_ms=100,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    seeded_patch_session.commit()

    captured_prompt = {}

    def fake_stream_fn(system_prompt: str, user_message: str):
        captured_prompt["user_message"] = user_message
        yield "답변"

    list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "지금 메타 조합 추천해줘",
            embed_fn=lambda text: [0.0],
            classify_fn=lambda text: INTENT_COMP_RECOMMENDATION,
            search_fn=lambda db, intent, patch, emb: [],
            stream_fn=fake_stream_fn,
        )
    )

    assert "[이전 대화]" in captured_prompt["user_message"]
    assert "이전 질문" in captured_prompt["user_message"]
