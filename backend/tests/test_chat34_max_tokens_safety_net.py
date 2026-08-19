"""CHAT-34 pytest: stream_groq_chat()에 방어적 max_tokens 상한이 실제로
전달되는지 확인. TEST-11 D1 조사 결과, 실측 API 호출 6회로는 재현되지
않아(4/4 정상 완전 답변, reasoning_effort="low"는 오히려 역효과로 확인돼
폐기) 결정론적 버그 수정 대신 방어적 안전망만 추가하기로 PM이 결정했다
(docs/verification/CHAT-34-작업결과.md 참고). 실제 Groq API는 호출하지
않고 클라이언트를 mock으로 대체한다(policies.md 10.2/11)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.groq_client import _MAIN_ANSWER_MAX_TOKENS, stream_groq_chat


def test_stream_groq_chat_sets_defensive_max_tokens() -> None:
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = iter([])

    with patch("services.groq_client._get_client", return_value=fake_client):
        list(stream_groq_chat("system", "user"))

    _args, kwargs = fake_client.chat.completions.create.call_args
    assert kwargs["max_tokens"] == _MAIN_ANSWER_MAX_TOKENS


def test_stream_groq_chat_does_not_set_reasoning_effort() -> None:
    """PM 결정(2026-08-19) — reasoning_effort="low"는 답변 포기율을 오히려
    높이는 역효과가 실측 확인돼 메인 답변 생성 경로에는 적용하지 않는다
    (분류 등 짧은 호출 전용인 call_groq_chat의 _SHORT_CALL_REASONING_EFFORT와
    다른 경로임을 명확히 하는 회귀 방지 테스트)."""
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = iter([])

    with patch("services.groq_client._get_client", return_value=fake_client):
        list(stream_groq_chat("system", "user"))

    _args, kwargs = fake_client.chat.completions.create.call_args
    assert "reasoning_effort" not in kwargs
