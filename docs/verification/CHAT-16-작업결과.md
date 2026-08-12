# CHAT-16 : 작업결과

- **TASK**: 오프토픽 판별 2차 LLM 검증 도입
- **상태**: 완료(PM 승인 2026-08-12)
- **선행 TASK**: CHAT-01, CHAT-04
- **근거 문서**: PM 요청(2026-08-12, 웹검색 스코프 검토), `policies.md` 8번
- **변경 파일**: `backend/services/chat_preprocessing.py`, `backend/services/chat_stream.py`, `backend/routers/chat.py`, `docs/test-scenarios.md`, pytest 다수

## 결과 요약

`chat_preprocessing.py`의 `is_off_topic()`이 `_TFT_DOMAIN_PATTERN` 키워드 정규식 미스만으로 즉시 범위 밖 처리해, "시즌 종료는 언제?"처럼 TFT 관련이지만 조합/아이템/증강체/메타 키워드가 없는 질문이 오분류되는 문제를 CHAT-01 의도 분류와 동일한 "1차 키워드 → 애매하면 2차 Groq LLM" 패턴으로 개선했다.

- `is_off_topic()`: 반환값·로직은 그대로 두되 "1차 후보 판정"으로 의미를 재정의(docstring만 갱신)
- `confirm_off_topic(text, llm_call)` 신규: 1차 후보로 판정된 질문만 Groq에 `on_topic`/`off_topic` 단답을 요청. 호출 실패·유효하지 않은 응답은 **on-topic으로 통과(fail-open)** — LLM 실패 시 기본값을 PM과 확정(2026-08-12), CHAT-01 `classify_by_llm`이 실패 시 `general_strategy`로 폴백하는 것과 동일한 방향성
- `is_off_topic_for_query(text)` 신규: 운영 진입점(실제 `call_groq_chat` 사용)
- `chat_stream.py`의 `generate_answer_stream()`에 `offtopic_confirm_fn` 필수 인자 추가, `preprocessed.is_off_topic and offtopic_confirm_fn(...)`로 단락평가해 **키워드 매칭 성공(on-topic 확실) 시엔 LLM 호출 자체를 만들지 않음**(무료 티어 비용·속도 보존)
- `routers/chat.py`에 `is_off_topic_for_query` 배선
- `docs/test-scenarios.md` CHAT-04 섹션에 시나리오 8~11 추가(PM 합의 완료) — 8: 키워드 미스+LLM on_topic 통과, 9: 키워드 미스+LLM도 off_topic 거부(회귀 방지), 10: LLM 실패 시 fail-open, 11: 키워드 매칭 시 LLM 미호출

## 자체 검증

- pytest 신규: `confirm_off_topic` 4건(`test_chat04_input_preprocessing.py`), 키워드미스+LLM on_topic 통과 케이스 1건(`test_chat05_streaming.py`), 기존 off_topic 테스트를 "2차 LLM도 off_topic 확인" 케이스로 보강
- `generate_answer_stream`을 직접 호출하는 기존 테스트 29건(chat05/08/09/11)에 `offtopic_confirm_fn` 인자 일괄 반영(대부분 on-topic 질의라 호출 자체가 없어 `lambda text: False`로 통일, 실제 off-topic 분기 테스트만 개별 지정)
- 1차 로컬 실행 시 docker 미설치로 DB 의존 테스트 13건 미실행 → PM이 로컬 테스트용 docker 기동 후 재검증: **backend 전체 pytest 280/280 통과**(migration/DATA/KPI 등 전부 포함), ruff check/format 클린
  - 재검증 중 신규 테스트 1건의 토큰 분할 방식 오류 발견·수정(최종 답변은 공백 단위로 분할 전송되는데 `["생성된 답변"]`으로 잘못 기대 → `["생성된", "답변"]`으로 수정)
