# CHAT-32 : 작업결과

- **TASK**: 다중 주제 복합질의 항목별 분해 응답
- **상태**: 완료(PM 확인 2026-08-19, 구현·자체검증·도커 재검증 모두 완료)
- **선행 TASK**: CHAT-01 (TEST-11 H12에서 발견, 2026-08-19 신설)
- **근거 문서**: `docs/verification/TEST-11-작업결과.md`(카테고리 H 결과 상세)
- **변경 파일**: `backend/services/chat_preprocessing.py`, `backend/services/prompt_assembly.py`, `backend/services/chat_stream.py`, `backend/tests/test_chat32_multi_topic.py`

## 문제

"아이템 조합표랑 이번 패치노트랑 랭크 시스템 다 한 번에 알려줘"처럼 서로 다른 주제 3개를 한 질문에 요청하면, 기존 단일 의도분류·단일 검색 구조로는 의도분류가 잡은 항목(또는 우연히 매칭된 조합) 하나만 답하고 나머지는 통째로 침묵했다.

## 설계 결정

주제별로 각각 검색·LLM 호출을 반복하는(sub-query 분해) 방식도 검토했으나, 다중 주제 질의 하나마다 Groq 호출이 N배로 늘어나 과거 TPD 소진 사고(CHAT-23/24)와 같은 위험을 키운다고 판단해 채택하지 않았다. 대신 **CHAT-27(general_rules)과 동일한 설계** — 검색을 생략하고 단일 LLM 호출로 감지된 주제를 전부 항목별로 답하도록 프롬프트로 강제하는 가벼운 방식을 선택했다.

## 구현

1. **`chat_preprocessing.py`에 `detect_multi_topic_signals()` 신설**: 5개 주제 버킷(item_combination/patch_notes/rank_system/comp_recommendation/augment)을 정규식으로 감지해, 2개 이상 매칭되면 다중 주제 질의로 판정. `multi_topic_labels()`가 감지된 버킷을 한글 표시 이름으로 변환.
2. **`prompt_assembly.py`에 `MULTI_TOPIC_SYSTEM_PROMPT` 신설**: 1번 규칙이 핵심 — "[요청된 주제] 섹션에 나열된 주제를 하나도 빠짐없이, 각각 소제목을 붙여 답하라." 그 외 general_rules와 동일한 안전장치(모르면 정직하게 확인 안 됨, 시의성 있는 내용 추측 금지, TFT 무관 내용 안내)를 재사용.
3. **`chat_stream.py`**: `is_patch_version_query` 조기반환 다음, 의도분류 전에 `detect_multi_topic_signals()`가 2개 이상 감지하면 `_generate_multi_topic_answer()`로 라우팅 — `embed_fn`/`search_fn`/`web_search_fn`/`classify_fn` 전부 호출하지 않는다. `chat_logs.intent`에는 `"multi_topic"`(6개 정식 의도와 별도 식별용 자유 문자열, KPI 집계에서 구분 가능)로 기록.

## 자체 검증

- **pytest 신규 11건**(`test_chat32_multi_topic.py`): H12 문장에서 3개 주제(아이템 조합/패치노트/랭크 시스템)가 모두 감지되는지, 단일 주제 질문(및 정상 조합 추천 요청)은 다중 주제로 오탐하지 않는지, 라벨 매핑, 프롬프트 규칙 문자열, `[요청된 주제]` 섹션 조립, 스트림 레벨에서 H12가 실제로 검색·의도분류 없이 항목별 답변을 만드는지, `chat_logs.intent`가 `"multi_topic"`으로 기록되는지, 단일 주제 질문은 기존 의도분류 경로(`classify_fn` 호출 1회)를 그대로 타는지(회귀 방지).
- **backend 전체 448/448 통과**(기존 437+신규 11건), ruff check/format 클린.
- **batch 전체 139/139 통과**(회귀 없음).
- Docker(test-db) 재검증 완료.

## 한계 및 후속 확인 필요 사항

- 주제 감지는 5개 버킷에 한정된 키워드 매칭이라, H12 외의 다른 조합(예: "증강체랑 랭크 시스템 같이 알려줘")에서는 감지되지만 완전히 새로운 주제 조합(예: 이 5개 버킷에 없는 주제)은 여전히 단일 주제로 처리된다 — 재발 시 버킷을 계속 추가하는 CHAT-19/21/25/31과 동일한 점진적 보강 방식.
- 실제 답변이 각 주제를 얼마나 정확하고 충실하게 다루는지는 2차 Groq LLM이 `MULTI_TOPIC_SYSTEM_PROMPT` 1번 규칙(항목 누락 금지)을 얼마나 잘 따르는지에 달려있어, 배포 후 프로덕션 재질의로 최종 확인 필요(CHAT-27~31과 동일한 성격의 한계).
- 다중 주제 답변은 검색을 생략하므로, 만약 감지된 주제 중 하나가 실제로는 내부 RAG(comps/items/augments)가 답할 수 있는 구체적 데이터 질문(예: "지금 메타 1위 조합이랑 아이템 조합표 같이 알려줘")이면 그 주제도 general_rules처럼 LLM 일반 지식으로만 답해, RAG에 있는 최신 통계를 놓칠 수 있다 — 이번 범위에서는 "빠짐없이 답하는 것"을 "각 주제의 최신 데이터 정확도"보다 우선했다(H12 자체는 애초에 RAG로 답할 수 없는 주제 조합이라 문제 없음).
