from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_catalog_allows_up_to_60_requests_per_minute() -> None:
    for _ in range(60):
        response = client.get("/api/v1/catalog/")
        assert response.status_code == 200

    response = client.get("/api/v1/catalog/")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"


def test_chat_allows_up_to_10_requests_per_minute() -> None:
    for _ in range(10):
        response = client.get("/api/v1/chat/")
        assert response.status_code == 200

    response = client.get("/api/v1/chat/")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"


def test_rate_limit_does_not_apply_outside_catalog_and_chat() -> None:
    for _ in range(70):
        response = client.get("/health")
        assert response.status_code == 200
