# CHAT-04 : 작업결과

- **TASK**: 입력 전처리 구현
- **상태**: 완료(PM 승인 2026-08-04)
- **선행 TASK**: CHAT-01
- **근거 문서**: 설계서 4.4.2, `/docs/test-scenarios.md` CHAT-04 7개 케이스(TEST-00)
- **변경 파일**: `backend/services/chat_preprocessing.py`, `backend/tests/test_chat04_input_preprocessing.py`

## 결과 요약

TEST-00에서 사전 정의한 CHAT-04 7개 시나리오를 그대로 pytest 케이스로 옮겨 구현했다.

- `normalize_query`: 공백 정리 + 은어 사전 치환(사전에 없는 표현은 실패 처리하지 않고 그대로 통과 — 임베딩 유사도 검색이 흡수)
- `wrap_user_message`: `[사용자 메시지]`/`[/사용자 메시지]` 델리미터로 사용자 입력을 시스템 프롬프트와 구조적으로 분리(NFR-SEC-03). 프롬프트 인젝션 문구도 차단하지 않고 데이터로만 취급해 그대로 감싼다 — "차단"이 아니라 "구조적 분리"가 방어 방식
- `preprocess_input`: 최대 500자 truncate, 빈 입력/공백만 있는 입력은 `needs_clarification=True`로 플래그
- `is_off_topic`: TFT 도메인 키워드 패턴 매칭으로 범위밖 잡담 질문 플래그
- `get_conversation_history`: API-10의 `RECENT_TURNS_LIMIT`(=3)·`get_session_history`를 그대로 재사용해 대화 이력을 최근 3턴으로 제한 — 두 곳의 "최근 3턴" 기준이 어긋나지 않도록 상수·로직 공유

## 자체 검증

- pytest 13/13 통과 (`backend/tests/test_chat04_input_preprocessing.py`, 테스트 DB는 `docker-compose.test.yml`)
- `ruff check` / `ruff format --check` 통과
- WBS DoD("각 케이스 단위 테스트 통과") 충족

## 다음 세션을 위한 메모

`is_off_topic`/`needs_clarification` 플래그는 이 TASK에서는 값 계산까지만 담당한다. 실제로 이 플래그를 받아 "범위밖 안내"·"명확화 요청" 응답으로 분기하는 배선은 CHAT-01의 `classify_intent_for_query`와 마찬가지로 아직 엔드포인트에 연결되지 않았으며, CHAT-05(sLLM 답변 생성 연동) 등 이후 TASK에서 이어진다.
