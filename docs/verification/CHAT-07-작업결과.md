# CHAT-07 : 작업결과

- **TASK**: 웹사이트 링크 자동 삽입 구현
- **상태**: 완료(PM 승인 2026-08-04)
- **선행 TASK**: CHAT-06
- **근거 문서**: PRD 7-2·설계서 4.4, `docs/reference/glossary.md`(IA 화면 7개 URL)
- **변경 파일**: `backend/services/chat_links.py`(신규), `backend/services/chat_stream.py`(배선), `backend/tests/test_chat07_links.py`(신규)

## 결과 요약

- **URL 매핑**(IA v1.2 그대로, `docs/reference/glossary.md` "IA 화면 7개" 참고): 조합만 개별 상세 페이지(`/comps/{comp_id}`)가 있고, 아이템 빌드·증강체는 IA상 개별 상세 페이지가 없어 각각의 목록 페이지(`/items/builds`, `/augments`)로 연결.
- **`chat_links.py`**: `insert_links(answer_text, retrieved_docs)` — CHAT-06이 만든 인용 규칙(작은따옴표)을 그대로 재사용해, 인용된 이름이 검색 문서(`doc_metadata`의 `name`/`champion`)에 실재하면 마크다운 링크 `[이름](url)`로 치환. **검색 문서에 없는 이름(CHAT-06이 이미 경고 처리한 대상)은 링크를 만들 id 자체가 없으므로 그대로 둔다** — WBS의 "존재하지 않는 id 오탐 케이스"는 애초에 검증된 이름만 링크 대상으로 삼는 설계로 원천 차단.
- **`chat_stream.py`**: `generate_answer_stream()`에서 `postprocess_answer()`(CHAT-06) 다음 단계로 `insert_links()` 적용 후 스트리밍.

## 자체 검증

- pytest 8건 신규(backend 전체 **157/157 통과**), ruff check/format 통과
  - 조합 언급 → `/comps/{id}` 링크(comp/playstyle doc_type 둘 다 source_table=comps라 동일 URL)
  - 아이템 빌드·증강체 언급 → 각 목록 페이지 링크
  - 검색 문서에 없는 이름(오탐 케이스) → 링크 생성 안 됨, 원문 그대로 유지
  - 같은 이름 여러 번 언급 시 전부 치환, 검증된/미검증 이름 혼재 시 검증된 것만 치환
