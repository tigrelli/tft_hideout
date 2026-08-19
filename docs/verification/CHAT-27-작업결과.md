# CHAT-27 : 작업결과

- **TASK**: 일반 게임 규칙/개념 설명 RAG 커버리지 확충
- **상태**: 완료(PM 확인 2026-08-19, 구현·자체검증·도커 재검증 모두 완료)
- **선행 TASK**: CHAT-01, CHAT-02, CHAT-16 (TEST-11 카테고리 B/C/D/E·H에서 발견, 2026-08-19 신설)
- **근거 문서**: `docs/verification/TEST-11-작업결과.md`(카테고리 B/C/D/E 결과 상세), PM 결정(2026-08-19, "새 의도 신설" 방식 채택)
- **변경 파일**: `backend/services/intent_classification.py`, `backend/services/prompt_assembly.py`, `backend/services/chat_stream.py`, `backend/tests/test_chat27_general_rules.py`, `docs/reference/glossary.md`

## 문제

TEST-11 채점(2026-08-15~08-19) 중 B~E·H 전 카테고리에 걸쳐 반복 확인된 가장 큰 규모의 커버리지 공백 — 패치와 무관한 불변 게임 규칙/개념(아이템 조합 방식, 마나 시스템, 성급별 스킬 강화, 랭크 티어 단계·LP 계산, 매칭 방식 등)을 물으면 내부 RAG(comps/items/augments)에 설명 문서 자체가 없어 전부 "정보가 확인되지 않았습니다"로 회피. 비중: B 8/25(32%) · C 15/20(75%, 아이템 영역 특히 심각) · D 5/15(33%).

## 해결 방식 (PM 결정)

RAG 문서 신설(문서 작성 부담 큼) 대신 **새 의도(`general_rules`) 신설**을 채택 — 패치·세트가 바뀌어도 달라지지 않는 고정 규칙 질문은 검색을 생략하고 LLM의 일반 TFT 지식으로 직접 답하게 한다.

## 구현

1. **`intent_classification.py`**: `INTENT_GENERAL_RULES = "general_rules"` 신설, `VALID_INTENTS`에 추가. `general_game_info`(CHAT-17)와 동일하게 **1차 키워드 매칭에는 넣지 않고 2차 LLM 분류로만 도달**하도록 설계(키워드로 사전 나열하기 어려운 잔여 카테고리라는 기존 원칙 그대로 적용). 2차 LLM 분류 프롬프트에 6번째 카테고리로 추가하되, "특정 시점에만 유효한 시의성 있는 내용은 general_rules가 아니라 general_game_info로 분류하라"는 경계 지시를 명시.
2. **`prompt_assembly.py`**: `GENERAL_RULES_SYSTEM_PROMPT` 신설 — 검색 문서·웹 검색 결과가 전부 없는 유일한 경로라 별도 프롬프트로 분리. 핵심은 3번 규칙: "특정 세트/패치에서만 유효한 시의성 있는 내용은 절대 추측해서 단정하지 마라" — H15(카테고리 H, 미확정 미래 세트 정보 환각)와 같은 유형을 이 경로에서 사전 차단하기 위한 안전장치.
3. **`chat_stream.py`**: `_generate_general_rules_answer()` 신설, `general_game_info` 분기 바로 다음에 `general_rules` 분기 추가 — `embed_fn`/`search_fn`/`web_search_fn` 전부 호출하지 않고 `stream_fn`만으로 답한다(6개 의도 중 유일하게 근거 검색이 아예 없는 경로). `postprocess_answer()`(근거검증 `verify_grounding`)는 retrieved_docs가 항상 비어있어 재사용하면 모든 답변이 오탐하므로, `general_game_info`와 동일하게 `strip_internal_doc_marker_leak`+`mask_augment_win_rate_leak`만 적용.

## ⚠️ 알려진 한계 — CHAT-27만으로는 대상 질문의 약 절반만 즉시 해결됨

`general_rules`가 **2차 LLM 분류로만 도달**하는 설계라, 1차 키워드 매칭(`조합|덱|편성`, `아이템|빌드|장비`, `증강체|오그먼트`, `메타|전략`)이 먼저 걸리는 질문은 여전히 general_rules에 도달하지 못하고 기존 의도(주로 item_recommendation)로 잘못 흡수된다. 실측 결과:

