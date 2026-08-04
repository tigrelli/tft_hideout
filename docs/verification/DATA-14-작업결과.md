# DATA-14 : 작업결과

- **TASK**: 배치 동시 실행 방지 구현
- **상태**: 완료(PM 승인 2026-08-04)
- **선행 TASK**: DATA-12
- **근거 문서**: 설계서 4.3
- **변경 파일**: `.github/workflows/patch-detection.yml`(신규), `batch/run_patch_batch.py`(신규 — DATA-12~13 배선), `batch/README.md`, `backend/db/session.py`·`batch/db_session.py`(DB URL 드라이버 보정, 검증 중 발견), `backend/alembic/env.py`(위 보정 재사용, 검증 중 발견), `render.yaml`(alembic 자동 적용, 검증 중 발견 — 단 Render Build Command는 대시보드에서 별도 수동 반영 필요했음, 아래 참고)

## 착수 전 확인 — 실제 운영 자동화라 PM 확인 먼저 받음

concurrency 그룹은 "돌아가는 워크플로우"에 붙는 설정이라, 이 TASK를 검증하려면 DATA-08~13을 잇는 진입점(`run_patch_batch.py`)과 실제 GitHub Actions 워크플로우가 있어야 한다. 그런데 이 워크플로우가 살아있으면 **실제 운영 Supabase DB에 매시간 자동으로 쓰기 작업**이 발생하므로, 착수 전 PM 확인을 받았다: **워크플로우는 만들되 `schedule` 트리거는 아직 켜지 않고 `workflow_dispatch`(수동 실행)만 활성화**하기로 결정(2026-08-04).

## 결과 요약

- **`batch/run_patch_batch.py`**: DATA-12(`run_patch_detection`)로 패치 변경을 감지하고, 변경 시 콜백에서 DATA-08(op.gg)·DATA-09(Community Dragon) 수집 → DATA-10 정규화 → DATA-11 임베딩을 `BatchStep`으로 묶어 DATA-13(`run_batch_with_atomic_promotion`)에 넘긴다. 무료 티어 한도를 고려해 임베딩은 실행당 최대 `MAX_EMBED_CHUNKS_PER_RUN`(기본 500)개까지만 처리 — upsert가 멱등적이라 다음 실행에서 이어서 처리해도 안전(DATA-11 설계)
- **`.github/workflows/patch-detection.yml`**: `concurrency: {group: patch-detection, cancel-in-progress: false}` — 이미 실행 중인 배치가 있으면 새 트리거는 **취소하지 않고 대기열에서 기다렸다가 실행**(CI의 `cancel-in-progress: true`와 반대 방향 선택 — 배치 도중 취소하면 부분 적재 상태가 애매해질 수 있어 순차 실행이 안전). `on: workflow_dispatch`만 활성화, `schedule` 블록은 주석 처리
- **필요 시크릿**: `DATABASE_URL`은 SET-09에서 이미 등록 확인됨. **`HUGGINGFACE_API_KEY`는 GitHub Actions 저장소 시크릿으로 등록됐는지 확인되지 않음**(smoke-tests.md엔 `DATABASE_URL` 등록만 기록돼 있음) — PM 확인/등록 필요, 없으면 워크플로우 실행 시 임베딩 단계에서 실패함

## 자체 검증

- pytest 66/66 통과(기존과 동일 — 이번 TASK는 신규 pytest 대상 로직 없음, glue 코드라 DATA-08~13에서 이미 검증된 함수만 조립)
- `ruff check`/`ruff format --check` 통과
- **로컬 테스트 DB로 `run_patch_batch.py` 실제 실행 확인**: 감지 → 트리거 → 수집·정규화·임베딩(15개 chunk로 상한 테스트) → 원자적 승격까지 전부 성공(`is_current` 정확히 전환, `patch_detection_runs`에 `triggered`+`success` 2건 기록)
- **concurrency 자체(GH Actions 동시 실행 방지)는 GitHub 서버 쪽 기능이라 로컬/pytest로 검증 불가** — 워크플로우가 main에 머지된 뒤 PM이 GitHub UI에서 `workflow_dispatch`를 짧은 간격으로 2번 트리거해, 두 번째 실행이 "Queued"(대기)로 표시되고 첫 번째가 끝난 뒤 시작되는지 직접 확인해야 한다(SET-08/SET-13처럼 사람이 하는 스모크 테스트 — WBS 테스트 요구사항도 "pytest:"가 아니라 "동시성 테스트"로 별도 표기돼 있어 이 방식이 맞음)

## PM 확인/조치 필요 → 2026-08-04 검증 완료

