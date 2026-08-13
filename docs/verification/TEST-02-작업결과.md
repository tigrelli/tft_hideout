# TEST-02 : 작업결과

- **TASK**: catalog API 단위/통합 테스트
- **상태**: 완료(PM 승인 2026-08-13)
- **선행 TASK**: API-02, API-03, API-04, API-05, API-06
- **완료 기준(DoD)**: 전체 테스트 통과
- **변경 파일**:
  - `backend/tests/test_test02_catalog_integration.py`(신규)

## 배경 및 범위

API-02~06은 각자 완료 시점에 자기 엔드포인트만 다루는 단위/통합 테스트를 이미 갖고 있다(`test_api02_tierlist.py` 등, 실제 DB(`migrated_engine`)에 TestClient로 요청하는 방식이라 이미 통합 테스트 성격). TEST-01과 같은 이유로 이들과 중복을 피해, **엔드포인트를 가로지르는 관점 3가지**만 새로 다뤘다.

## 구현

`backend/tests/test_test02_catalog_integration.py` 신규 7건:

1. **공유 `_resolve_patch()` 미검증 분기 발견·테스트(파라미터화 3건)** — `routers/catalog.py`의 `_resolve_patch()`는 tierlist(API-02)·item_builds(API-04)·augments(API-05) 3개 엔드포인트가 함께 쓰는 헬퍼인데, "patches 테이블이 완전히 비어 있을 때" `no_current_patch` 404를 내는 분기는 API-06 자신의 엔드포인트(`GET /patches/current`, 이건 별도 inline 체크라 다른 코드 경로)의 테스트에서만 검증돼 있었다. 정작 이 헬퍼를 호출하는 3개 엔드포인트 자신의 테스트 파일은 전부 최소 1개 패치를 미리 시드하고 시작해서, 이 분기 자체가 3개 엔드포인트 기준으로는 한 번도 실행된 적이 없었다. 이번에 `test_no_current_patch_returns_404_across_resolve_patch_endpoints`로 3개 엔드포인트 각각 검증.
2. **invalid_patch(400) 에러 포맷 일관성(파라미터화 3건)** — 동일 3개 엔드포인트가 `patch=not-a-patch`일 때 모두 동일한 `{"error": {"code": "invalid_patch", "message": ...}}` 형태를 반환하는지 확인.
3. **5개 엔드포인트 통합 스모크(1건)** — 패치·챔피언·아이템·증강체·조합(+comp_champions/comp_augments/champion_item_builds)을 하나의 공유 시드로 구성해 tierlist → comp_detail → item_builds → augments → patches/current 순서로 실제 서비스 흐름을 재현, 응답의 `patch_version`/연관 ID가 서로 일관되는지(예: augments 응답의 `related_comp_ids`가 시드한 comp_id와 일치) 확인.

## 자체 검증

- 신규 7건 전체 통과, 회귀 없음: `backend` 전체 pytest **311/311** 통과(TEST-01 이후 304 + 신규 7).
- 첫 실행에 7건 모두 통과 — 발견한 "미검증 분기"는 버그가 아니라 테스트 공백이었음(구현 자체는 정상 동작).
- `ruff check` / `ruff format` 통과.
- Docker(`docker-compose.test.yml`) test-db(5433)로 로컬에서 직접 실행.

## PM 확인 결과

2026-08-13 PM 승인.
