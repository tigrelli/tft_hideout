# TEST-10 : 작업결과

- **TASK**: Rate Limiting/보안 테스트
- **상태**: 완료(PM 승인 2026-08-13)
- **선행 TASK**: API-07
- **근거 문서**: 개발설계서 4.2·6장
- **완료 기준(DoD)**: 429 응답 및 로그 확인
- **변경 파일**:
  - `backend/tests/test_test10_rate_limit_security.py`(신규)

## 배경 및 범위

API-07 자신의 테스트(`test_api07_rate_limit.py`)는 이미 catalog(분당 60)·chat(분당 10) 각각의 한도·429 응답을 확인하지만, 전부 `/api/v1/catalog/`·`/api/v1/chat/` 루트(스텁) 경로 하나만 반복 호출한다. `middleware/rate_limit.py`의 버킷 키가 `(client_ip, prefix)`라 실제로는 `/api/v1/catalog/*` 아래 모든 엔드포인트가 하나의 버킷을 공유하고 IP별로 버킷이 분리되는데, 이 두 핵심 동작은 검증된 적이 없었다. TASK 설명이 요구하는 "비정상 입력 처리"도 함께 다뤘다(악의적 patch 값이 여러 엔드포인트에서 500 없이 안전하게 처리되는지).

## "로그 확인" 처리 방침(PM 확인, 2026-08-13)

DoD에 "로그 확인"이 명시돼 있으나, 현재 백엔드 전체에 앱 차원의 구조화 로깅이 아직 구현돼 있지 않다(CLAUDE.md 10.1에 요구사항만 있고 실제 도입은 안 됨). 착수 전 PM에게 (1) uvicorn 기본 접근 로그로 충분(권장) (2) 미들웨어에 구조화 로그를 새로 추가 두 가지 방향을 확인 요청 → **(1) uvicorn 기본 로그로 충분**하다는 결정. 429 응답 자체가 상태코드로 uvicorn 접근 로그에 자동으로 남으므로, 이 TASK 범위에서 별도 로깅 코드를 추가하지 않았다(TEST-* TASK가 새 기능을 추가하지 않는다는 워크플로우 원칙과도 부합).

## 구현

`backend/tests/test_test10_rate_limit_security.py` 신규 3건:

1. `test_rate_limit_bucket_is_shared_across_different_catalog_endpoints` — tierlist/item_builds/augments 3개 서로 다른 실제 엔드포인트에 20회씩(총 60회) 나눠 호출해도 하나의 버킷을 공유해 한도 안에서는 429가 안 나고, 61번째 호출(네 번째 엔드포인트인 patches/current)이 즉시 429가 되는지 확인.
2. `test_rate_limit_buckets_are_isolated_per_client_ip` — 서로 다른 client IP로 만든 두 `TestClient`가 독립된 버킷을 갖는지 확인(한쪽이 60회를 소진해 429를 받아도 다른 IP는 영향 없음).
3. `test_malicious_patch_values_never_cause_500_across_endpoints` — SQL 인젝션 스타일 문자열·XSS 스크립트 태그·경로 순회 문자열·10,000자 초과 입력·널바이트 포함 문자열 5종을 `_resolve_patch()`를 공유하는 3개 엔드포인트 각각에 흘려, 전부 500 없이 기존 `invalid_patch` 400 검증에 걸리는지 확인.

## 자체 검증

- 신규 3건 전체 통과, 회귀 없음: `backend` 전체 pytest **325/325** 통과(TEST-06 이후 322 + 신규 3).
- 첫 실행에 3건 모두 통과 — 버킷 공유/IP 격리 동작과 비정상 입력 방어 모두 설계대로 동작함을 확인(버그 없음).
- `ruff check` / `ruff format` 통과.
- Docker(`docker-compose.test.yml`) test-db(5433)로 로컬에서 직접 실행.

## PM 확인 결과

2026-08-13 PM 승인.
