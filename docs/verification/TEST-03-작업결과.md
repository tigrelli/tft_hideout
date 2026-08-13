# TEST-03 : 작업결과

- **TASK**: chat API 및 RAG 파이프라인 테스트
- **상태**: 완료(PM 승인 2026-08-13)
- **선행 TASK**: CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, CHAT-06, CHAT-07, CHAT-08, CHAT-09
- **완료 기준(DoD)**: 전체 통과, 근거율 샘플 검증
- **변경 파일**:
  - `backend/tests/test_test03_chat_pipeline_integration.py`(신규)

## 배경 및 범위

CHAT-01~09(+CHAT-11~18)는 이미 자기 단계를 촘촘히 단위 테스트한다(3,877줄). 하지만 조사 결과 `generate_answer_stream`(CHAT-05)을 호출하는 기존 테스트(`test_chat05_streaming.py`, `test_chat08_cache.py` 등)는 전부 `classify_fn`/`search_fn`을 하드코딩된 람다로 갈아끼운 채 실행되고, `test_api09_chat_message_stream.py`도 자신의 docstring에서 "실제 LLM 파이프라인 배선은 CHAT-05가 대체했다"며 검증을 명시적으로 미뤄뒀다는 걸 확인했다. 즉 **실제 `classify_intent`(CHAT-01) → 실제 `hybrid_search`(CHAT-02, 진짜 pgvector 검색) → `generate_answer_stream`의 오케스트레이션 → 실제 `postprocess_answer`의 근거검증(CHAT-06)**이 한 번도 함께 실행된 적이 없었다. TEST-01/TEST-02와 같은 방식으로, 이 배선 자체와 DoD가 요구하는 "근거율 샘플 검증"만 새로 다뤘다(외부 I/O인 Groq/HF는 계속 fake 유지 — policies.md 10.2 mock 정책 그대로).

## 구현

`backend/tests/test_test03_chat_pipeline_integration.py` 신규 6건:

1. `test_real_pipeline_wiring_classify_search_postprocess` — 실제 `classify_intent`(키워드 1차 분류만으로 확정, LLM 호출 시 assert 실패하도록 고의로 막음) → 실제 `hybrid_search` → 실제 `postprocess_answer`가 한 번에 연결됐을 때, 실제로 검색된 문서 이름을 인용한 답변이 근거검증 경고 없이 그대로 나오는지 확인(배선 자체의 정상 동작 증명).
2. **근거율 샘플 검증(doc_type 2종 × grounded/ungrounded, 파라미터화 4건)** — comp/augment 두 doc_type에 대해 (a) 실제 검색 결과 이름을 인용하면 통과, (b) 검색은 정상이었지만 LLM이 지어낸 이름을 인용하면 경고가 붙는지 확인.
3. `test_second_session_same_query_hits_cache_and_skips_real_pipeline` — 실제 classify_fn/search_fn을 쓴 채로 동일 질문을 다른 세션(=다른 사용자)이 다시 물으면 캐시(CHAT-08)가 응답해 검색이 재호출되지 않는지 확인.

## 작성 중 발견한 사실(버그 아님, 테스트 설계 실수 2건 자체 교정)

1. **augment 첫 샘플 쿼리가 CHAT-15 이름 겹침 필터에 걸림**: 처음엔 "증강체 뭐가 좋아?"처럼 증강체 이름을 언급하지 않는 질의를 썼는데, `hybrid_search.py`의 `filter_by_name_overlap()`(item/augment 전용, CHAT-15)이 "질의 문자열에 문서 이름 글자가 50% 이상 겹쳐야" 통과시키는 걸 발견 — 실사용에서 아이템/증강체 이름은 항상 질의에 그대로 들어있다는 전제(줄임말은 SLANG_DICTIONARY로 먼저 정식 명칭으로 치환된 뒤 검색됨)로 설계된 정상 동작이었다. 질의를 "힘의 마법공학 증강체 효과 알려줘"로 수정해 실사용 패턴에 맞춤(comp/playstyle은 이 필터 대상이 아니라 원래 질의 그대로 통과).
2. **캐시 테스트가 같은 session_id로 두 번 호출해 실패**: CHAT-08 캐시는 "첫 턴"(해당 session_id에 이전 chat_logs가 없음)일 때만 조회되고, 같은 세션의 후속 턴은 문맥 유지를 위해 의도적으로 캐시를 건너뛴다(`test_chat08_cache.py`의 `test_subsequent_turn_ignores_cache_even_if_entry_exists`가 이미 이 정책을 검증 중). 두 번째 호출에 다른 session_id를 써서 "새 사용자의 첫 턴"을 정확히 흉내내도록 수정.

## 자체 검증

- 신규 6건 전체 통과, 회귀 없음: `backend` 전체 pytest **317/317** 통과(TEST-02 이후 311 + 신규 6).
- 수정 두 건 반영 후 첫 통과 — 둘 다 앱 코드 버그가 아니라 위 두 가지 실제 정책(이름 겹침 필터, 첫 턴 전용 캐시)을 테스트가 처음엔 잘못 가정한 것이었음.
- `ruff check` / `ruff format` 통과.
- Docker(`docker-compose.test.yml`) test-db(5433)로 로컬에서 직접 실행.

## PM 확인 결과

2026-08-13 PM 승인.
