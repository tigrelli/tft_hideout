"""CHAT-33 pytest: 비한국어(영어) 질의 감지가 실제 스트림 조기반환까지
이어지는지 확인. TEST-11 H17("Can you explain the best comp in English?")가
전부 한국어로만 답하고 언어 안내조차 없던 문제를 재현·방지한다."""

from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from services.chat_stream import (
    NON_KOREAN_LANGUAGE_MESSAGE,
    generate_answer_stream,
)


def _fail_if_called(name: str):
    def _fn(*args: object, **kwargs: object) -> object:
        raise AssertionError(f"{name}이 호출되면 안 됨")

    return _fn


def test_english_question_short_circuits_with_language_notice(
    migrated_engine: Engine,
) -> None:
    """embed_fn/offtopic_confirm_fn/classify_fn/search_fn/web_search_fn/stream_fn
    전부 호출되지 않고, patch_version 조회조차 필요 없는 가장 이른 조기
    반환인지 확인(patch 데이터 없는 순수 migrated_engine으로 검증,
    chatbot_meta·off_topic과 동일한 설계)."""
    with Session(migrated_engine) as session:
        tokens = list(
            generate_answer_stream(
                session,
                "11111111-1111-1111-1111-111111111111",
                "Can you explain the best comp in English?",
                embed_fn=_fail_if_called("embed_fn"),
                offtopic_confirm_fn=_fail_if_called("offtopic_confirm_fn"),
                classify_fn=_fail_if_called("classify_fn"),
                search_fn=_fail_if_called("search_fn"),
                web_search_fn=_fail_if_called("web_search_fn"),
                stream_fn=_fail_if_called("stream_fn"),
            )
        )
    assert " ".join(tokens) == NON_KOREAN_LANGUAGE_MESSAGE


def test_korean_question_is_not_affected(migrated_engine: Engine) -> None:
    """회귀 방지 — 한국어 질문은 언어 안내로 새지 않고 정상 파이프라인을
    계속 탄다(off_topic 확인까지는 도달해야 함)."""
    with Session(migrated_engine) as session:
        tokens = list(
            generate_answer_stream(
                session,
                "22222222-2222-2222-2222-222222222222",
                "오늘 점심 뭐 먹지",
                embed_fn=_fail_if_called("embed_fn"),
                offtopic_confirm_fn=lambda text: True,
                classify_fn=_fail_if_called("classify_fn"),
                search_fn=_fail_if_called("search_fn"),
                web_search_fn=_fail_if_called("web_search_fn"),
                stream_fn=_fail_if_called("stream_fn"),
            )
        )
    assert tokens != [NON_KOREAN_LANGUAGE_MESSAGE]
