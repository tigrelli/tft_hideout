# CHAT-17 : 작업결과

- **TASK**: 웹검색 기반 일반 게임 정보 답변 경로 신설
- **상태**: 완료(PM 승인 2026-08-12)
- **선행 TASK**: CHAT-16, CHAT-03, CHAT-06, SET-17
- **근거 문서**: PM 요청(2026-08-12), `docs/reference/policies.md` 14번(웹 검색 근거 원칙, 이번 TASK로 신설)
- **변경 파일**: `backend/services/web_search.py`(신규), `backend/services/intent_classification.py`, `backend/services/prompt_assembly.py`, `backend/services/chat_stream.py`, `backend/routers/chat.py`, `backend/tests/test_chat17_web_search.py`(신규), 기존 `generate_answer_stream` 호출 테스트 30건에 `web_search_fn` 인자 반영

## 결과 요약

CHAT-16이 on-topic으로 판별했지만 기존 4개 의도(조합/아이템/증강체/일반전략) RAG 검색 대상이 아닌 질문(시즌 일정, 공식 이벤트 등)에 대해 5번째 의도 `general_game_info`를 신설하고, 해당 의도일 때 내부 RAG(CHAT-02) 대신 Tavily 웹 검색을 근거로 답변한다.

- **`services/web_search.py`(신규)**: `WebSearchResult` 데이터클래스, `search_web()`(Tavily 실호출 진입점 — 실패는 예외 그대로 전파, 폴백은 호출측 책임), `verify_web_citation()`(답변에 포함된 URL이 실제 검색 결과 URL과 일치하는지 사후 검증 — CHAT-06 `verify_grounding()`과 동일한 결정론적 사후 점검 원칙, 불일치 시 경고 문구 추가)
- **`intent_classification.py`**: `INTENT_GENERAL_GAME_INFO` 신설. 키워드 사전 나열이 어려운 잔여 카테고리라 1차 키워드 매칭에는 넣지 않고 2차 LLM 분류 전용으로 설계(CHAT-16과 동일한 원칙). LLM 실패/무효 응답 시 폴백은 여전히 `general_strategy`(무료 티어 오류로 엉뚱하게 웹검색이 트리거되지 않도록 안전한 쪽 유지)
- **`prompt_assembly.py`**: `WEB_SEARCH_SYSTEM_PROMPT`(별도 시스템 프롬프트 — 기존 `SYSTEM_PROMPT_BASE`는 `[검색된 문서]`·패치버전 근거를 전제해 그대로 재사용 불가, 출처 URL 필수·완곡한 표현·존댓말 등 6개 규칙 신설), `WEB_SEARCH_FEW_SHOT_EXAMPLE`, `assemble_web_search_system_turn()`/`assemble_web_search_user_turn()`(기존 assemble 함수와 동일 구조, `[웹 검색 결과]` 섹션 사용)
- **`chat_stream.py`**: `generate_answer_stream()`에 `web_search_fn` 신규 인자 추가, `intent == INTENT_GENERAL_GAME_INFO`면 신규 `_generate_web_search_answer()` 헬퍼로 완전히 분기(embed_fn/search_fn 미호출). Tavily 실패 시 기존 `FALLBACK_MESSAGE`로 즉시 폴백(Groq 호출 없이, chat_logs 미기록 — 다른 조기반환 분기와 동일 원칙). 성공 시 `chat_logs`에 `intent=general_game_info`, `retrieved_doc_ids=[]`로 기록. **v1 범위 제한**: 웹 검색 결과는 `meta_document_embeddings`에 없어 기존 `retrieved_doc_ids` 기반 CHAT-08 캐시·CHAT-11 후속질문 result 사이드채널은 지원하지 않음(필요해지면 별도 TASK)
- **`routers/chat.py`**: `web_search_fn=search_web` 배선
- **`policies.md` 14번 신설**: 웹 검색 근거 원칙(5번 RAG 근거 원칙과 관계 명시)

## 자체 검증

- pytest 신규 16건(`test_chat17_web_search.py`): 의도분류(키워드 미매칭·LLM 분류·실패 폴백), `verify_web_citation`(일치/불일치/문장부호 처리/URL 없음), 프롬프트 조립(시스템 프롬프트 존댓말·출처 규칙, few-shot 포함, 결과 있음/없음/이력 유무), `generate_answer_stream` 분기(내부 RAG 미호출 확인, chat_logs 기록, Tavily 실패 폴백, 할루시네이션 URL 경고)
- 기존 `generate_answer_stream` 직접 호출 테스트 30건에 `web_search_fn` 인자 일괄 반영(모두 다른 의도 질의라 호출 자체가 없음, `lambda text: []`로 통일)
- **backend 전체 pytest 296/296 통과**(docker test-db 기반), ruff check/format 클린
- **로컬 실제 서버(3000/8000) + 실제 Groq + 실제 Tavily 종단 검증**:
  - `"TFT 이번 시즌은 언제 끝나?"` → 실제 Groq가 실제 Tavily 검색 결과(네이버 지식iN·레딧·티스토리 등)를 근거로 "정확한 종료일은 확인되지 않았습니다. 일반적으로 3~4개월 지속된다고 알려져 있습니다..." 형태로 존댓말 응답, 출처 URL 포함. 답변에 포함된 URL 일부가 실제 검색 결과 URL과 정확히 일치하지 않아 `verify_web_citation`이 의도대로 "(주의: ... 확인되지 않았습니다.)" 경고를 실제로 붙임(안전장치 정상 작동 실증)
  - DB 직접 조회로 `chat_logs` 확인: `intent=general_game_info`, `retrieved_doc_ids=[]`, `patch_version=17.8`, `latency_ms=940` 정상 기록
  - 회귀 확인: `"지금 메타에서 강한 조합 추천해줘"`(기존 comp_recommendation 경로) 동일 서버에서 정상 응답(링크·티어 정보 포함) — CHAT-17 변경이 기존 4개 의도 경로에 영향 없음 확인

## 한계·후속 논의 필요

- CHAT-08 캐시·CHAT-11 후속질문은 이번 범위에서 미지원(위 "v1 범위 제한" 참고)
- 실측에서 확인된 것처럼 LLM이 여러 출처 URL을 쉼표로 나열할 때 사소한 포맷 차이(트레일링 문자 등)로도 `verify_web_citation`이 보수적으로 경고를 붙이는 경향이 있음 — 오탐 허용(안전 우선) 설계로 의도된 동작이나, 체감상 경고가 너무 잦으면 추후 URL 정규화 로직 보강 검토
- Tavily 무료 티어(월 1,000크레딧) 소진 시 폴백 메시지로만 응답 — 실사용량 모니터링은 KPI-01 지표 확장 여부 별도 논의 필요(이번 TASK 범위 아님)
