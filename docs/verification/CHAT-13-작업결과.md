# CHAT-13 : 작업결과

- **TASK**: 아이템 이름 근거검증 인식 개선
- **상태**: 완료(PM 승인 2026-08-08)
- **선행 TASK**: CHAT-06, CHAT-07, DATA-11
- **근거 문서**: PM 제보(2026-08-08), `docs/verification/CHAT-12-작업결과.md`
- **변경 파일**:
  - `batch/embeddings.py`(수정) — `item_build` 문서 `doc_metadata`에 `champion`·`items` 외 `champion_id`(2차 수정분) 추가
  - `batch/tests/test_data11_embeddings.py`(수정, 1건 추가/갱신)
  - `backend/services/chat_postprocessing.py`(수정) — `_known_names()`가 `items` 같은 목록형 메타데이터 키도 인식하도록 확장
  - `backend/services/chat_links.py`(수정) — `_name_to_url()`이 `champion_id`가 있으면 필터 링크를 만들도록 변경(2차 수정분), 아이템 이름은 링크 대상에서 제외(2차 수정분), 목록 항목 맨 앞 챔피언명을 인용 누락 시에도 인식하는 보정 로직 추가(2차 수정분)
  - `backend/tests/test_chat13_item_grounding.py`(신규 5건 + 2차 수정 4건 추가/교체, 총 9건)
  - `TFT_Hideout_WBS.xlsx`·`진행현황.md`(신규 TASK 등록)

## 설계

- **원인**: `verify_grounding()`의 `_known_names()`는 검색 문서 `doc_metadata`의 `name`/`champion` 키만 "알려진 이름"으로 인정했다. `item_build` 문서 메타데이터는 `{"champion": "..."}`뿐이라 아이템 이름 자체가 아예 없었고, 8번 규칙(고유명사는 작은따옴표로 인용)에 따라 아이템 이름을 정상적으로 인용한 답변도 검증을 통과할 방법이 구조적으로 없었다(CHAT-12 작업결과 "PM 질문 답변" 절 참고). `insert_links()`도 같은 이유로 아이템 이름을 절대 링크로 바꿀 수 없었다.
- **수정**: `batch/embeddings.py`의 `item_build` 청크 생성부는 이미 `item_names`(표시용 아이템 이름 리스트)를 로컬 변수로 갖고 있어, 이를 그대로 `doc_metadata["items"]`에 실었다(추가 조회 없음). `_known_names()`/`_name_to_url()` 양쪽에 "목록형 메타데이터 키"(`items`) 처리를 추가해, 단일 문자열 키(`name`/`champion`)와 별개로 리스트를 순회하며 각 아이템 이름을 인식하게 했다. 근거 없는 이름(진짜 할루시네이션)은 여전히 걸러진다 — CHAT-12 검증 중 실제로 나온 `'베이'`(문서에 없는 이름) 같은 케이스는 이 변경 후에도 계속 경고가 붙는다(테스트로 확인).
- **범위**: 아이템 이름에 개별 상세 페이지가 없어(IA 기준) 링크는 챔피언과 동일하게 `/items/builds` 목록 페이지로 연결된다(`_link_target`의 기존 `item_build` doc_type 처리 그대로 재사용, 신규 URL 규칙 없음).

## 설계 — PM 재검증 중 발견한 문제 2건·수정 (2026-08-08)

CHAT-12·CHAT-13을 로컬 서버로 직접 확인하던 PM이 "무한의 대검 사용하는 챔피언은?" 질문에서 두 가지를 제보했다: (1) 답변 맨 앞의 아이템 이름("무한의 대검")이 링크로 걸려 있는데 눌러도 당연히 챔피언이 선택 안 됨(원인: 위 1차 수정에서 아이템 이름을 링크 대상에 포함시켰던 것 — 그라운딩 인식과 링크 삽입을 같은 목록으로 취급한 설계 실수), (2) 목록 안 챔피언 이름을 클릭해도 URL이 전혀 안 바뀜(원인: item_build 문서의 챔피언 링크가 애초에 `champion_id` 없이 항상 필터 없는 `/items/builds`로만 갔던 기존 버그 + 목록 항목에서 모델이 챔피언명을 작은따옴표로 인용하지 않아 아예 링크 자체가 안 생긴 경우가 섞여 있었음).

