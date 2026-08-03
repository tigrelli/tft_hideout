from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_all_routers_mounted() -> None:
    for prefix in ("/catalog", "/chat", "/analysis", "/kpi"):
        response = client.get(f"{prefix}/")
        assert response.status_code == 200, f"{prefix} 라우터가 마운트되지 않음"
        assert response.json() == {"router": prefix.strip("/")}
