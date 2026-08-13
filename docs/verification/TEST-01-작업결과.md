# TEST-01 : 작업결과

- **TASK**: DB 스키마/마이그레이션 검증
- **상태**: 완료(PM 승인 2026-08-13)
- **선행 TASK**: DATA-01, DATA-02, DATA-03, DATA-04
- **완료 기준(DoD)**: 마이그레이션 재실행 무결성 확인
- **변경 파일**:
  - `backend/tests/test_test01_migration_integrity.py`(신규)

## 배경 및 범위

DATA-01~04는 각자 완료 시점에 자신이 추가한 테이블·컬럼만 스팟체크하는 `test_dataNN_migration.py`를 이미 갖고 있다(테이블 존재/컬럼 일치/FK·UNIQUE 제약/JSONB 타입/HNSW 인덱스 등). TEST-01의 테스트 요구사항("해당 TASK 자체가 테스트 작성/실행 TASK의 산출물")과 DoD("마이그레이션 재실행 무결성 확인")는 이들과 다른 축 — 개별 테이블이 아니라 **현재 18개 전체 마이그레이션 체인이 재실행 가능한지**를 검증하는 것이라 판단해, 기존 4개 파일과 중복 없이 새 테스트 파일 하나를 추가했다.

## 구현

`backend/tests/test_test01_migration_integrity.py` 신규 3건:

1. `test_downgrade_base_then_upgrade_head_reproduces_identical_schema` — `alembic upgrade head` → 스키마 스냅샷(테이블·컬럼) 저장 → `alembic downgrade base` → 다시 `upgrade head` → 스냅샷이 처음과 동일한지 확인. 18개 마이그레이션 각각의 `downgrade()`가 실제로 자신의 `upgrade()`를 정확히 역전시키는지 검증(개별 TASK 테스트는 `upgrade head`만 호출해 처음부터 한 번도 실행된 적 없는 경로).
2. `test_downgrade_base_removes_all_application_tables` — `downgrade base` 이후 `alembic_version`을 제외한 모든 애플리케이션 테이블이 남김없이 제거됐는지 확인(일부 downgrade가 누락돼 고아 테이블이 남는 경우를 잡기 위함).
3. `test_upgrade_head_when_already_at_head_is_idempotent` — 이미 head인 상태에서 `upgrade head`를 다시 호출해도 에러 없이 스키마가 그대로인지 확인(배치·배포 스크립트가 실수로 두 번 호출해도 안전한지).

`migrated_engine`(기존 conftest fixture)을 그대로 쓰지 않고 별도 `fresh_engine` fixture를 둔 이유: `migrated_engine`은 매번 스키마를 초기화한 뒤 `upgrade head`까지 끝낸 상태를 반환하지만, 이 테스트들은 그 이후 시점에 `downgrade`/재-`upgrade`를 직접 호출해야 해서 `Config` 객체를 테스트 내부에서 다뤄야 했다.

## 자체 검증

- 신규 3건 전체 통과, 회귀 없음: `backend` 전체 pytest **304/304** 통과(기존 301 + 신규 3).
- 첫 실행에서 바로 3건 모두 통과 — 18개 마이그레이션의 `downgrade()`가 전부 정확히 구현돼 있어 재실행 무결성에 문제가 없음을 확인(버그 발견 없음, 검증 자체가 목적인 TASK라 정상적인 결과).
- `ruff check` / `ruff format --check` 통과.
- Docker(`docker-compose.test.yml`)로 로컬 test-db(5433)를 직접 기동해 실행(이전 세션들이 "로컬 도커 미설치"로 못 했던 것과 달리 이번 세션 환경에는 docker 설치돼 있어 로컬에서 바로 실행 가능했음).

## PM 확인 결과

2026-08-13 PM 승인.
