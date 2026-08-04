# DATA-12 : 작업결과

- **TASK**: 자동 패치 감지 트리거 구현
- **상태**: 완료(PM 확인 요청 중)
- **선행 TASK**: DATA-08, SET-08
- **근거 문서**: PRD 9-1·설계서 4.3
- **변경 파일**: `batch/patch_detection.py`(신규), `batch/tests/test_data12_patch_detection.py`(신규)

## 결과 요약

- **패치 감지 신호**: DATA-05 결정대로 `tft_list_item_combinations().version`(op.gg)을 유일한 신호로 사용. `patches.is_current=true` 행의 버전(없으면 `None`, 최초 실행)과 비교
- **`run_patch_detection(session, opgg_client, on_trigger)`**: 버전이 다르면 주입받은 `on_trigger(before, after)` 콜백을 호출하고, 같으면 호출하지 않음. 실행 결과(트리거 여부·전후 버전·소요시간)를 `patch_detection_runs`에 기록(schema.md 로그 테이블, DATA-03에서 이미 생성됨)
- **범위**: 이 TASK는 "감지 후 콜백 호출"까지만 담당한다. 실제 "전체 배치 재수집" 오케스트레이션(DATA-08→10→11→13 연결)은 DATA-13(원자적 전환) 이후 별도로 묶일 예정이라 콜백 자리만 마련해둠. 동시 실행 방지(GitHub Actions concurrency)는 DATA-14 몫

## 자체 검증

- pytest 60/60 통과(기존 51 + 신규 9): `get_latest_patch_version` 필드 누락 시 에러, `get_current_patch_version` 없음/있음 케이스, `run_patch_detection`의 트리거 발동/미발동·`patch_detection_runs` 기록 검증(op.gg는 fake 오브젝트로 대체, 실 API 미호출)
- `ruff check`/`ruff format --check` 통과(pre-commit 고정 버전 기준)
- **WBS DoD("패치 변경 시뮬레이션 트리거 성공") 실제 데이터로 검증**: 테스트 DB에 가짜 옛날 버전(`0.0-old-fake`)을 `is_current`로 심어두고 실제 op.gg 최신 버전(`17.8`)과 비교 → **트리거 정상 발동**. 이후 `17.8`을 `is_current`로 승격(DATA-13이 할 일을 흉내)하고 다시 실제 op.gg와 비교 → **트리거 미발동** 확인. `patch_detection_runs`에 두 실행 모두(`triggered`/`skipped`) 정상 기록됨

## 다음 세션을 위한 메모

`on_trigger` 콜백에 실제로 무엇을 연결할지(DATA-08 클라이언트 호출 → DATA-10 정규화 → DATA-11 임베딩 → DATA-13 원자적 전환을 잇는 최상위 오케스트레이션 함수)는 DATA-13 완료 후 결정. GitHub Actions 크론 워크플로우(`schedule` 트리거) 자체는 아직 없음 — SET-08 로그가 "DATA-12·KPI-02는 동일 워크플로우에 schedule 트리거를 함께 추가"라고 남긴 대로, 이 Python 로직을 실제로 매시간 실행하는 워크플로우 YAML 배선은 별도 확인 필요(DATA-13 이후 오케스트레이션 함수가 나온 다음이 자연스러움).
