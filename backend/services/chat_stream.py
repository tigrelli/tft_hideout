from collections.abc import Generator


def mock_llm_stream(message: str) -> Generator[str, None, None]:
    """CHAT-05에서 실제 Groq 스트리밍 호출로 교체될 자리표시자.
    API-09는 SSE 배관만 검증하므로 입력을 토큰(단어) 단위로 그대로 되돌려 보낸다."""
    yield from message.split()


def build_sse_stream(message: str) -> Generator[str, None, None]:
    """LLM 토큰 제너레이터를 SSE(text/event-stream) 포맷으로 감싼다.
    각 토큰은 `data:` 이벤트로, 스트림 종료는 별도 `done` 이벤트로 보내
    클라이언트가 연결 종료 시점을 명확히 알 수 있게 한다."""
    for token in mock_llm_stream(message):
        yield f"data: {token}\n\n"
    yield "event: done\ndata: [DONE]\n\n"