1. ~~`HUGGINGFACE_API_KEY`(및 필요 시 `GROQ_API_KEY`)가 GitHub Actions 저장소 시크릿으로 등록돼 있는지 확인~~ → **확인 완료**: `gh secret list`로 `DATABASE_URL`(2026-07-31 등록), `HUGGINGFACE_API_KEY`(2026-08-04 등록) 둘 다 존재 확인. `GROQ_API_KEY`는 이 워크플로우의 env에 애초에 필요 없음(patch-detection은 Groq를 쓰지 않음, CHAT-05에서만 필요).
2. ~~main 머지 후 `workflow_dispatch`를 짧은 간격으로 2번 트리거해 동시 실행 방지(대기열) 동작 직접 확인~~ → **확인 완료**: 06:58:48/06:58:55(UTC) 7초 간격으로 2회 트리거(run 30885970214, 30885977450). 로그 타임스탬프 대조 결과 두 번째 실행의 실제 스텝은 첫 번째가 끝난 뒤(06:59:15 이후)에 시작 → `cancel-in-progress: false`대로 취소 없이 순차 대기·실행됨을 확인. **DATA-14 핵심 목적(동시 실행 방지) 검증 완료.**
3. **`schedule` 트리거 활성화 완료(2026-08-04, PM 승인)**: 매시간(PRD 9-1 원안) 대신 **1일 1회(매일 03:00 KST = `cron: "0 18 * * *"`)**로 결정. TFT 패치는 월 1~2회뿐이라 매시간 감지는 GitHub Actions 무료 분(2,000분/월, CI와 공유)의 약 36%(720분/월)를 소모하는 반면 1일 1회는 약 1.5%(30분/월)만 소모 — 개인/지인 10명 규모 MVP에서 매시간 감지의 이점(최대 1시간 지연)이 예산 절감(CI에 배정 가능한 여유 확보)보다 크지 않다고 판단. 패치 발생 후 최대 24시간 지연은 `workflow_dispatch` 수동 트리거(이미 동작 확인됨)로 즉시 만회 가능.

## 검증 중 발견하고 해결한 프로덕션 이슈 3건 (2026-08-04)

위 2번 트리거 검증 중 두 실행 모두 `psycopg.errors.UndefinedTable: relation "patches" does not exist`로 실패 — DATA-14 로직 자체가 아니라 **운영 인프라 쪽 문제**였다. 원인 3단계를 순서대로 발견·해결:

1. **Render 빌드에 마이그레이션 단계가 아예 없었음**: `render.yaml`의 `buildCommand`가 `pip install`만 하고 `alembic upgrade head`가 없어서, 운영 Supabase DB에 스키마(patches 등 테이블)가 SET-06 이후 한 번도 생성된 적이 없었다(별도 커밋 `ed3f1e3`로 `render.yaml`에 alembic 단계 추가 — 단, 아래 2번 이슈로 이 커밋만으로는 실제 반영되지 않았음).
2. **`render.yaml` 수정이 Render 서비스에 반영되지 않음**: (a) Render 서비스의 Root Directory가 `backend`로 설정돼 있어 저장소 **루트**의 `render.yaml` 변경은 auto-deploy 트리거 대상이 아니었고, (b) Blueprint(`render.yaml`)로 생성된 서비스는 파일이 바뀌어도 서비스의 실제 Build Command가 자동 동기화되지 않는다(수동 Sync 필요). PM이 Render 대시보드 Settings → Build에서 Build Command를 직접 `pip install -r requirements.txt && alembic upgrade head`로 수정해 해결.
3. **`alembic/env.py`가 DB URL 드라이버 보정을 안 탐**: 위 2번 해결 후 재배포했더니 `ModuleNotFoundError: No module named 'psycopg2'`로 빌드 실패. `f5f9b49`(별도 커밋)에서 `db/session.py`·`batch/db_session.py`의 `get_database_url()`에 `postgres://`/`postgresql://` → `postgresql+psycopg://` 자동 보정을 추가했는데, `alembic/env.py`는 `os.getenv("DATABASE_URL")`을 직접 써서 그 보정을 거치지 않고 있었다. `get_database_url()`을 재사용하도록 수정(커밋 `227178c`), pytest 104/104 통과 확인 후 main에 push.

**최종 결과**: push 직후 Render 재배포(Root Directory 안쪽 변경이라 이번엔 정상 auto-deploy) → `GET /api/v1/catalog/patches/current`가 500(`relation does not exist`) → 404(`no_current_patch`, 스키마는 생겼지만 아직 데이터 없음)로 바뀜을 확인 → 이어서 `workflow_dispatch` 재트리거(run 30886830574)가 **처음으로 전체 배치 성공**(`success=True failed_step=None`, 패치 감지 `None -> 17.8`) → `GET /api/v1/catalog/patches/current`가 실제 데이터로 200 응답(`{"version":"17.8","set_number":17,...}`)까지 확인. **운영 Supabase DB에 스키마와 실데이터가 이번에 처음으로 실제 생성됨.**

## 다음 세션을 위한 메모

- `run_patch_batch.py`가 실제로 production DB에 처음 쓰기를 성공한 시점은 2026-08-04 16:13 KST(patch 17.8). `schedule`을 켜기 전에 KPI-01의 "데이터 최신성" 지표가 `patch_detection_runs`를 근거로 계산되므로, 실제 자동 실행이 시작되면 KPI 대시보드에도 값이 잡히기 시작할 것 — REL-03(배포 후 모니터링) 체크리스트에 참고.
- **Render Blueprint(`render.yaml`) 운영 시 주의사항(신규 발견, 향후 배포 설정 변경 시 재발 방지용)**: (1) Root Directory가 설정된 서비스는 그 경로 밖의 파일(`render.yaml` 등 저장소 루트 파일) 변경이 auto-deploy를 트리거하지 않는다. (2) Blueprint로 생성한 서비스는 `render.yaml` 변경이 있어도 buildCommand 등 서비스 설정이 자동 동기화되지 않으며, Render 대시보드에서 수동으로 Sync하거나 직접 Settings를 고쳐야 실제로 반영된다. SET-06 작업결과 문서에도 이 내용 추가 필요(다음 세션 또는 REL-03에서 반영).
