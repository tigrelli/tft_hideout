# DATA-22 : 작업결과 (PM 확인 요청 중)

- **TASK**: 조합 통계 필드 확장 수집(top4Rate·표본게임수·시너지 구성)
- **계기**: TEST-11 카테고리 G 논의 중 "op.gg에서 승률/픽률/평균등수 외 더 받을 수 있는 정보가 있는지" PM 문의(2026-08-18) → op.gg MCP `tft_list_meta_decks` 재조사(`docs/spike/opgg-schema.md` 10번 항목)에서 `top4Rate`·`compsCount`(조합별 실제 표본 게임수)·`traits[]`(시너지 구성) 등 미사용 필드 다수 확인.

## 변경 파일

- `backend/db/models.py`: `Comp`에 `top4_rate`(Float, nullable)·`game_count`(Integer, nullable) 컬럼 추가, `CompTrait` 신규 모델(`comp_id`+`trait_id` 복합키, `comp_champions`/`comp_augments`와 동일 패턴).
- `backend/alembic/versions/202608181100_data22_add_comps_top4_rate_game_count_and_comp_traits.py`: 마이그레이션 신규(upgrade/downgrade 모두 구현).
- `batch/normalize.py`: `comp_rows()`에 `top4_rate`/`game_count` 매핑 추가(`deck_stat.get("top4Rate")`/`deck_stat.get("compsCount")`), `upsert_comps()`의 `on_conflict_do_update`에 두 컬럼 반영, `comp_trait_rows(deck)`·`upsert_comp_traits()` 신규(매핑에 없는 특성은 건너뜀, `comp_champions`와 동일 패턴).
- `batch/run_patch_batch.py`: `upsert_traits()` 반환값(`trait_ids`)을 캡처해 `step_normalize()`의 조합별 루프에서 `upsert_comp_traits()` 호출 추가.
- `batch/comps_refresh.py`(DATA-18 주기 재수집 경로): `traits` 테이블에서 `trait_ids_by_riot_id`를 조회(champions와 동일 패턴)해 동일하게 `upsert_comp_traits()` 호출 추가 — 패치 미변경 시 재수집 경로에도 누락 없이 반영됨.
- `batch/tests/test_data10_normalize.py`: `FAKE_DECK` fixture에 `traits[]`·`stat.deck.top4Rate`·`stat.deck.compsCount` 추가, `test_comp_rows_maps_fields_from_deck` 신규 필드 검증 추가, `test_comp_trait_rows_extracts_traits`·`test_upsert_comp_traits_skips_unmapped_trait`·`test_upsert_comp_traits_updates_style_and_num_units_on_conflict` 신규 3건.
- `backend/tests/test_data02_migration.py`: `EXPECTED_TABLES`에 `comps.top4_rate`/`comps.game_count`·`comp_traits` 테이블 반영(기존 컬럼 하드코딩 스팟체크가 신규 컬럼과 충돌해 실패했던 것 수정).

## 왜 `totalCount`가 아니라 `compsCount`인가

op.gg 응답의 `stat.deck.totalCount`는 조합별 표본이 아니라 이번 집계구간 전체 게임수(모든 조합 공통 분모, `pickRate = compsCount/totalCount` 수식으로 검증됨) — `docs/spike/opgg-schema.md` 10번 항목에 이미 정정 기록됨. `game_count` 컬럼은 `compsCount`(조합별 실제 표본)를 매핑한다.

## 자체 검증

- 도커 테스트 DB(`docker-compose.test.yml`)로 재검증: **backend 전체 353/353 통과**(기존 352+신규/수정 반영), **batch 전체 138/138 통과**(기존 130+신규 8건: `comp_trait_rows` 1건, `upsert_comp_traits` DB 통합 2건, `comp_rows` 필드 확장 검증 갱신 등).
- `ruff check .`·`ruff format --check` 전체 클린.
- 마이그레이션 upgrade/downgrade는 TEST-01(`test_test01_migration_integrity.py`)의 전체 체인 재실행 테스트가 자동으로 신규 마이그레이션까지 포함해 검증(별도 파일 추가 불필요, 위 backend 353건에 포함).

## 완료 기준(DoD) 대조

- ✅ `comps.top4_rate`·`comps.game_count`가 op.gg 응답값으로 채워짐(다음 배치 실행부터 반영, 기존 행은 NULL로 유지되다 다음 실행 시 upsert로 채워짐).
- ✅ `comp_traits` 테이블에 조합별 시너지(특성명·단계·유닛수) 목록이 저장됨.
- ✅ 기존 티어리스트/조합상세 API·챗봇 RAG 임베딩에 회귀 없음(테스트로 확인, API/RAG 코드 자체는 이번 TASK에서 변경 안 함 — 노출은 API-16/FE-18 후속 TASK 몫).

## 참고 — DATA-23과의 관계

`docs/spike/comp-tier-scoring.md`에서 이미 확인했듯, `op_score`가 `top4Rate`/`pickRate` 정보를 사실상 대부분 담고 있어(상관계수 0.984) **DATA-23(자체 티어 스코어링)은 이 TASK가 추가한 필드에 의존하지 않는다** — `comps.op_score`는 DATA-23에서 별도 컬럼으로 추가할 예정. 이 TASK의 `top4_rate`/`game_count`/`comp_traits`는 API-16/FE-18(조합 상세 페이지 "표시"용)에서만 쓰인다.
