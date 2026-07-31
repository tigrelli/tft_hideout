import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_env_check_true_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    response = client.get("/env-check")
    assert response.status_code == 200
    assert response.json() == {"database_url_set": True}


def test_env_check_false_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    response = client.get("/env-check")
    assert response.status_code == 200
    assert response.json() == {"database_url_set": False}
