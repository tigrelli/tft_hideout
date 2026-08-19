# CHAT-26 : 작업결과

- **TASK**: 챗봇 자기소개/메타 질문 전용 의도(chatbot_meta) 신설
- **상태**: 완료(PM 확인 2026-08-19, 구현·자체검증·도커 재검증 모두 완료)
- **선행 TASK**: CHAT-01, CHAT-16 (TEST-11 카테고리 G에서 발견해 2026-08-18 신설, H10 사례를 2026-08-19 추가)
- **근거 문서**: `docs/verification/TEST-11-작업결과.md`(카테고리 G·H 결과 상세), `docs/spike/opgg-schema.md`(4·7번 항목, region 파라미터 부재 재확인)
- **변경 파일**: `backend/services/chat_preprocessing.py`, `backend/services/chat_stream.py`, `backend/tests/test_chat04_input_preprocessing.py`, `backend/tests/test_chat05_streaming.py`

## 문제

TEST-11 카테고리 G(챗봇 기능·서비스, 15문항) 채점 결과, "너는 어떤 걸 도와줄 수 있어?" 같은 챗봇 자기 자신에 대한 메타 질문이:

- **11/15건**: TFT 게임 콘텐츠 키워드(`_TFT_DOMAIN_PATTERN`)가 거의 없어 `is_off_topic()` 1차 판정에서 범위 밖 후보로 걸리고, 2차 LLM 검증(CHAT-16)도 대부분 "무관한 잡담"으로 오판 → 날씨 질문과 동일한 정형 거절 메시지로 회피
- **1건(G9)**: "한국 서버 기준으로 답해주는 거야, 아니면 글로벌 기준이야?"가 우연히 "한국 서버" 키워드로 걸려 general_game_info(웹검색) 경로로 새고, 무관한 "TFT 한국 서버 2019년 6월 29일 정식 오픈"이라는 실제 게임 출시일 정보를 근거로 "한국 서버 기준"이라는 틀린 결론을 제시
- **2026-08-19 추가 확인(카테고리 H, H10)**: "너 진짜 도움이 하나도 안 되네" 같은 메타 피드백/불만도 날씨 질문(H1)과 동일한 정형 거절로 응대 — 방어적이지 않다는 기준은 충족하나 개선 방향을 되묻지 않음

## 원인

A~F가 "TFT 게임 규칙/전략 RAG 부재"였다면, G/H10은 "챗봇 자신에 대한 메타 질문을 처리할 경로 자체가 없다"는 별개 구조적 공백 — 오프토픽 판별기가 이런 질문을 그대로 흡수해 정형 거절로 쳐내거나, 우연히 키워드가 걸리면 웹검색으로 새서 무관한 정보를 인용했다.

## 수정

CHAT-19(패치버전 조기반환)와 동일한 설계: `is_off_topic()` 판정보다 먼저 결정론적으로 감지해, 검색·LLM 호출 없이 고정 FAQ 답변으로 즉답한다.

1. **`chat_preprocessing.py`**: `detect_chatbot_meta_topic()` 신설 — 15개 주제 버킷(identity/privacy/memory/source/feedback_report/region/voice/image/language/realtime_stats/realtime_patch/match_analysis/other_game/feedback_complaint/capability)을 정규식으로 감지하고, `CHATBOT_META_ANSWERS` 딕셔너리에서 매칭된 버킷의 고정 답변을 찾는다. G1~G15(15문항)와 H10을 각각 하나의 버킷에 매핑.
   - **오탐 방지**: 각 정규식은 "주제 키워드 + 챗봇에게 묻는 문형"을 함께 요구한다. 예를 들어 `realtime_stats`는 "최신/실시간 승률·픽률" + "알려줄 수/가능"을 함께 요구해, "이 챔피언 실시간 승률 알려줘" 같은 순수 통계 요청(조합/아이템 검색 경로로 가야 함)과 구분한다. `privacy`는 "안전"만으로 매칭하지 않고 "계정 정보/닉네임" 문맥을 필수로 둬 "이 조합 안전해?"(게임 전략 질문) 오탐을 막는다.
   - **G9 정정**: `region` 버킷 답변에 "전 세계 통합 집계 기준(리전별로 나눠서 제공하지 않음)"을 명시(op.gg MCP 통계 도구에 애초에 region 파라미터가 없다는 사실 재확인, `docs/spike/opgg-schema.md` 4·7번 참고).
2. **`chat_stream.py`**: `generate_answer_stream()`의 `needs_clarification` 체크 직후, `is_off_topic` 체크보다 먼저 `detect_chatbot_meta_topic()` 조기 반환을 추가 — patch_version 조회조차 필요 없는 가장 이른 단계라 DB 접근 없이도 즉답한다.

## 자체 검증

- **pytest 신규**: `test_chat04_input_preprocessing.py`에 6건 추가 — G1~G15+H10 전체 16개 질문이 각각 올바른 버킷으로 분류되는지(parametrize), 일반 TFT 질문(조합 추천/아이템 효과/패치버전 질의)이 오분류되지 않는지, 순수 잡담이 매칭되지 않는지, `realtime_stats`/`privacy` 오탐 방지 가드가 실제로 동작하는지, `CHATBOT_META_ANSWERS`가 모든 감지 가능 버킷을 빠짐없이 커버하는지. `test_chat05_streaming.py`에 2건 추가 — chatbot_meta 감지 시 `embed_fn`/`offtopic_confirm_fn`/`classify_fn`/`search_fn`/`web_search_fn`/`stream_fn`이 전혀 호출되지 않는지(mock 카운트 0, `_fail_if_called` 사용)를 identity·feedback_complaint 두 버킷으로 확인.
- **backend 전체 382/382 통과**(기존 376+신규 8건 — 위 6+2), ruff check/format 클린.
- **batch 전체 139/139 통과**(회귀 없음, 이번 TASK는 batch 무관).
- Docker 재검증: `docker-compose.test.yml`(test-db, 5433)로 DATABASE_URL 지정 후 위 수치 그대로 재확인.

## 한계 및 후속 확인 필요 사항

- 정규식 기반 키워드 감지라 완벽한 구분은 불가능 — 특히 `capability`(포괄적 "너는 뭘 도와줄 수 있어?" 패턴)는 표현이 조금만 달라져도(예: "네가 할 수 있는 게 뭐야?") 놓칠 수 있다. TEST-11 G/H10 원문 그대로는 전부 커버되지만, 실제 프로덕션 사용자의 다른 표현은 다음 TEST-11 재실행이나 실사용 중 추가로 확인 필요.
- `feedback_report`(G8) 답변은 API-15/FE-17(신고 게시판)이 아직 대기 상태라 "추후 지원할 예정"으로만 안내 — 두 TASK가 완료되면 실제 경로를 안내하도록 이 문구를 업데이트해야 한다(별도 후속 조치로 기록해둘 것).
- 배포 후 실제 프로덕션 재질의(G1~G15, H10)로 최종 확인은 PM 승인 이후 진행 예정.
