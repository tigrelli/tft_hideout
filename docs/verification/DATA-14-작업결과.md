# DATA-14 : 작업결과

- **TASK**: 배치 동시 실행 방지 구현
- **상태**: 완료(PM 확인 요청 중)
- **선행 TASK**: DATA-12
- **근거 문서**: 설계서 4.3
- **변경 파일**: `.github/workflows/patch-detection.yml`(신규), `batch/run_patch_batch.py`(신규 — DATA-12~13 배선), `batch/README.md`

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

## PM 확인/조치 필요

1. `HUGGINGFACE_API_KEY`(및 필요 시 `GROQ_API_KEY`)가 GitHub Actions 저장소 시크릿으로 등록돼 있는지 확인 — 없으면 등록
2. main 머지 후 `workflow_dispatch`를 짧은 간격으로 2번 트리거해 동시 실행 방지(대기열) 동작 직접 확인
3. 위 확인이 끝나면 `schedule` 트리거를 켤지(PRD 9-1 설계대로 매시간 자동 실행 시작) 별도로 결정

## 다음 세션을 위한 메모

`run_patch_batch.py`가 실제로 production DB에 처음 쓰기 시작하는 지점이다. `schedule`을 켜기 전에 KPI-01의 "데이터 최신성" 지표가 `patch_detection_runs`를 근거로 계산되므로, 실제 자동 실행이 시작되면 KPI 대시보드에도 값이 잡히기 시작할 것 — REL-03(배포 후 모니터링) 체크리스트에 참고.
