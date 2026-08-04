# DATA-11 : 작업결과

- **TASK**: 임베딩 생성 파이프라인 구현
- **상태**: 완료(PM 승인 2026-08-04)
- **선행 TASK**: DATA-04, DATA-10, SET-10
- **근거 문서**: 설계서 4.3·5.2
- **변경 파일**: `batch/embeddings.py`(신규), `batch/tests/test_data11_embeddings.py`(신규), `backend/alembic/versions/202608041100_data11_add_embeddings_unique_constraint.py`(신규 마이그레이션), `backend/db/models.py`(`MetaDocumentEmbedding` UniqueConstraint 추가), `backend/tests/test_data04_migration.py`(seed fixture가 새 제약과 충돌해 source_id를 서로 다르게 수정), `docs/reference/api-spec.md`(HF 신규 엔드포인트 기록)

## 착수 전 발견 1 — HF Inference API 엔드포인트가 바뀌어 있었음

레거시 `api-inference.huggingface.co`에 접속을 시도했더니 **DNS 자체가 뜨지 않았다**(HF가 라우터 방식으로 이전한 것으로 보임). 실호출로 신규 엔드포인트를 확인:

```
POST https://router.huggingface.co/hf-inference/models/BAAI/bge-m3/pipeline/feature-extraction
{"inputs": ["문장1", "문장2"]}
```
문자열 리스트를 보내면 원소가 1개여도 항상 `list[list[float]]`(배치) 형식으로 응답함을 확인(1024차원). `docs/reference/api-spec.md`에 기록.

## 착수 전 발견 2 — DATA-10과 동일한 upsert 제약 부재

`meta_document_embeddings`에도 (patch_version, doc_type, source_table, source_id) UNIQUE 제약이 없어 재수집 시 중복이 쌓일 수 있었음. DATA-10과 동일한 패턴으로 마이그레이션 추가(같은 소스 레코드라도 doc_type이 다르면 별개 문서이므로 doc_type도 키에 포함). 기존 DATA-04 테스트 fixture가 같은 (patch_version, doc_type, source_table, source_id)로 4행을 넣고 있어 제약과 충돌 — source_id를 행마다 다르게 부여하도록 수정(테스트 의도인 "코사인 거리 순서 검증"에는 영향 없음).

## 결과 요약

- **`HuggingFaceEmbeddingClient`**: BGE-M3 배치 임베딩 호출. 503(콜드스타트/모델 로딩) 시 재시도(policies.md 9번 무료 인프라 대응), JSON-RPC 유사 에러는 `EmbeddingError`로 통일
- **chunk 텍스트 생성**: `comp`(조합 전체: 티어·등수·승률·픽률·구성원·플레이스타일), `playstyle`(플레이스타일 텍스트만 별도 — CHAT-02 하이브리드 검색이 "리롤 덱"류 질의에 쓸 것을 염두에 둠), `augment`(이름·등급·설명 — augments 테이블엔 win_rate 자체가 없어 제외, DATA-10에서 이미 결정된 사실), `item_build`(챔피언·아이템 조합·승률·픽률·평균 등수)
- **`collect_chunks`**: 특정 patch_version의 comps/augments/champion_item_builds를 조회해 4종 chunk 목록 생성(임베딩 벡터는 별도 계산)
- **`upsert_embeddings`**: `ON CONFLICT (patch_version, doc_type, source_table, source_id) DO UPDATE`. 임베딩 차원이 1024가 아니면 즉시 `ValueError`(WBS 테스트 요구사항 "임베딩 차원 검증")
- 구현 중 실수 발견·수정: `models.MetaDocumentEmbedding`을 ORM 클래스로 직접 `insert()`하면 dict 키 `"metadata"`가 컬럼이 아니라 `DeclarativeBase.metadata`(상속된 레지스트리 속성)로 오인되어 깨짐 — `.__table__`로 Core 레벨 insert를 사용해 해결

## 자체 검증

- pytest 51/51 통과(기존 38 + 신규 13): chunk 텍스트 생성 순수 로직, HF 클라이언트(mock, 503 재시도 포함), 실제 마이그레이션 DB로 upsert·차원 검증
- `ruff check`/`ruff format --check` 통과(pre-commit 훅 기준으로 재확인 — 로컬 `.venv` ruff와 pre-commit 고정 버전 간 E402 판정이 달라 pre-commit 기준으로 맞춤)
- backend 회귀 100/100 통과
- **WBS DoD("임베딩 upsert 및 유사도 검색 성공") 실제 데이터로 검증**: DATA-10 스모크로 채운 실데이터(comps 10·augments 357) 중 30개 chunk를 실제 HF API로 임베딩(1024차원 확인) → upsert → 재실행해도 행 개수 그대로(중복 없음) → **실제 pgvector 코사인 유사도 검색**으로 조합 chunk 하나를 쿼리했더니 자기 자신이 1위, 같은 조합의 playstyle chunk가 2위, 비슷한 조합이 3위로 나옴(의미적으로 타당한 순서) — 유사도 검색 정상 동작 확인

## 다음 세션을 위한 메모

- 이번 TASK는 "chunk 생성 + 임베딩 + upsert 함수"까지다. 전체 배치 오케스트레이션(패치 감지→수집→정규화→임베딩→원자적 전환)을 하나로 잇는 최상위 스크립트는 DATA-12(패치 감지)·DATA-13(원자적 전환) 이후 별도로 묶일 예정
- 무료 티어 호출량을 고려해 실제 스모크 검증은 30개 chunk만 임베딩했다(전체 377개+는 실제 배치 실행 시 처리) — HF 무료 티어 레이트리밋에 유의
- `item_build` doc_type은 이번 스모크에서 champion_item_builds 데이터가 없어 실제 확인은 못 했으나(DATA-10 스모크가 그 테이블은 안 채움), 함수 자체는 pytest로 검증됨
