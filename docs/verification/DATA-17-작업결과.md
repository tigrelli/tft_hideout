# DATA-17 : 작업결과

- **TASK**: 메타 조합 소프트 삭제(비활성화) 로직 구현
- **상태**: 자체검증 완료, PM 확인 대기
- **선행 TASK**: DATA-08
- **근거 문서**: `docs/spike/opgg-schema.md`(7·8번), 진행현황.md 2026-08-06 "DATA-17 신규 등록·착수" 항목
- **변경 파일**: `backend/alembic/versions/202608061700_data17_add_comps_is_active_column.py`(신규), `backend/db/models.py`(`Comp.is_active`), `backend/routers/catalog.py`(`get_tierlist` 필터), `batch/normalize.py`(`upsert_comps` on_conflict에 재활성화 반영, `mark_stale_comps_inactive` 신규), `batch/run_patch_batch.py`(정리 로직 배선), `backend/tests/test_data02_migration.py`·`backend/tests/test_api02_tierlist.py`·`backend/tests/test_api03_comp_detail.py`·`batch/tests/test_data10_normalize.py`(pytest 신규)

## 문제 재확인

PM 요청으로 N.O.V.A. 벡스·운명술사 트위스티드 페이트 두 조합의 좌표 누락 원인을 op.gg부터 재조사한 결과:
- 두 조합 모두 챔피언 전원의 `cell_x/cell_y`가 null인 원인은 파싱 버그가 아니라 컬럼·추출 코드 자체가 두 조합의 마지막 적재 시점(2026-08-04) 이후인 2026-08-06에야 추가됐기 때문.
- N.O.V.A. 벡스는 op.gg 상위 10위에 여전히 있어 재배치 시 정상 백필 가능.
- **운명술사 트위스티드 페이트는 op.gg 상위 10위 목록에서 이미 빠짐** — `tft_list_meta_decks`는 페이지네이션 없이 항상 정확히 현재 상위 10개만 반환해(opgg-schema.md 8번), 메타가 회전하면 같은 patch_version 내에서도 예전 상위권 조합이 이번 응답에 없을 수 있다.
- 조사 중 `normalize.py`의 `upsert_comps`/`upsert_comp_champions`가 순수 upsert라 상위 10위에서 빠진 조합을 지우는 로직이 전혀 없어, 이런 조합이 좌표 등 신규 필드를 영영 채우지 못한 채 `comps` 테이블에 영구히 남는 구조적 공백을 추가로 확인.

## PM 결정 (2026-08-06)

1. **하드 삭제 대신 `comps.is_active` 플래그로 소프트 삭제.** `comp_champions`/`comp_augments`(comp_id FK)·`match_analyses.matched_comp_id`(nullable FK)·`meta_document_embeddings`(`source_table='comps'` 참조)가 있어 하드 삭제 시 FK 위반 또는 PGA 사후 패인 분석·챗봇 RAG 인용 참조가 끊길 위험이 있음.
2. 신규 TASK로 즉시 등록해 진행(`DATA-17`, 권장, 선행TASK DATA-08).

## 구현

- **마이그레이션**: `comps.is_active BOOLEAN NOT NULL DEFAULT true` 추가(기존 행은 전부 `true`로 채워짐).
- **`normalize.upsert_comps()`**: `ON CONFLICT DO UPDATE`의 `set_`에 `is_active: True`를 추가 — 이전 배치에서 비활성화됐던 조합이 다시 op.gg 상위 10위에 나타나면 자동 재활성화된다.
- **`normalize.mark_stale_comps_inactive(session, patch_version, active_riot_comp_ids)`** 신규: 같은 `patch_version` 내에서 `is_active=true`인데 이번 배치의 `active_riot_comp_ids`(이번 op.gg 응답으로 upsert한 riot_comp_id 전체)에 없는 행만 `is_active=false`로 전환. 다른 `patch_version` 행은 절대 건드리지 않는다(정합성 원칙 유지).
- **`run_patch_batch.py`**: `step_normalize()`에서 `upsert_comps()` 직후 `mark_stale_comps_inactive(session, patch_version, set(comp_ids.keys()))` 호출.
- **`GET /catalog/tierlist`**: `Comp.is_active.is_(True)` 조건 추가 — 비활성 조합은 티어리스트에서 사라진다.
- **`GET /catalog/comps/{comp_id}`**: 의도적으로 변경하지 않음 — 비활성 조합도 상세 조회는 그대로 가능(기존 링크·PGA 매칭·챗봇 인용 보존).

## 자체 검증

- **batch pytest 4건 신규**(`upsert_comps`가 신규 행을 `is_active=True`로 채우는지 / `mark_stale_comps_inactive`가 이번 배치에 없는 조합만 비활성화하는지 / 다른 patch_version 행은 건드리지 않는지 / 재등장 시 재활성화되는지) — **전체 87/87 통과**, ruff check/format 통과.
- **backend pytest 3건 신규**(`test_data02_migration.py`에 `is_active` 컬럼 존재 확인 추가, `test_api02_tierlist.py`에 비활성 조합이 티어리스트에서 제외되는지, `test_api03_comp_detail.py`에 비활성 조합도 상세 조회는 200으로 응답하는지) — **전체 202/202 통과**, ruff check/format 통과.
- 마이그레이션을 로컬 테스트 DB(`docker-compose.test.yml`)에 실제로 적용해 `alembic upgrade head` 성공 확인.

## 운영 반영 관련 참고 (착수 전 PM 확인 필요)

- 배포 후 Render 빌드 커맨드가 `alembic upgrade head`를 자동 실행하므로(DATA-14 이력 참고) 별도 백필 스크립트 없이 컬럼만 추가되면 기존 운영 `comps` 행은 전부 `is_active=true`로 시작한다.
- **비활성화 자체는 다음 배치 실행(`workflow_dispatch` 수동 트리거 또는 매일 03:00 KST 정기 실행)이 한 번 돌아야 반영된다** — 이번 커밋만으로는 운영 DB의 기존 상태(예: 운명술사 트위스티드 페이트)가 즉시 바뀌지 않는다.
- 이번 세션에서 재확인한 대로 운명술사 트위스티드 페이트는 이미 op.gg 상위 10위 밖이라, 다음 배치가 돌면 자동으로 `is_active=false`가 되어 티어리스트에서 사라질 것으로 예상됨 — PM이 원하는 동작인지 최종 확인 필요.
