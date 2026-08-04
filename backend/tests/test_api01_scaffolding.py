from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_all_routers_mounted() -> None:
    for name in ("catalog", "chat", "analysis", "kpi"):
        response = client.get(f"/api/v1/{name}/")
        assert response.status_code == 200, f"{name} 라우터가 마운트되지 않음"
        assert response.json() == {"router": name}
