import uuid

import pytest
from fastapi.testclient import TestClient

from main import app
from services.chat_stream import build_sse_stream, mock_llm_stream


def test_mock_llm_stream_yields_tokens_in_order() -> None:
    tokens = list(mock_llm_stream("최적의 조합을 추천해줘"))
    assert tokens == ["최적의", "조합을", "추천해줘"]


def test_build_sse_stream_emits_data_events_then_done_event() -> None:
    events = list(build_sse_stream("가장 좋은 덱은"))

    assert events[:-1] == ["data: 가장\n\n", "data: 좋은\n\n", "data: 덱은\n\n"]
    assert events[-1] == "event: done\ndata: [DONE]\n\n"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_chat_message_endpoint_streams_sse_response_in_order(
    client: TestClient,
) -> None:
    session_id = str(uuid.uuid4())

    with client.stream(
        "POST",
        "/api/v1/chat/message",
        json={"session_id": session_id, "message": "가장 좋은 덱은 뭐야"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    assert body == (
        "data: 가장\n\n"
        "data: 좋은\n\n"
        "data: 덱은\n\n"
        "data: 뭐야\n\n"
        "event: done\ndata: [DONE]\n\n"
    )


def test_chat_message_endpoint_closes_stream_after_done_event(
    client: TestClient,
) -> None:
    """done 이벤트 전송 후 제너레이터가 더 이상 청크를 내보내지 않고
    응답 스트림이 정상적으로 끝까지 소진(연결 종료)되는지 확인한다."""
    session_id = str(uuid.uuid4())

    with client.stream(
        "POST",
        "/api/v1/chat/message",
        json={"session_id": session_id, "message": "한 단어"},
    ) as response:
        body = "".join(response.iter_text())

    assert body.endswith("event: done\ndata: [DONE]\n\n")
    assert body.count("event: done") == 1


def test_chat_message_endpoint_invalid_session_id_returns_400(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/chat/message",
        json={"session_id": "not-a-uuid", "message": "안녕"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_session_id"
