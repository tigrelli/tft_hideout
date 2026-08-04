# CHAT-05 : 작업결과

- **TASK**: sLLM 답변 생성 및 SSE 스트리밍 연동
- **상태**: 완료(PM 승인 2026-08-04)
- **선행 TASK**: CHAT-03, API-09, SET-10
- **근거 문서**: 설계서 4.4
- **변경 파일**: `backend/services/groq_client.py`(스트리밍 함수 추가), `backend/services/chat_stream.py`(전면 재작성 — mock 제거, 실제 배선), `backend/services/current_patch.py`(신규), `backend/services/prompt_assembly.py`(system/user 역할 분리 함수 추가, 기존 `assemble_prompt` 출력은 그대로 유지), `backend/services/embedding_client.py`(`embed_query` 진입점 추가), `backend/routers/chat.py`(엔드포인트 실배선), `backend/tests/test_chat05_streaming.py`(신규), `backend/tests/test_api09_chat_message_stream.py`(mock 전용 테스트 정리)

## 결과 요약

- **`services/groq_client.py`**: `stream_groq_chat(system_prompt, user_message)` 신규 — Groq 채팅 완성을 `stream=True`로 호출해 델타 토큰을 순서대로 yield. 실패 시 예외를 그대로 던지고, 재시도/폴백은 호출측이 담당(기존 `call_groq_chat`과 동일한 원칙).
- **`services/prompt_assembly.py`**: CHAT-03의 `assemble_prompt()`(단일 문자열, 스냅샷 테스트 유지)를 `assemble_system_turn()`(정적: 시스템프롬프트+few-shot) + `assemble_user_turn()`(동적: 검색문서+대화이력+질문)으로 분해 — Groq 채팅 API의 system/user 역할 분리 호출에 필요. 리팩터링이 기존 출력과 동일함을 CHAT-03 스냅샷 테스트로 재확인(변경 없이 통과).
- **`services/chat_stream.py`**:
  - `stream_llm_answer(system_prompt, user_message, stream_fn)`: 토큰을 하나도 못 받고 실패하면 1회 재시도, 그래도 실패하거나 스트림 도중 실패하면 예외 전파 없이 고정 폴백 메시지로 대체(WBS 핵심 요구사항)
  - `generate_answer_stream(db, session_id, raw_message, embed_fn, classify_fn, search_fn, stream_fn)`: CHAT-04가 계산만 해두고 미뤄뒀던 `is_off_topic`/`needs_clarification` 분기를 실제로 연결(해당 시 검색·LLM 호출 전부 스킵) → 정상 질문은 현재 패치 조회(신규 `current_patch.py`) → CHAT-01 의도분류 → CHAT-02 임베딩+검색 → CHAT-03 프롬프트 조립 → 위 `stream_llm_answer` 순으로 배선. 외부 API 호출부(embed/classify/search/stream)는 전부 명시적 인자로 주입받아 라우터가 실제 함수를, 테스트가 fake를 전달(DI, `classify_intent`의 `llm_call` 주입 패턴과 동일)
  - `build_sse_stream()`: API-09의 시그니처를 `(message: str)`→`(token_stream: Generator)`로 일반화(실제 토큰 스트림을 감싸도록)
- **`routers/chat.py`**: `/api/v1/chat/message`가 이제 `generate_answer_stream`(실제 함수 4종 주입)의 결과를 `build_sse_stream`으로 감싸 반환. API-09의 mock 배관을 완전히 대체.
- **API-09 테스트 정리**: mock 특정 동작(단어 그대로 에코)에 의존하던 테스트 4건 제거, `invalid_session_id`/`missing_session_id` 같이 여전히 유효한 라우팅 계층 테스트만 남김.

## 자체 검증

- pytest 10건 신규(backend 전체 **135/135 통과**), ruff check/format 통과, 외부 Groq/HF API 미호출(전부 주입식 fake)
  - **WBS 핵심 요구사항**: `build_sse_stream` SSE 조립(가짜 토큰 제너레이터), `stream_llm_answer` 재시도(토큰 없이 실패→재시도 성공)·재시도 소진 시 폴백·스트림 도중 실패 시 재시도 없이 폴백(중복 전송 방지)
  - `generate_answer_stream`: 명확화 필요/범위 밖 질문은 검색·LLM 호출 전혀 없이 즉시 고정 메시지 반환(fake 함수가 호출되면 테스트가 실패하도록 설계해 확인), 현재 패치 없음 시 고정 메시지, 정상 흐름에서 의도분류→검색→프롬프트조립까지 올바른 인자로 연결되는지, 대화 이력이 프롬프트에 포함되는지
