"""API-09: SSE 스트리밍 인프라 자체(배관)만 검증한다. 실제 LLM 파이프라인
배선(의도분류/검색/프롬프트조립/Groq 스트리밍)은 CHAT-05가 대체했고,
그쪽 테스트는 test_chat05_streaming.py에 있다."""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_chat_message_endpoint_invalid_session_id_returns_400(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/chat/message",
        json={"session_id": "not-a-uuid", "message": "안녕"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_session_id"


def test_chat_message_endpoint_missing_session_id_returns_422(
    client: TestClient,
) -> None:
    response = client.post("/api/v1/chat/message", json={"message": "안녕"})
    assert response.status_code == 422
