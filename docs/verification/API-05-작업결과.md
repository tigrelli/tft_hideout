# API-05 : 작업결과

- **TASK**: GET /catalog/augments 구현(Legend 승률 비노출)
- **상태**: 완료(PM 승인 2026-08-04)
- **선행 TASK**: DATA-07, API-01
- **근거 문서**: PRD 10-1·설계서 4.4.3, `docs/test-scenarios.md` API-05(TEST-00)
- **변경 파일**: `backend/alembic/versions/202608041700_api05_add_augments_win_rate_column.py`(신규), `backend/db/models.py`(Augment.win_rate 추가), `backend/routers/catalog.py`(엔드포인트 구현), `backend/tests/test_api05_augments.py`(신규), `backend/tests/test_data01_migration.py`(augments 컬럼 목록 갱신)

## 착수 전 발견하고 PM 승인받은 설계 이슈

TEST-00 시나리오·WBS 완료기준이 전제한 "증강체 `win_rate`"가 실제로는 존재하지 않았다:
- `augments` 테이블(DATA-01)에 애초에 `win_rate` 컬럼이 없었음(`comps`/`champion_item_builds`에만 있음)
- op.gg `tft_list_augments` 응답 필드는 `apiName, desc, name, tier, imageUrl` 5개뿐(DATA-05 스파이크로 이미 확인됨) — 증강체 단위 승률 데이터 소스 자체가 없음
- Riot 공식 API도 확인 결과 매치 단위 원본 데이터만 제공하고 집계 통계(승률 등)는 제공하지 않음 — "메타 집계"는 애초에 op.gg 전담으로 설계돼 있어(api-spec.md) Riot API로도 대체 불가
- `comp_augments` 경유 계산도 불가(DATA-10에서 "데이터 소스 없어 제외"로 이미 미구현)

**PM 승인 결정(2026-08-04, DATA-07과 동일한 패턴)**: `augments.win_rate`(nullable) 컬럼만 마이그레이션으로 추가하고 배치는 채우지 않음(항상 NULL) — 마스킹 로직 자체는 TEST-00 시나리오대로 구현하고 합성 데이터로 검증. 나중에 데이터 소스가 생기면 그때 채운다.

## 결과 요약

- **마이그레이션**: `augments`에 `win_rate: float | None` 컬럼 추가(`f1b3c9d4e8a2`, down_revision `c5d8f1a3e6b9`)
- **`GET /api/v1/catalog/augments?patch=&tier=`**: `patch` 미지정 시 현재 패치로 대체(기존 `_resolve_patch()` 재사용), `tier`는 op.gg 실제 값 3종(`gold`/`silver`/`prism`, `docs/spike/legend-augment.md`)만 허용. 응답의 `win_rate`는 `is_legend_related=true`면 **DB에 값이 있어도 무조건 `null`로 강제**(방어적 마스킹 — policies.md 1번 "클라이언트를 신뢰하지 않는다" 원칙)

## 자체 검증

- pytest 7건 신규(TEST-00 시나리오 4건 그대로 + 기본 필터/현재패치 3건), backend 전체 **111/111 통과**, batch 회귀 74/74 통과, ruff check/format 통과
  1. 일반 증강체(`is_legend_related=false`)는 `win_rate` 그대로 노출
  2. Legend 계열(`is_legend_related=true`)은 `win_rate`가 `null`(키 자체는 생략 안 됨, 명시적 `null`)
  3. 같은 목록에 혼재해도 legend 항목만 마스킹, 나머지는 정상 노출
  4. 직렬화된 JSON에서 `win_rate` 필드의 원문 값이 정확히 `null`이고 숫자 패턴이 없는지 확인(정규식 스캔)
  5. `tier` 필터 동작, 잘못된 `tier` 값은 400, `patch` 미지정 시 현재 패치 적용
- `test_data01_migration.py`의 `augments` 기대 컬럼 목록에 `win_rate` 추가(스키마 변경 반영)
