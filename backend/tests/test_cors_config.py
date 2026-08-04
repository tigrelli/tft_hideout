"""FE-03 착수 중 발견: 브라우저에서 실제로 호출해보기 전까지 CORS 미설정으로
전부 막혀있던 걸 못 보고 있었음(pytest TestClient·curl은 브라우저 CORS 정책을
적용하지 않음). 배포된 프론트엔드 오리진과 로컬 dev 서버가 허용되는지 확인."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_deployed_frontend_origin_is_allowed() -> None:
    response = client.get(
        "/api/v1/catalog/",
        headers={"Origin": "https://tft-hideout.suraholic.workers.dev"},
    )
    assert (
        response.headers["access-control-allow-origin"]
        == "https://tft-hideout.suraholic.workers.dev"
    )


def test_local_dev_origin_is_allowed() -> None:
    response = client.get(
        "/api/v1/catalog/", headers={"Origin": "http://localhost:3000"}
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unknown_origin_is_not_allowed() -> None:
    response = client.get(
        "/api/v1/catalog/", headers={"Origin": "https://evil.example.com"}
    )
    assert "access-control-allow-origin" not in response.headers
