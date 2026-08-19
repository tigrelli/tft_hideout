# CHAT-33 : 작업결과

- **TASK**: 비한국어(영어) 질문 언어 대응
- **상태**: 완료(PM 확인 2026-08-19, 구현·자체검증·도커 재검증 모두 완료)
- **선행 TASK**: CHAT-01 (TEST-11 H17에서 발견, 2026-08-19 신설)
- **근거 문서**: `docs/verification/TEST-11-작업결과.md`(카테고리 H 결과 상세)
- **변경 파일**: `backend/services/chat_preprocessing.py`, `backend/services/chat_stream.py`, `backend/tests/test_chat04_input_preprocessing.py`, `backend/tests/test_chat33_language_detection.py`

## PM 결정

착수 전 WBS가 명시한 대로 "완전한 영어 응답 지원 vs 한국어 우선 안내만" 중 방식을 PM에게 확인 — **한국어 우선 안내만** 채택(MVP 스코프상 번역 품질을 담보하기 어려운 전체 다국어 지원은 과잉 구현으로 판단).

## 문제

"Can you explain the best comp in English?"처럼 영어로 질문해도 전부 한국어로만 답하고 "한국어 우선 지원"이라는 안내조차 없었다. 원인: `is_off_topic()` 1차 판정에 쓰이는 `_TFT_DOMAIN_PATTERN`이 전부 한글 키워드라 영어 질문은 매칭될 수 없고, 2차 LLM 오프토픽 확인으로 넘어가 봐야 정형 거절 메시지만 나오거나(잡담으로 오판), 통과하더라도 일반 파이프라인이 한국어로만 답을 생성했다.

## 구현

1. **`chat_preprocessing.py`에 `is_non_korean_query()` 신설**: 한글(가-힣)이 전혀 없고 영어 단어가 3개 이상이면 비한국어 질의로 판정. 짧은 영문 약어 하나만 있는 경우("TFT?")까지 비한국어로 판정하면 과잉 차단 위험이 커, 최소 3단어 기준을 뒀다. 한글이 하나라도 있으면(예: "TFT 조합 추천해줘") 무조건 정상 한국어 질문으로 취급한다.
2. **`chat_stream.py`**: `detect_chatbot_meta_topic` 조기반환 다음, `is_off_topic` 판정보다 먼저 검사 — 검색·LLM 호출 없이 결정론적으로 즉답. `NON_KOREAN_LANGUAGE_MESSAGE`를 영어 문장 + 한국어 문장 둘 다 포함하도록 작성해, 정작 영어로 질문한 사용자가 안내 내용 자체를 이해할 수 있게 했다("Sorry, this chatbot mainly supports Korean for now. 죄송하지만 현재는 한국어를 우선 지원하고 있어요...").

## 자체 검증

- **pytest 신규 7건**: `test_chat04_input_preprocessing.py`에 4건(영어 질문 감지, 한글 포함 질문은 오탐 안 함(영어 약어 섞여도), 짧은 영문 약어 1~2단어는 비한국어로 안 걸림) / `test_chat33_language_detection.py`에 2건(H17 스트림 레벨에서 embed_fn/offtopic_confirm_fn/classify_fn/search_fn/web_search_fn/stream_fn 전부 미호출 확인, 한국어 질문은 영향 없음 회귀 확인).
- **backend 전체 455/455 통과**(기존 448+신규 7건), ruff check/format 클린.
- **batch 전체 139/139 통과**(회귀 없음).
- Docker(test-db) 재검증 완료.

## 한계 및 후속 확인 필요 사항

- 영어 외 다른 비한국어 언어(일본어, 중국어 등)는 이번 감지 로직이 다루지 않는다 — `_HANGUL_PATTERN`이 없고 `_ENGLISH_WORD_PATTERN`(A-Za-z)도 없는 경우(예: 순수 일본어)는 감지되지 않아 기존처럼 한국어로 응답을 시도한다. 실사용 중 다른 언어 문의가 재발하면 유니코드 스크립트 감지로 확장 검토.
- 최소 3단어 기준은 TEST-11 H17 문항 하나로 검증한 값이라, 다른 짧은 영어 질문(예: "explain augments please")은 3단어에 딱 걸려 감지되지만 더 짧은 표현은 놓칠 수 있다 — 재발 시 임계값 조정.
