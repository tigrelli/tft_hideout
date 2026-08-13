"""TEST-10: Rate Limiting/보안 테스트 — 요청 한도 초과·비정상 입력 처리 검증,
DoD "429 응답 및 로그 확인"(로그는 uvicorn 기본 접근 로그로 충분하다고 PM
확인, 2026-08-13 — 429 응답 자체가 상태코드로 uvicorn 접근 로그에 남으므로
앱 차원의 별도 구조화 로깅 없이 DoD를 충족한다).

API-07 자신의 테스트(test_api07_rate_limit.py)는 이미 catalog/chat 각각의
한도·429 응답을 확인하지만, 전부 `/api/v1/catalog/`·`/api/v1/chat/`
루트(스텁) 경로 하나만 반복 호출한다. 그런데 `middleware/rate_limit.py`의
버킷 키는 `(client_ip, prefix)` — 즉 실제로는 `/api/v1/catalog/*` 아래
모든 엔드포인트가 하나의 버킷을 공유하고, IP별로 버킷이 분리된다는
두 가지 핵심 동작이 정작 한 번도 검증된 적이 없었다. 여기서는 그 두
가지와, TASK 설명이 요구하는 "비정상 입력" 방어(악의적 patch 값이 여러
엔드포인트에서 500 없이 안전하게 처리되는지)를 다룬다.
"""

from fastapi.testclient import TestClient

from main import app

RESOLVE_PATCH_ENDPOINTS = [
    "/api/v1/catalog/tierlist",
    "/api/v1/catalog/items/builds",
    "/api/v1/catalog/augments",
]


# ---- 요청 한도 초과: 실제 서로 다른 엔드포인트가 버킷을 공유하는지 --------------------


def test_rate_limit_bucket_is_shared_across_different_catalog_endpoints() -> None:
    client = TestClient(app)

    # 세 엔드포인트에 20회씩(총 60회) 나눠 호출해도 같은 (IP, "/api/v1/catalog")
    # 버킷을 공유하므로 한도(60)를 채울 때까지는 전부 429가 아니어야 한다.
    for path in RESOLVE_PATCH_ENDPOINTS:
        for _ in range(20):
            response = client.get(path)
            assert response.status_code != 429

    # 61번째 호출은 처음 호출한 적 없는 네 번째 catalog 엔드포인트여도 같은
    # 버킷을 공유하므로 429여야 한다.
    response = client.get("/api/v1/catalog/patches/current")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"


# ---- 요청 한도 초과: IP별로 버킷이 독립적인지 -------------------------------------


def test_rate_limit_buckets_are_isolated_per_client_ip() -> None:
    client_a = TestClient(app, client=("203.0.113.10", 1234))
    client_b = TestClient(app, client=("203.0.113.20", 5678))

    for _ in range(60):
        response = client_a.get("/api/v1/catalog/")
        assert response.status_code != 429
    response = client_a.get("/api/v1/catalog/")
    assert response.status_code == 429

    # client_a가 한도를 소진했어도 다른 IP(client_b)는 영향을 받지 않는다.
    response = client_b.get("/api/v1/catalog/")
    assert response.status_code != 429


# ---- 비정상 입력: 악의적 patch 값이 여러 엔드포인트에서 500 없이 안전하게 처리되는지 ----

MALICIOUS_PATCH_VALUES = [
    "' OR '1'='1",
    "<script>alert(1)</script>",
    "../../etc/passwd",
    "A" * 10_000,
    "17.8\x00",
]


def test_malicious_patch_values_never_cause_500_across_endpoints() -> None:
    client = TestClient(app)
    for path in RESOLVE_PATCH_ENDPOINTS:
        for payload in MALICIOUS_PATCH_VALUES:
            response = client.get(path, params={"patch": payload})
            assert response.status_code != 500, (
                f"{path}?patch={payload!r} -> 500(서버 오류)이면 안 됨"
            )
            assert response.status_code == 400
            assert response.json()["error"]["code"] == "invalid_patch"
