# CHAT-15 : 작업결과

- **TASK**: 검색 결과 최소 유사도 신뢰도 임계값 도입
- **상태**: 완료(PM 승인 2026-08-09)
- **선행 TASK**: CHAT-02, CHAT-14
- **근거 문서**: CHAT-14 PM 검증 중 발견(2026-08-09), `docs/verification/CHAT-14-작업결과.md`(5차 수정 — "죽무" 오검색)
- **변경 파일**:
  - `backend/services/hybrid_search.py`(수정) — `_DOC_TYPE_MAX_DISTANCE`(거리 임계값), `_distance_within_threshold()`, `_search_single_doc_type()`/메인 검색문에 임계값 적용, `NAME_OVERLAP_DOC_TYPES`·`_name_overlap_ratio()`·`filter_by_name_overlap()`(이름 문자 겹침 2차 보정) 신규
  - `backend/services/chat_stream.py`(수정) — `generate_answer_stream()`이 `search_fn` 결과에 `filter_by_name_overlap()`을 추가로 적용
  - `backend/tests/test_chat02_hybrid_search.py`(수정) — 거리 임계값 적용/미적용(doc_type별) 8건, `filter_by_name_overlap` 단위 테스트 4건
  - `backend/tests/test_chat05_streaming.py`(수정) — `generate_answer_stream`이 이름 겹침 없는 문서를 프롬프트에서 실제로 제외하는지 2건

## 배경

CHAT-14 5차 수정("죽무 효과는?"이 전혀 다른 아이템 '절멸자'로 오검색된 사례) 확인 후 PM이 더 근본적인 대응이 가능한지 문의. `hybrid_search()`가 pgvector 코사인 거리를 순위 정렬에만 쓰고 값 자체는 버리는 구조라, top-k 안에만 들면 아무리 멀어도(=의미상 무관해도) 근거 문서로 채택돼 LLM이 그걸 사실처럼 답하는 구조적 위험이 있음을 실측으로 확인·설명 후 착수.

## 설계

### 1차 방어 — 거리 임계값(`_DOC_TYPE_MAX_DISTANCE`)

착수 전 doc_type별 실측(2026-08-09, HuggingFace BGE-M3 + pgvector 코사인 거리):

| doc_type | 정상 매칭 거리 | 비정상/애매 매칭 거리 | 임계값 적용 |
|---|---|---|---|
| item | 0.38~0.46 | 0.59(오매칭), 0.65(정답이지만 52위) | 적용(0.5) |
| augment | 0.38~0.42 | 0.51~0.53(애매한 질의) | 적용(0.5) |
| champion | 0.37~0.39(목록형), **0.507(정상적인 특정 이름 질의)** | - | **미적용**(정상 케이스가 item의 "나쁜 매칭" 구간과 겹침) |
| comp | 0.27(특정 조합명), **0.48~0.49(정상적인 "메타 추천" 질의)** | - | **미적용**(정상 케이스가 임계값 부근) |

item·augment만 정상/비정상 매칭이 실측상 확실히 분리돼 임계값(0.5)을 안전하게 둘 수 있었다. champion·comp·playstyle·item_build는 정상 케이스도 거리가 멀 수 있는 구조(목록형·일반 추천 질의)라 임계값을 걸면 정상 동작을 깨뜨릴 위험이 실측으로 확인돼 제외했다.

구현은 `_search_single_doc_type()`이 `_DOC_TYPE_MAX_DISTANCE.get(doc_type)`을 스스로 조회해 적용하도록 해 champion 등 정의 안 된 doc_type을 호출하는 기존 코드는 전혀 손대지 않았고(champion 배분 로직 등 기존 코드 100% 보존), comp_recommendation/augment_recommendation이 함께 쓰는 메인 검색문은 `_distance_within_threshold()`(OR 조합)로 doc_type별 다른 정책을 한 쿼리 안에서 처리한다.

### 2차 방어 — 이름 문자 겹침 비율(`filter_by_name_overlap`)

1차 방어 적용 후 실사용 검증 중 "광폭검 효과는?"(존재하지 않는 아이템)이 '포악한 절단검'과 거리 0.49로 임계값(0.5)을 통과해 여전히 확신에 찬 오답이 재현됨을 발견 — 정상 매칭(0.38~0.46)과 비정상 매칭(관측: 0.49)이 겹치는 회색지대가 실제로 존재해, 거리값 하나만으로는 완전히 분리되지 않는다는 구조적 한계를 확인(PM에게 설명, "다른 신호를 추가로 결합" 결정).

