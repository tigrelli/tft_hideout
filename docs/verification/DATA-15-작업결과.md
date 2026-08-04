# DATA-15 : 작업결과

- **TASK**: 캐시 정리 배치 구현(Postgres, v1.7)
- **상태**: 완료(PM 승인 2026-08-04)
- **선행 TASK**: DATA-13, DATA-03
- **근거 문서**: 설계서 v1.7 4.3·4.6
- **변경 파일**: `batch/cache_cleanup.py`(신규), `batch/run_patch_batch.py`(배선), `batch/tests/test_data15_cache_cleanup.py`(신규)

## 결과 요약

WBS 범위(TASK 설명·완료기준 모두 `chat_answer_cache`만 명시, `db/models.py`의 `ChatAnswerCache` 독스트링에도 "패치 배치 완료 후 이전 patch_version 행은 DATA-15 배치가 DELETE"로 한정)에 맞춰, `puuid_cache`(자체 `expires_at` TTL, 별도 정리 불필요)는 이번 TASK 범위에서 제외했다.

- **`batch/cache_cleanup.py`**: `delete_stale_chat_answer_cache(session, current_patch_version)` — `chat_answer_cache`에서 `patch_version != current_patch_version`인 행을 DELETE하고 삭제된 행 수를 반환.
- **`batch/run_patch_batch.py`** 배선: `on_trigger()`에서 `run_batch_with_atomic_promotion()`이 **성공한 경우에만**(`result.success`) 새 patch_version 기준으로 정리 함수를 호출한 뒤 커밋. 배치가 실패해 승격이 안 된 경우(`patches.is_current`가 이전 버전 유지)엔 정리도 건너뛰어, 아직 유효한 이전 버전 캐시가 잘못 삭제되는 일이 없도록 함.

## 자체 검증

- pytest 4건 신규(batch 전체 74/74 통과, ruff check/format 통과):
  1. 이전 patch_version 행만 삭제되고 현재 버전 행은 남는지
  2. 삭제할 이전 버전 행이 없을 때 0건 반환하는지
  3. **WBS 테스트 요구사항 그대로**: `run_batch_with_atomic_promotion` 성공(배치 완료 이벤트) 시 캐시 정리가 실행되어 이전 버전 캐시가 삭제되는지
  4. 배치가 실패해 승격이 안 됐을 때는 캐시 정리도 건너뛰어 이전(현재 유효) 버전 캐시가 그대로 남는지

## PM 확인 필요 사항

없음(외부 API 미사용 로직이라 별도 실운영 스모크 테스트 불필요 — 다음 실제 패치 감지 시 `run_patch_batch.py` 로그의 "캐시 정리(DATA-15): chat_answer_cache N행 삭제" 출력으로 자연히 확인 가능).
