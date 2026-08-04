# DATA-13 : 작업결과

- **TASK**: 원자적 패치 전환 트랜잭션 구현
- **상태**: 완료(PM 확인 요청 중)
- **선행 TASK**: DATA-10, DATA-11
- **근거 문서**: PRD 12장
- **사전 시나리오**: `/docs/test-scenarios.md` DATA-13(TEST-00, PM 합의됨) — 5개 케이스 그대로 pytest로 옮김
- **변경 파일**: `batch/patch_transition.py`(신규), `batch/tests/test_data13_patch_transition.py`(신규)

## 결과 요약

- **`promote_patch_to_current(session, new_version)`**: 단일 트랜잭션으로 이전 `is_current` 행을 `false`로, 새 버전을 `true`로 전환. `session.commit()` 전까지는 다른 커넥션에 이전 값이 그대로 보임(Postgres READ COMMITTED 기본 격리 수준으로 보장)
- **`run_batch_with_atomic_promotion(session, new_version, steps)`**: `BatchStep` 목록을 순서대로 실행하다 하나라도 예외가 나면 즉시 중단하고 **이후 단계와 승격을 모두 건너뜀** — 그래서 `is_current`는 자연스럽게 이전 값으로 남는다(별도 "롤백" 로직 불필요, 애초에 승격을 안 하면 그만). 앞 단계가 이미 DB에 커밋한 부분 적재 데이터(예: 새 patch_version 태그가 붙은 champions 행)는 그대로 남는다 — `is_current`가 안 가리키므로 API·챗봇에는 노출 안 됨
- 예외를 위로 전파하지 않고 성공/실패 여부를 `BatchRunResult`로 반환 + `patch_detection_runs`에 `status="success"/"failed"`로 기록(TEST-00 #5) — 크론이 죽지 않고 다음 시간에 재시도 가능
- DATA-08(op.gg)·DATA-09(Community Dragon)·DATA-10(정규화)·DATA-11(임베딩)을 `BatchStep`으로 감싸 이 함수에 넘기면 전체 배치가 완성된다(실제로 스모크 테스트에서 그렇게 조립해 확인 — 아래 참고)

## TEST-00 5개 시나리오 → pytest 매핑

| # | 시나리오 | 테스트 |
|---|---|---|
| 1 | 전체 성공 시 전환 | `test_all_steps_succeed_promotes_new_patch` |
| 2 | 6개 중 4번째 실패 시 이전 패치 유지 | `test_failure_on_fourth_of_six_steps_keeps_previous_patch` |
| 3 | 마지막(임베딩) 단계 실패해도 전환 안 됨(부분 적재 확인 포함) | `test_failure_on_last_step_still_keeps_previous_patch` |
| 4 | 전환 도중 동시 조회 — 커밋 전/후 다른 커넥션이 보는 값 | `test_concurrent_read_sees_old_patch_until_commit` |
| 5 | 성공/실패 모두 `patch_detection_runs`에 기록 | `test_success_and_failure_both_recorded_in_patch_detection_runs` |

## 자체 검증

- pytest 66/66 통과(기존 60 + 신규 6, TEST-00 5개 시나리오 전부 포함)
- `ruff check`/`ruff format --check` 통과(pre-commit 고정 버전 기준)
- backend 영향 없음(스키마 변경 없이 기존 `patches`/`patch_detection_runs` 테이블만 사용)
- **WBS DoD("중간 실패 시나리오에서 이전 패치 유지 확인") + 통합 검증**: pytest로 트랜잭션 격리 수준까지 정확히 검증했고, 추가로 **DATA-08~13 전체를 실제로 연결해 한 번에 실행**했다 — Community Dragon+op.gg 실호출 → 정규화(champions 83건 등) → 임베딩(10개 청크, 무료 티어 고려해 표본만) → 원자적 승격까지 9.9초 만에 성공, `is_current`가 정확히 새 patch_version을 가리키는 것까지 확인. 이걸로 DATA-08/09/10/11/12/13이 실제로 하나의 파이프라인으로 맞물려 동작함이 처음으로 증명됨

## 다음 세션을 위한 메모

- 이 스모크에서 조립한 `step_collect`/`step_normalize`/`step_embed` 3단계 패턴이 실제 GitHub Actions 크론 워크플로우에서 쓸 최상위 오케스트레이션 스크립트의 뼈대가 될 수 있다(현재는 임시 스크립트로만 존재, 정식 스크립트 파일화는 필요 시 후속 작업)
- `on_trigger`(DATA-12) ↔ `run_batch_with_atomic_promotion`(DATA-13) 연결: DATA-12의 `on_trigger(before, after)` 콜백 자리에 `lambda before, after: run_batch_with_atomic_promotion(session, after, steps)`를 넣으면 감지→실행이 이어진다. 아직 실제 배선 코드는 작성하지 않음(둘 다 함수 단위로는 완성, 접착만 남음)
- 동시 실행 방지(GitHub Actions concurrency)는 여전히 DATA-14 몫 — 이 트랜잭션 자체는 "같은 프로세스 안에서 실행 도중 조회"만 다루고 "두 배치가 동시에 도는 것"은 안 막는다
