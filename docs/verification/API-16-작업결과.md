# API-16 : 작업결과 (PM 확인 요청 중)

- **TASK**: 조합 API 응답에 top4Rate·표본게임수·시너지 구성 노출
- **계기**: DATA-22가 채운 `comps.top4_rate`·`comps.game_count`·`comp_traits`를 API 응답에 노출.

## 변경 파일

- `backend/routers/catalog.py`:
  - `TraitInComp` 신규 Pydantic 모델(`trait_id`·`name_kr`·`name_en`·`style`·`num_units`).
  - `CompSummary`(티어리스트)·`CompDetailResponse`(조합 상세) 둘 다에 `top4_rate`·`game_count`·`traits` 필드 추가(WBS DoD가 두 엔드포인트 모두를 명시).
  - `_fetch_traits_for_comp()` 신규 헬퍼(comp_id로 `comp_traits`+`traits` 조인 조회, style 내림차순 정렬) — `get_tierlist()`·`get_comp_detail()` 양쪽에서 재사용.
- `backend/tests/test_api02_tierlist.py`: `top4_rate`/`game_count` NULL·값 있는 경우, `traits` 빈 리스트·값 있는 경우 각 2건씩 신규 4건.
- `backend/tests/test_api03_comp_detail.py`: 동일 패턴으로 조합 상세 엔드포인트에 신규 2건(NULL 케이스, 값 있는 케이스 — 한 테스트에서 top4_rate/game_count/traits 셋 다 함께 검증).

## 설계 결정

WBS DoD가 "티어리스트/조합상세 API 응답에 top4_rate·game_count·시너지 구성(traits) 목록이 포함됨"이라고 명시해 두 엔드포인트 모두에 반영했다. FE-18(조합 상세 페이지 표시)은 조합 상세 화면만 대상이지만, 티어리스트 응답에도 미리 포함해두면 추후 티어리스트 카드에도 같은 정보를 노출하고 싶을 때 API 변경 없이 바로 가능하다.

## 자체 검증

- 도커 테스트 DB로 재검증: **backend 전체 359/359 통과**(기존 353+신규 6), **batch 전체 139/139 통과**(무회귀).
- `ruff check .`·`ruff format --check` 전체 클린.
- 기존 API-02/API-03 테스트 전체 무회귀(carry_champions·champions·augments 등 기존 필드 동작 그대로 유지).

## 완료 기준(DoD) 대조

- ✅ 티어리스트/조합상세 API 응답에 `top4_rate`·`game_count`·`traits` 목록 포함.
- ✅ 기존 응답 필드에 회귀 없음(pytest로 확인).
