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

## 운영 반영 완료 (2026-08-06, PM 승인 후 실행)

- PR #16 머지(4f2d617) → Render/Cloudflare 자동 배포 → Render 빌드 커맨드(`alembic upgrade head`)로 운영 DB에 `is_active` 컬럼 자동 추가, 기존 행은 전부 `is_active=true`로 시작.
- **`patch-detection.yml`을 `workflow_dispatch`로 수동 트리거했으나(Run #9, 28초, Success) 실제로는 아무 것도 갱신되지 않음을 운영 API 재확인으로 발견** — `run_patch_detection()`이 `현재 DB 패치버전 != op.gg 최신 버전`일 때만 수집을 실행하는데 둘 다 17.8이라 `triggered=False`로 스킵됨(FE-05 때 겪은 것과 동일한 구조적 공백, 성공 표시는 뜨지만 무동작).
- 패치 감지·승격 로직은 건드리지 않고 이미 검증된 `upsert_comps`/`mark_stale_comps_inactive`/`upsert_comp_champions`만 재사용하는 1회성 스크립트(레포 미커밋, `batch/_data17_prod_backfill.py`, 실행 후 삭제)를 PM 승인 하에 운영 DB에 직접 실행.
- **결과**: op.gg 10개 조합 upsert, 1건 비활성화(운명술사 트위스티드 페이트, `riot_comp_id=3d430c9c...`). 운영 API로 최종 확인:
  - `GET /catalog/tierlist`: 운명술사 트위스티드 페이트 제외, N.O.V.A. 미스 포츈 등 신규 메타 조합 반영.
  - `GET /catalog/comps/9`(운명술사 트위스티드 페이트): 200 정상 응답, 8명 챔피언 그대로 조회 가능(소프트 삭제 의도대로 상세 링크 보존).
  - `GET /catalog/comps/10`(N.O.V.A. 벡스): 9명 전원 실좌표(`cell_x`1~7·`cell_y`1~4)·`star_level`(2) 정상 반영 — 프론트 헥스 배치도가 휴리스틱에서 실좌표 모드로 전환됨.
- **후속 논의 필요(별도 TASK 미등록)**: `patch-detection.yml`이 같은 patch_version 내 데이터 갱신(이번처럼 신규 컬럼 추가·메타 회전 반영)엔 반응하지 않는 구조적 공백이 FE-05·DATA-17 두 번 재현됨 — 재발 방지책(예: 주기적 무조건 재수집, 또는 수동 백필 스크립트를 정식 관리 스크립트로 승격)을 PM이 판단해 필요 시 신규 TASK로 등록할 것.
