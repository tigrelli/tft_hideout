# CHAT-18 : 작업결과

- **TASK**: 비활성 조합(is_active=false) 근거검증·랭킹 정합성 개선 + comp 근거검증 오탐 수정
- **상태**: 완료(PM 승인 2026-08-12)
- **선행 TASK**: -(CHAT-17 실사용 검증 중 PM 제보로 신설)
- **근거 문서**: PM 제보(2026-08-12), `docs/reference/policies.md` 14번 인접 정책(RAG 근거 원칙, 5번)
- **변경 파일**: `batch/embeddings.py`, `backend/services/prompt_assembly.py`, `backend/services/hybrid_search.py`, `backend/services/chat_postprocessing.py`, `backend/tests/test_chat02_hybrid_search.py`, `backend/tests/test_chat03_prompt_assembly.py`, `backend/tests/test_chat06_postprocessing.py`, `batch/tests/test_data11_embeddings.py`, `frontend/src/components/chat-widget/chat-message-list.tsx`

## 문제 재확인

CHAT-17 실사용 검증 중 PM이 두 가지를 제보:

1. **링크 오버플로우**: 챗봇 답변의 웹검색 출처 URL이 채팅 버블 밖으로 삐져나옴
2. **비활성 조합 오답**: "룰루는 어떤덱으로?"에 챗봇이 "별돌보미 룰루"(id=24)를 티어 S로 추천했는데, 이 조합은 `comps.is_active=false`(DATA-17 소프트 삭제 — op.gg 상위 10위에서 밀려나 사이트 티어리스트엔 안 보임)라 실제로는 최신 메타가 아님

## 원인·수정

### 1. 링크 오버플로우
- **원인**: CHAT-17이 `(출처: https://...)` 원문 URL 형식으로 답변하도록 지시했는데, 프론트는 `[텍스트](URL)` 마크다운만 짧은 링크로 변환. 채팅 버블에도 `break-words`류 CSS가 없어 wrap이 안 됨.
- **수정**: `WEB_SEARCH_SYSTEM_PROMPT` 규칙 2를 `[출처](URL)` 마크다운 형식으로 변경(기존 프론트 `LINK_PATTERN`이 그대로 처리, 프론트 코드 변경 불필요). `chat-message-list.tsx`의 봇/유저 버블에 `wrap-break-word` 추가(형식 무관 방어).
- **부수 발견**: 위 수정 검증 중, CHAT-17이 `postprocess_answer()`(CHAT-06 `verify_grounding`, 작은따옴표 인용을 `retrieved_docs` 메타데이터와 대조)를 그대로 재사용해 웹검색 답변이 고유명사를 인용할 때마다(`retrieved_docs=[]`라 항상 "알려진 이름" 0개) 오탐 경고가 붙는 것을 발견. `_generate_web_search_answer()`가 `postprocess_answer()` 대신 `strip_internal_doc_marker_leak`+`mask_augment_win_rate_leak`만 직접 호출하도록 분리(URL 기반 `verify_web_citation`이 이 경로의 근거검증을 전담).

### 2. 비활성 조합 오답 (본 TASK 핵심)
- **원인**: (a) `batch/embeddings.py`의 `comp_chunk_text()`/`playstyle_chunk_text()`가 `comp.is_active`를 전혀 반영하지 않아, 상위 10위 밖으로 밀려나 통계가 갱신을 멈춘 조합도 매 배치마다 "티어 S" 같은 현재형 문구로 재임베딩됨 (b) `hybrid_search.py`의 정렬이 `tier_rank`만 1차 기준으로 써서, 얼어붙은 옛 "S"가 실제로 활성인 "A"보다 검색 랭킹에서 앞섬
- **수정**:
  - `comp_chunk_text()`/`playstyle_chunk_text()`: `is_active=false`면 "현재 op.gg 상위 10위 밖으로 밀려났습니다 — 수치는 마지막 상위권 시점 기준" 문구를 본문에 추가, `metadata`에도 `is_active` 포함
  - `SYSTEM_PROMPT_BASE` 11번 규칙 신설: 문서에 그 문구가 있으면 티어/수치를 현재형으로 단정하지 말고 캐비엇을 밝히도록 지시
  - `hybrid_search.py`: `_ACTIVE_PRIORITY`(is_active=false만 우선순위 1, 나머지 0 — `is_active` 키 없는 doc_type은 영향 없음)를 `_TIER_RANK_PRIORITY`보다 앞선 1차 정렬 기준으로 추가해, 비활성 조합이 활성 조합보다 항상 뒤로 밀리게 함