**수정**:
1. `_name_to_url()`에서 아이템 이름 매핑을 완전히 제거 — 아이템 이름은 `_known_names()`(근거검증)에서만 "알려진 이름"으로 남고 링크 대상에서는 빠진다.
2. `item_build` 문서 `doc_metadata`에 `champion_id`를 추가(`batch/embeddings.py`, 이미 로컬 변수 `build.champion_id`가 있어 추가 조회 없음)하고, `_name_to_url()`이 `champion_id`가 있으면 `/items/builds?champion_id={id}`(필터 링크)를, 없으면(구 데이터) 기존처럼 `/items/builds`를 반환하도록 분기했다. 부수 효과: `extract_champion_ids_from_answer()`(CHAT-05 후속턴 구조화 조회)도 item_build 기반 챔피언 링크에서 champion_id를 뽑을 수 있게 돼 더 정확해진다.
3. 모델이 목록 항목에서 인용을 빠뜨려도 링크가 생기도록, `insert_links()`에 2차 정규식 패스(`_LIST_ITEM_LEADING_NAME_PATTERN`)를 추가했다 — CHAT-12가 강제하는 `- 챔피언명: 아이템...` 형식에서 줄 맨 앞(콜론 앞)은 항상 챔피언명이 오는 구조적으로 안전한 위치라, 인용 여부와 무관하게 그 위치의 텍스트가 알려진 챔피언명과 일치하면 링크로 바꾼다(이미 인용 패스에서 링크된 항목은 `[`로 시작해 건드리지 않음).

**재검증(개발 DB 백필 후 실제 로컬 서버)**: `champion_id`도 채우는 2차 백필(630행) 실행 후, 실제 "무한의 대검 사용하는 챔피언은?" 질문을 다시 보내 확인 — 답변에 링크가 총 15개(모두 챔피언, 아이템 링크 0개) 생성되었고, 목록의 챔피언 15명 **전원**이 `/items/builds?champion_id={id}` 링크로 렌더링됨(모델이 일부는 인용, 일부는 인용을 빠뜨렸지만 2차 정규식 패스가 전부 보정). 첫 번째 링크를 실제로 클릭해 `/items/builds?champion_id=56`으로 이동 후 스크린샷으로 "챔피언 선택" 필드에 실제로 "이즈리얼"이 선택되고 그 챔피언의 빌드 목록이 표시되는 것까지 확인.

## 자체 검증

- **batch pytest**: `test_collect_chunks_item_build_metadata_includes_item_names` 신규(item_build 청크 metadata에 `items`·`champion_id`가 채워지는지, 2차 수정으로 `champion_id` 검증 추가) — **batch 전체 106/106 통과**(무회귀), `ruff check`/`ruff format --check` 통과.
- **backend pytest**: `test_chat13_item_grounding.py` 총 9건 — 1차(아이템 이름 인용이 경고 없이 통과 3건, 알 수 없는 이름은 여전히 경고 1건) + 2차(아이템 이름은 인용해도 링크 안 됨, 알 수 없는 이름은 여전히 링크 안 됨, `champion_id` 있으면 필터 링크·없으면 하위호환 미필터 링크, 목록 항목 맨 앞 챔피언명이 인용 없이도 링크로 보정, 보정 로직이 콜론 뒤 아이템까지 잘못 링크하지 않는지) — **backend 전체 251/251 통과**(기존 CHAT-06/07 테스트 무수정 통과로 무회귀 확인), `ruff check`/`ruff format --check` 통과.
- **DB 백필 2회 완료(2026-08-08, PM 요청)**: (1) `items` 목록 백필(630행), (2) `champion_id` 백필(630행) — 둘 다 `champion_item_builds` 조인만으로 `doc_metadata`만 UPDATE하는 1회성 스크립트(레포 미커밋, 외부 API 호출 없음, content_text·임베딩 벡터 미변경). 실제 로컬 서버로 최종 재검증: "무한의 대검 사용하는 챔피언은?" 질문에서 아이템 이름(무한의 대검)은 링크 없이 텍스트로만 표시되고, 목록의 챔피언 15명 전원이 `/items/builds?champion_id={id}` 링크로 렌더링됨(모델의 인용 누락도 2차 정규식 패스로 보정됨을 실제 응답에서 확인). 링크 클릭 → 실제로 해당 챔피언이 선택된 상태로 아이템 빌드 목록이 표시되는 것을 스크린샷으로 확인. **정정(PM 확인)**: 이 백필은 policies.md 12번에 명시된 대로 개발·운영 겸용 단일 Supabase DB에 실행된 것이라 곧바로 운영에도 반영됐다 — 아래·CHAT-12 문서의 "개발 Supabase DB"/"개발 DB" 표현은 부정확했다(별도 DB 없음, production API와 직접 대조해 재확인).

## PM 확인 결과

2026-08-08 PM 승인. 1차 수정(아이템 이름 근거검증 인식) 확인 중 링크 관련 회귀 2건(아이템 이름이 링크됨, 챔피언 링크가 champion_id 필터 없음)을 제보받아 2차 수정으로 함께 반영, 실제 서버 재검증 후 커밋·push 진행.
