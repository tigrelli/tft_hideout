# CHAT-02 : 작업결과

- **TASK**: 하이브리드 검색 구현(SQL 필터 + pgvector top-k 코사인 검색)
- **상태**: 완료(PM 승인 2026-08-04)
- **선행 TASK**: DATA-11, CHAT-01
- **근거 문서**: PRD 9-4·설계서 4.4, `docs/reference/glossary.md`(챗봇 의도 분류 4종)
- **변경 파일**: `backend/services/embedding_client.py`(신규), `backend/services/hybrid_search.py`(신규), `backend/requirements.txt`(httpx 추가), `backend/tests/test_chat02_hybrid_search.py`(신규)

## 결과 요약

- **`services/embedding_client.py`**: 실시간 사용자 질문을 BGE-M3로 임베딩하는 `HuggingFaceEmbeddingClient`. `batch/embeddings.py`와 로직이 동일하지만, Render 배포 backend는 `rootDir: backend`라 batch/ 코드를 임포트할 수 없어(render.yaml) 필요한 부분만 복제.
- **`services/hybrid_search.py`**: `hybrid_search(session, intent, patch_version, query_embedding, top_k=5)` — glossary.md 4종 의도별 `doc_type` 매핑(조합 추천→comp/playstyle, 아이템 추천→item_build, 증강체 추천→augment, 일반 전략→전체)으로 먼저 SQL 필터(`patch_version` + `doc_type IN (...)`), 그 안에서 `MetaDocumentEmbedding.embedding.cosine_distance()`로 top-k 정렬(WBS "SQL 필터 + pgvector top-k" 그대로).
- CHAT-01의 의도 분류 결과(`INTENT_*` 상수)를 그대로 입력으로 받아 CHAT-03(프롬프트 조립)으로 이어질 자리를 마련(이번 TASK는 검색 함수 자체만 구현, 엔드포인트 배선은 CHAT-03/05에서 진행 — API-09와 동일한 "뼈대 우선" 패턴).

## 자체 검증

- pytest 10건 신규(backend 전체 **121/121 통과**), ruff check/format 통과, 외부 HF API 미호출(mock transport, policies.md 10.2/11 정책)
  - `HuggingFaceEmbeddingClient`: 정상 응답, 503 콜드스타트 재시도 후 성공, 재시도 소진 시 예외 (DATA-11과 동일 케이스)
  - `hybrid_search`: 의도 4종 각각 올바른 `doc_type`만 검색되는지, `patch_version` 필터로 이전 패치 문서가 제외되는지, 코사인 거리 오름차순 정렬(동일 방향 벡터가 직교 벡터보다 먼저), `top_k` 제한 동작