`filter_by_name_overlap()`을 결정론적 2차 신호로 추가: 후보 문서의 `doc_metadata["name"]`(공백 제외 고유 글자 집합)이 검색에 실제로 쓰인 질의 문자열과 몇 % 겹치는지(`_name_overlap_ratio`) 계산해 50% 미만이면 제외한다. item/augment doc_type에만 적용(1차 방어와 동일 범위 — champion/comp 등은 이름이 질의에 안 나오는 게 정상인 목록형·추천형 질의라 이 신호도 부적합).

이 신호가 안전한 이유: `SLANG_DICTIONARY`(CHAT-14)로 이미 정식 명칭이 치환된 뒤 검색되므로("죽무" → "죽음의 저항 효과는?") 정상 케이스는 질의 문자열에 정답 이름이 그대로 들어있어 겹침 비율이 거의 항상 1.0이다. 반대로 지어낸 이름은 실제 아이템명과 글자가 거의 안 겹친다(실측: "광폭검" vs "포악한 절단검" = 6글자 중 1글자만 겹침, 비율 0.167).

`generate_answer_stream()`(chat_stream.py)이 `search_fn` 결과에 이 필터를 한 번 더 적용한다(`hybrid_search()`의 공개 시그니처는 건드리지 않아 `search_fn` 콜러블 타입·기존 테스트의 mock 시그니처를 전혀 바꾸지 않음 — 저비용·저위험 배선).

## 자체 검증

- **backend pytest**: 신규 14건(거리 임계값 8건 — item/augment 근/원 문서 갈림, general_strategy에서 item만 제외되고 champion은 유지, item_recommendation 전체가 임계값 밖이어도 에러 없음, champion/comp 회귀 없음 확인 / `filter_by_name_overlap` 단위 4건 / `generate_answer_stream` 배선 2건) — **backend 전체 274/274 통과**, ruff check/format 통과.
- **실제 서버 재현(로컬=운영 DB)**:
  - "광폭검 효과는?"(존재하지 않는 아이템, 이번 TASK의 계기) → 수정 전 '포악한 절단검' 오답 → 수정 후 "'광폭검'의 효과에 대한 정보가 확인되지 않았다." 정상 응답.
  - "강철몽둥이 효과는?"(신규 지어낸 이름) → 같은 패턴으로 정상적으로 "정보 없음" 응답, 오답 없음.
  - "죽무 효과는?"(CHAT-14 5차 수정 대상) → 여전히 '죽음의 저항'으로 정확히 응답(회귀 없음, SLANG_DICTIONARY 경로가 이름 겹침 비율 1.0으로 자연스럽게 통과함을 확인).
  - "무한의 대검 효과는?", "보석 건틀릿 효과는?" 등 정상 질의도 그대로 정확한 수치 포함 응답(회귀 없음).
  - **주의(디버깅 메모)**: 1차 검증 때 "광폭검"이 여전히 오답으로 보여 당황했으나, 원인은 코드가 아니라 CHAT-08 캐시(이 질문을 수정 전에 이미 한 번 물어봐 오답이 캐시돼 있었음) — 해당 캐시 행을 삭제 후 재확인해 실제로는 수정이 정상 동작함을 확인. 앞으로 같은 방식으로 재검증할 때는 캐시 오염 가능성을 먼저 배제할 것(다음 세션을 위한 메모).

## 한계 및 후속 고려사항

- **완전한 해결이 아님**: 거리 임계값 + 이름 겹침 비율 2단 방어로 실측된 두 사례(죽무, 광폭검)는 해결했지만, 이론상 "실제 아이템 이름과 우연히 글자가 절반 이상 겹치는 지어낸 이름"이 나오면 여전히 뚫릴 수 있다(예: 진짜 아이템명의 일부를 그대로 포함한 오타). 결정론적 방어의 한계로, 발생 시 같은 패턴(글자 겹침 비율 조정 또는 추가 신호)으로 대응 가능.
- **champion/comp/item_build는 여전히 무방비**: 실측상 임계값 적용이 위험해 제외했으나, 이 doc_type들도 이론상 같은 유형의 오검색에 노출돼 있을 수 있다(다만 이 doc_type들은 "특정 고유명사 하나를 정확히 맞혀야 하는" 질의 패턴이 상대적으로 적어 실제 발생 빈도는 낮을 것으로 추정 — 확인된 사례는 아직 없음).
- **`filter_by_name_overlap`의 MIN_NAME_OVERLAP_RATIO(0.5)는 실측 2개 사례 기반의 보수적 추정치**로, 향후 더 많은 실사례가 쌓이면 조정이 필요할 수 있다.

## PM 확인 결과

2026-08-09 PM 승인, 커밋(d45ec9b). champion/comp/item_build doc_type의 잔여 위험은 발생 사례 없어 이번 범위에서 제외한 채로 승인.
