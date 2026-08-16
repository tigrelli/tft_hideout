# CHAT-24 : 작업결과 (완료 — PM 승인 2026-08-16)

- **TASK**: gpt-oss-120b 리즈닝 토큰으로 인한 의도분류/오프토픽/후속질문 생성 회귀 수정
- **긴급도**: 높음 — CHAT-23 배포(15:01경) 이후 **지금 이 순간까지 프로덕션에 이미 영향을 주고 있는 실사용 버그**.
- **계기**: TEST-11 카테고리 E 재개 전 소량 프로브(3문항) 중 "다음 세트는 언제 출시되나요?"가 정상적인 `general_game_info`(웹검색) 경로 대신 엉뚱한 회피성 답변을 내는 것을 발견, 원인 추적.

## 원인

`openai/gpt-oss-120b`는 리즈닝(추론) 모델이라 최종 답변(`content`) 이전에 별도 `reasoning` 필드로 사고 과정을 먼저 생성하고, 이 reasoning 토큰도 `max_tokens` 예산에서 함께 차감된다. `backend/services/groq_client.py`의 `call_groq_chat`(의도분류·오프토픽 2차 검증·후속질문 생성이 공유)는 CHAT-23 이전(비-리즈닝 구모델 llama-3.3-70b-versatile) 기준으로 `max_tokens=20`이 정해져 있었는데, 새 모델에서는 이 20토큰이 reasoning만으로 소진되어 `content`가 빈 문자열로 잘리는 것을 Groq API 응답 객체(`finish_reason="length"`, `usage.completion_tokens_details.reasoning_tokens=18`)로 직접 확인했다.

**영향 범위**(모두 `call_groq_chat` 공유):
- `intent_classification.classify_by_llm` — 반환값이 `VALID_INTENTS`에 속하지 않으면(빈 문자열 포함) `general_strategy`로 항상 폴백 → 1차 키워드로 애매했던 질문(`general_game_info`·`item_recommendation` 등)이 전부 `general_strategy`로 오분류.
- `chat_preprocessing.confirm_off_topic` — `raw == "off_topic"` exact match라 빈 문자열이면 자동으로 `False`(on_topic 통과) 처리돼 이쪽은 fail-open으로 실사용자에게 직접적인 오류는 안 남지만, 설계 의도(2차 LLM 검증)가 사실상 무력화된 상태였음.
- `chat_followups.generate_followup_questions`은 별도 `FOLLOWUP_MAX_TOKENS=200`을 쓰고 있어 이번 회귀의 직접 피해자는 아니었으나, 같은 함수를 공유하므로 함께 재검증.

## 재현 (실제 Groq API 호출)

```
mt=20, effort=None(default): content='' finish_reason='length' reasoning_tokens=18
```
"메타 트렌드 알려줘" 등 일부 질문은 reasoning_tokens가 52까지 관측됨(질문 복잡도에 따라 가변).

## 수정

`backend/services/groq_client.py`:
- `call_groq_chat`에 `reasoning_effort="low"` 고정 적용(리즈닝 토큰 절감).
- 기본 `max_tokens`를 20 → **100**으로 상향(관측된 reasoning 최대치 52에 여유를 둠).
- `stream_groq_chat`(본답변 생성, max_tokens 제한 없음)은 이번 버그의 영향을 받지 않아 변경하지 않음 — 다만 기본 reasoning_effort(medium)로 매 답변마다 추가 토큰을 소비하고 있어 TPD 효율화 관점에서 별도 검토 여지가 있음(이번 범위 밖, 필요 시 별도 TASK로 제안 가능).

## 자체 검증

- **pytest**: 도커 테스트 DB로 백엔드 전체 스위트 재실행 — **352 passed**.
- **라이브 재검증**(실제 Groq API 호출):
  - `classify_intent_for_query`: "다음 세트는 언제 출시되나요?" → `general_game_info`(정상, 회귀 전 기대값과 일치), "메타 트렌드 알려줘" → `general_strategy`, "최고의 조합 알려줘" → `comp_recommendation` 등 5개 질문 모두 정상 분류.
  - `is_off_topic_for_query`: "오늘 저녁 뭐 먹지?" → `True`(off_topic), "시즌 종료는 언제인가요?"·"다음 세트는 언제 출시되나요?" → `False`(on_topic) — 정상 동작.
  - `generate_followup_questions`: 조합 답변에 대해 관련 후속 질문 1개 정상 생성 확인.

## 배포 후 확인 (2026-08-16, 076e3a2 push 직후)

- 캐시에 이미 있던 동일 질문("다음 세트는 언제 출시되나요?")은 CHAT-08 캐시(질문+patch_version 키) 히트로 수정 전 답변(범위 외 거부)이 15회 연속 그대로 반환됨 — 배포 실패가 아니라 **정상적인 캐시 동작**(자연 만료 대기, 별도 조치 불필요).
- 캐시에 없는 다른 문구("이번 세트 출시일이 언제인지 알려줄 수 있어?")로 재확인한 결과, `general_game_info`(웹검색) 경로로 정상 라우팅되어 출처 링크 포함 답변 생성 확인 — **수정 정상 배포·서빙 확인됨**.

## PM에게 필요한 결정

1. 수정 승인 시 즉시 커밋·push·배포(현재 프로덕션이 이 버그를 그대로 안고 있는 상태).
2. TEST-11은 이 수정 배포 후 카테고리 E부터 재개(수정 전 상태로는 결과가 무효).