- **부수 발견(CHAT-13과 동일한 구조적 문제)**: 랭킹 수정 검증 중 comp 답변이 개별 챔피언 이름을 정상 인용(8번 규칙)해도 `verify_grounding()`이 오탐 경고를 붙이는 것을 발견 — comp/playstyle `metadata`에 조합 이름만 있고 구성 챔피언 이름이 없었음(item_build는 CHAT-13에서 이미 "items" 키로 고쳤으나 comp는 누락돼 있었음). `metadata`에 `"champions"`(구성 챔피언 이름 목록) 키 추가, `chat_postprocessing._NAME_LIST_METADATA_KEYS`에 `"champions"` 추가.

## 자체 검증

- pytest 신규: hybrid_search 랭킹 1건, prompt_assembly 캐비엇 규칙 1건, comp_chunk_text/playstyle_chunk_text 상태표시 3건, comp metadata champions 1건(batch), verify_grounding champions 1건, 웹검색 오탐 회귀 1건 — **backend 전체 300/300, batch 전체 128/128 통과**, ruff check/format 양쪽 클린
- **운영 DB 재임베딩 2회 실행**(`refresh_comps()`를 실제 op.gg+HuggingFace로 직접 호출, DATA-18 정기 재수집과 동일한 정상 동작 — 1차: is_active 문구+메타데이터 backfill, 2차: champions 메타데이터 backfill): 16개 조합 × 2청크 = 32건씩 재임베딩 완료
- **로컬 실서버 종단 검증**(PM 제보 원문 그대로 재현):
  - "룰루는 어떤덱으로?" → 이전엔 비활성 "별돌보미 룰루"(S)를 추천했으나, 수정 후 **활성 "복제자 룰루"(A)**를 정상 추천, 오탐 경고 없이 깔끔한 답변 확인(과거 캐시된 답변 1건은 수정 전 데이터라 별도 삭제 후 재확인)
  - 웹검색 출처 링크 → Playwright 스크린샷으로 짧은 "출처" 링크 정상 렌더링, 가로 오버플로우 없음(`scrollWidth <= clientWidth`) 확인
  - 회귀 확인: "지금 메타에서 강한 조합 추천해줘"(활성 조합만 있는 정상 케이스) 정상 응답, 영향 없음

## 한계

- CHAT-08 캐시는 patch_version 변경 시에만 무효화되고, 이번처럼 같은 패치 안에서 RAG 코퍼스(임베딩 내용)만 갱신되는 경우엔 무효화되지 않는다 — 이번엔 문제가 된 캐시 1건만 수동 삭제했다(구조적 해결은 이번 범위 밖, 재발 시 참고할 것).
- `_ACTIVE_PRIORITY`는 comp/playstyle에만 실질적으로 영향을 준다(다른 doc_type엔 `is_active` 메타데이터 자체가 없어 항상 else_ 취급).

## 2026-08-12 추가 수정 — 웹검색 답변의 "[웹 검색 결과]" 마커 누출(PM 승인)

운영 실사용 검증 중 PM이 "[웹 검색 결과]를 바탕으로 살펴보면..."처럼 프롬프트 내부 구획 표시가 답변에 그대로 노출되는 것을 제보. 2026-08-07에 RAG 경로의 `[검색된 문서]` 누출을 막았던 `strip_internal_doc_marker_leak()`가 단일 마커만 처리해 CHAT-17 웹검색 경로의 `[웹 검색 결과]` 마커는 방어하지 못했던 것으로 확인 — 마커를 튜플(`_INTERNAL_DOC_MARKERS`)로 바꿔 두 경로 모두 방어하도록 수정.

- pytest 신규 1건, backend 301/301 통과, ruff 클린
- 로컬 실서버로 동일 유형 질문("TFT 이번 시즌 공식 행사 알려줘") 재현 — 마커 누출 없이 정상 답변 확인
- 커밋: `36eccde`
