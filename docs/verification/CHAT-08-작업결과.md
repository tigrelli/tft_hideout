# CHAT-08 : 작업결과

- **TASK**: 응답 캐싱 로직 구현
- **상태**: 완료(PM 승인 2026-08-04)
- **선행 TASK**: CHAT-05, DATA-15
- **근거 문서**: PRD 9-6·설계서 v1.7 4.4·4.6
- **변경 파일**: `backend/services/chat_cache.py`(신규), `backend/services/chat_stream.py`(배선), `backend/tests/test_chat08_cache.py`(신규)

## 결과 요약

- **`chat_cache.py`**: `cache_key = sha256(정규화 질문 + patch_version)`. `get_cached_answer()`/`store_answer_in_cache()`(Postgres `ON CONFLICT` upsert, `chat_answer_cache.cache_key` UNIQUE 제약 활용). 패치가 바뀌면 `cache_key` 자체가 달라져 자연 무효화되고(별도 무효화 로직 불필요), 이전 patch_version 행의 물리적 삭제는 DATA-15가 담당(역할 분리).
- **`chat_stream.py`** 배선: `get_conversation_history()` 조회 시점을 의도분류보다 앞으로 옮겨, **대화 이력이 없는 첫 턴 질문에서만** 캐시를 조회 — hit이면 의도분류·임베딩·검색·Groq 호출을 전부 건너뛰고 캐시된 답변만 반환. miss면 기존 파이프라인을 그대로 실행한 뒤 최종 답변(CHAT-07 링크 삽입까지 끝난 텍스트)을 캐시에 저장. **후속 턴(대화 이력 있음)은 캐시를 아예 조회하지 않음**(같은 문장이라도 직전 맥락에 따라 정답이 달라지므로, 설계서 4.4.1).

## 설계 참고 — 캐시 hit 시 chat_logs 미기록

캐시 hit 경로는 의도/검색 파이프라인을 아예 건너뛰므로 `intent`가 계산되지 않는다. `chat_logs.intent`가 NOT NULL이라 캐시 hit까지 로깅하려면 스키마 변경(캐시 테이블에 intent 저장 등)이 필요한데, 이는 DATA-03에서 이미 확정된 `chat_answer_cache` 컬럼 범위를 벗어나 이번 TASK 범위에서는 하지 않음. 캐시 hit은 "새로 생성"이 아니라 "이전에 이미 로깅된 답변의 재사용"이므로 CHAT-09의 "정상 답변 생성 흐름에서만 로깅" 원칙과도 일관됨.

## 자체 검증

- pytest 9건 신규(backend 전체 **172/172 통과**), ruff check/format 통과
  - **WBS 핵심 요구사항**: 첫 턴 캐시 hit 시 파이프라인 함수(embed/classify/search/stream)가 전혀 호출되지 않고 캐시된 답변만 반환되는지(fake 함수가 호출되면 테스트가 실패하도록 설계), 후속 턴은 캐시에 값이 있어도 무시하고 실제로 파이프라인이 도는지, 패치 갱신 후 이전 패치의 캐시는 그대로 남아있지만 새 패치로는 캐시 미스인지(자연 무효화)
  - 추가: `cache_key`가 질문+패치버전 조합마다 달라지는지, 캐시 miss 후 생성된 답변이 실제로 저장되는지, 같은 키에 재저장 시 upsert 되는지
