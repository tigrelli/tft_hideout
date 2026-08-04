# CHAT-06 : 작업결과

- **TASK**: 출력 후처리 구현(근거검증·Legend승률이중방어·닉네임마스킹·구조화출력·재시도폴백)
- **상태**: 완료(PM 승인 2026-08-04)
- **선행 TASK**: CHAT-05
- **근거 문서**: 설계서 4.4.3, `docs/test-scenarios.md` CHAT-06(TEST-00)
- **변경 파일**: `backend/services/chat_postprocessing.py`(신규), `backend/services/prompt_assembly.py`(시스템 프롬프트 8번 규칙 추가), `backend/services/chat_stream.py`(버퍼링+후처리 배선), `backend/tests/test_chat06_postprocessing.py`(신규), `backend/tests/test_chat05_streaming.py`(버퍼링 방식 반영해 fake 토큰 수정)

## 착수 전 PM 확인받은 설계 결정 2가지

1. **재시도/폴백은 CHAT-05에서 이미 구현됨**: WBS TASK 설명에 "재시도폴백"이 포함돼 있으나, TEST-00 시나리오 #6과 동일한 요구사항이고 CHAT-05의 `stream_llm_answer()`가 이미 처리 중이라 중복 구현하지 않음.
2. **근거검증 메커니즘**: 일반 한국어 자유문장에서 고유명사를 자동 추출(NER)하는 건 정규식만으로 원칙적으로 불가능하다는 점을 PM과 논의. 해결: 시스템 프롬프트에 8번 규칙 신설("조합/챔피언/아이템/증강체를 언급할 때는 작은따옴표로 감싸라") → 후처리에서 인용부호 구간만 추출해 검색 문서 메타데이터와 대조. 이건 임의 자연어 이해가 아니라 **설계서 4.4.3 원문이 명시한 "문자열 매칭" 방식**을 그대로 따른 것이며(LLM 재검증 호출 없음), LLM의 자연어 이해·생성은 여전히 프롬프트(4.4.1)가 전담하고 후처리는 결정론적 안전망 역할만 함을 명확히 함.
3. **스트리밍 방식 변경**: 근거검증·승률마스킹은 완성된 문장 단위로만 신뢰할 수 있어(부분 토큰 중간에 숫자·인용부호가 잘리면 정규식 오작동), CHAT-05의 "Groq 토큰 그대로 실시간 전달" 방식을 "서버에서 전체 버퍼링 → 후처리 → 검증된 텍스트를 공백 기준으로 재분할해 순차 전송"으로 변경(PM 승인 2026-08-04). 체감상 완전한 실시간 타이핑은 아니지만 순차 전송은 유지됨. 느리면 추후 개선하기로 함.

## 결과 요약

- **`prompt_assembly.py`**: `SYSTEM_PROMPT_BASE`에 8번 규칙 추가(상수 참조 방식이라 CHAT-03 스냅샷 테스트는 코드 변경 없이 그대로 통과 확인)
- **`chat_postprocessing.py`**:
  - `verify_grounding()`: 답변에서 작은따옴표로 인용된 이름을 추출 → 검색 문서 `doc_metadata`(comp/augment는 `name`, item_build는 `champion` 키, DATA-11 기준)와 대조 → 없으면 경고 문구 추가
  - `mask_augment_win_rate_leak()`: `승률` 뒤 10자 이내 퍼센트 숫자를 정규식으로 마스킹(Legend 승률 비노출 정책 2차 방어선, 1차 방어선은 API-05/프롬프트의 컨텍스트 제외)
  - `mask_opponent_nicknames()`: 주어진 닉네임 목록을 "상대 플레이어"로 치환(재사용 유틸 — PGA-09/CHAT-10에서 실제 닉네임과 함께 쓰일 예정, 일반 Q&A 흐름엔 닉네임 데이터가 없어 아직 호출 안 됨)
  - `postprocess_answer()`: 승률마스킹 → 닉네임마스킹 → 근거검증 순으로 전체 파이프라인 조립
  - **구조화 출력**: LLM에게 JSON 모드로 별도 요청하지 않고, `retrieved_docs`(CHAT-02 결과, id 포함)를 오케스트레이션 레이어가 이미 갖고 있으므로 이를 그대로 "참조 문서" 목록으로 활용 — CHAT-07(링크 삽입)에서 이 값을 그대로 소비하면 됨(불안정한 LLM JSON 모드 대신 결정론적 방식 채택)
- **`chat_stream.py`**: `generate_answer_stream()`이 `stream_llm_answer()` 전체를 버퍼링(`"".join`) → `postprocess_answer()` 적용 → 공백 기준 재분할 후 yield

## 자체 검증

- pytest 14건 신규(backend 전체 **149/149 통과**), ruff check/format 통과
  - TEST-00 시나리오 그대로: 검증된 이름만 언급(통과), 미검증 이름(경고 추가), 승률 무언급(no-op), 승률 패턴 마스킹(단일/복수), 닉네임 마스킹(단일/복수/미매칭/빈 목록)
  - 추가: item_build 문서의 `champion` 메타데이터 키로도 검증되는지, 인용부호 자체가 없는 답변은 그대로 통과하는지, 인용된 이름이 여러 개 섞였을 때 하나라도 미검증이면 플래그되는지, 전체 파이프라인(마스킹+검증+닉네임) 통합
- CHAT-05 테스트 중 `generate_answer_stream`의 최종 토큰 목록을 검증하던 테스트 1건은 버퍼링 방식 반영해 fake 토큰에 실제 Groq 델타처럼 선행 공백을 포함하도록 수정(동작은 동일하게 재확인)