| 카테고리 | 대상 질문 | 즉시 해결(2차 LLM 도달) | 여전히 미해결(1차 키워드에 흡수) |
|---|---|---|---|
| B | 8개 | 7개 | 1개(B25 — "아이템" 포함) |
| C | 15개 | 2개(C1·C13 — "조합"도 같이 있어 이중매칭→모호→2차) | 13개("아이템" 단독 매칭) |
| D | 5개 | 5개 | 0개 |
| E | 1개(E12) | 1개 | 0개 |
| **합계** | **29개** | **15개(52%)** | **14개(48%)** |

C 카테고리(전체 커버리지 공백의 가장 큰 비중, 75%)는 거의 전부(13/15)가 "아이템" 단일 키워드로 1차 확정돼버려 이번 TASK만으로는 해결되지 않는다. 이 1차 키워드 과잉매칭 문제는 CHAT-28(키워드 기반 의도 과잉분류 재발 방지, PM 우선순위 다음 순번)의 정확한 스코프이므로 **의도적으로 CHAT-27 범위에서 제외**하고 넘겼다 — CHAT-28이 1차 키워드 단계에서 "추천 요청"과 "규칙 설명 질문"을 구분하게 되면, 그 결과를 이번에 만든 `general_rules` 답변 경로로 그대로 라우팅하면 된다(새 인프라를 다시 만들 필요 없음). `docs/reference/glossary.md`의 의도 분류 절에도 이 한계를 기록해뒀다.

**참고로 CHAT-27 범위에서 의도적으로 제외한 것들**: E1(이번 패치 변경사항)·E3(신규 세트 컨셉)·E6(신규 게임 모드)는 얼핏 "커버리지 공백"처럼 보이지만 실제로는 **패치마다 바뀌는 시의성 있는 내용**이라 general_rules(LLM 고정 지식)로 보내면 오히려 H15와 같은 환각 위험이 커진다 — 이들은 general_game_info(웹검색) 경로에 남겨두고 검색 품질 개선은 CHAT-29 범위로 남긴다. H20(개인 전략 상담)도 "고정 규칙"이 아니라 상황별 조언이라 general_rules 범위에서 제외(향후 general_strategy 프롬프트 개선 등 별도 검토 필요, 이번 TASK 목록엔 없음).

## 자체 검증

- **pytest 신규 16건**(`test_chat27_general_rules.py`): 1차 키워드 미스 확인(5개 대표 질문), 2차 LLM 매핑 확인, 1차 키워드 흡수 한계를 문서화하는 회귀 표식 테스트, 시스템 프롬프트 핵심 규칙(LLM 지식 허용/시의성 내용 추측 금지/존댓말) 문자열 검증, 프롬프트 조립(few-shot 포함/대화이력 유무) 검증, `generate_answer_stream`이 general_rules 분기에서 embed_fn/search_fn/web_search_fn을 전혀 호출하지 않는지(mock 카운트 0), chat_logs에 intent=general_rules·retrieved_doc_ids=[]로 기록되는지, 내부 마커 누출 방어까지 확인.
- **backend 전체 398/398 통과**(기존 382+신규 16건), ruff check/format 클린.
- **batch 전체 139/139 통과**(회귀 없음).
- Docker(test-db) 재검증 완료.

## 후속 확인 필요 사항

- 배포 후 실제 프로덕션에서 D2/D5/D12/D13/D15/E12/B4/B10/B12/B13/B15/B21/B23(1차 키워드 미스 → 2차 LLM 도달 케이스) 재질의로 실제 Groq 2차 분류가 기대대로 `general_rules`를 반환하는지, 그리고 LLM이 생성한 답변 내용 자체가 정답지 채점기준을 충족하는지 최종 확인 필요(이번 자체검증은 mock LLM 응답 기반 배선 검증까지만 커버).
- CHAT-28 완료 후 C 카테고리 13개·B25를 재질의해 이번에 만든 `general_rules` 경로로 실제로 넘어가는지 교차 확인할 것.
