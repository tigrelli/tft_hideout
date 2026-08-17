# CHAT-25 : 작업결과

- **TASK**: 경제·로우롤 전략 질문의 오프토픽 오탐 수정
- **상태**: 완료(PM 확인 2026-08-17, 구현·자체검증 완료, 도커 재검증은 환경 제약으로 미실행 — 아래 "한계" 참고)
- **선행 TASK**: CHAT-01, CHAT-16 (TEST-11 카테고리 F QA 실행 중 발견해 2026-08-17 신설)
- **근거 문서**: TEST-11 QA 실행 결과(`docs/spike/chat-qa/results_F.json`)
- **변경 파일**: `backend/services/chat_preprocessing.py`, `backend/tests/test_chat04_input_preprocessing.py`

## 문제 재확인

TEST-11 카테고리 F(메타·공략·운영전략, 20문항)를 프로덕션 챗봇에 실제로 질의하던 중, 명백한 TFT 질문 2건이 오프토픽으로 거절됐다:

- "경제(이코노미) 운영은 어떻게 하는 게 좋나요?" → "죄송하지만 TFT(전략적 팀 전투) 관련 질문에만 답변드릴 수 있어요..."
- "스노우볼링과 그리핑(선반 강화)의 차이는 무엇인가요?" → 동일한 거절 메시지

두 응답 모두 `elapsed_s` 0.9초로, 정상 답변(5~18초)보다 훨씬 짧았다 — 전체 RAG 파이프라인을 타지 않고 오프토픽 판별 단계에서 조기 반환됐다는 신호.

## 원인

`chat_preprocessing.py`의 1차 키워드 패턴(`_TFT_DOMAIN_PATTERN`)에 "경제/이코노미/운영/골드/스노우볼링/그리핑" 같은 단어가 전혀 없어, 두 질문 모두 1차 판정에서 "범위 밖 후보"로 넘어가 2차 LLM 검증(CHAT-16, `confirm_off_topic`)으로 넘어갔다. 2차 프롬프트(`_OFF_TOPIC_CONFIRM_SYSTEM_PROMPT`)의 예시 목록에도 이런 커뮤니티 전략 은어가 없어, low-reasoning 모델(`openai/gpt-oss-120b`, `reasoning_effort="low"`)이 두 질문을 게임 무관 잡담으로 오판했다. 같은 카테고리의 다른 질문(예: "현재 메타에서 가장 강한 조합은?")은 "메타"/"조합"이 1차 패턴에 바로 매칭돼 2차 LLM 호출 없이 통과했다.

## 수정

1. `_TFT_DOMAIN_PATTERN`에 `경제|이코노미|스노우볼링|그리핑` 추가 — 향후 이 키워드가 포함된 질문은 2차 LLM 호출 없이 즉시 on-topic 확정.
2. `_OFF_TOPIC_CONFIRM_SYSTEM_PROMPT`의 on-topic 예시 목록에 "경제(골드/이자) 운영·로우롤/하이롤 같은 커뮤니티 전략 은어" 추가 — 사전에 없는 다른 니치 용어가 2차 LLM으로 넘어가더라도 오판 확률을 낮추기 위한 방어(1차 키워드 사전은 계속 커질 수 없으므로 2차 프롬프트도 함께 보강).

## 자체 검증

- pytest 신규 1건(`test_chat04_input_preprocessing.py::test_is_off_topic_does_not_flag_economy_and_lowroll_strategy_terms`): 두 실패 질문 모두 `is_off_topic() is False` 확인
- `tests/test_chat04_input_preprocessing.py` 전체 39/39 통과(DB 미필요 테스트 전부, 회귀 없음)
- ruff check/format: 변경 파일 클린

## 한계

- 이번 세션 WSL 환경에 Docker가 설치돼 있지 않아(`docker` 명령 자체 없음) `docker-compose.test.yml` 기반 전체 backend/batch pytest 재검증은 못 했다. DB 연동이 필요 없는 대상 파일 테스트만 로컬에서 통과 확인했다 — PR 생성 시 SET-14 CI 게이트가 전체 스위트를 자동 실행하므로 거기서 최종 확인 가능.
- 두 키워드(`경제`, `이코노미`, `스노우볼링`, `그리핑`)만 추가한 좁은 수정이라, 다른 니치 전략 은어(예: "선반강화" 단독, "로우롤"/"하이롤" 자체 등)는 여전히 2차 LLM에 의존한다 — 2차 프롬프트 보강으로 완화했지만 완전히 결정론적이지 않음. TEST-11 진행 중 유사 사례가 더 나오면 1차 키워드에 계속 추가.
