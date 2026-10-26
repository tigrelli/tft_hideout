# CHAT-36 : 작업결과

- **TASK**: HF 임베딩 의존 제거 및 챗봇 검색 텍스트 기반(pg_trgm) 전환
- **상태**: 자체검증 완료, PM 확인 대기(2026-10-18) — 커밋·push 전
- **선행 TASK**: CHAT-02, DATA-11
- **근거**: 진행현황.md 2026-10-18 "운영 장애 조사" 이력, PM 결정(B안: HF를 완전히 들어내고 텍스트 검색으로 교체)
- **변경 파일**
  - backend: `alembic/versions/202610181200_chat36_nullable_embedding_add_pg_trgm.py`(신규), `db/models.py`(embedding nullable), `services/hybrid_search.py`(검색 로직 교체), `services/chat_stream.py`·`routers/chat.py`(`embed_fn` 제거), `services/embedding_client.py`(**삭제**)
  - batch: `embeddings.py`(HF 클라이언트 삭제, `upsert_embeddings`→`upsert_documents`), `run_patch_batch.py`(`step_embed`→`step_index`, 500청크 상한 제거), `comps_refresh.py`(HF 호출 제거), `patch_transition.py`(실패 시 traceback 출력)
  - 설정: `.github/workflows/patch-detection.yml`·`.env.example`에서 `HUGGINGFACE_API_KEY` 제거
  - 테스트: backend `test_chat02_hybrid_search.py`(전면 재작성), `test_chat36_migration.py`(신규), `test_test03_*`·`test_chat05/08/09/11/17/27/29/30/32/33_*`·`test_test06_*`(`embed_fn` 인자 제거) / batch `test_data11_embeddings.py`, `test_data18_comps_refresh.py`, `test_test05_pipeline_integration.py`, `test_data13_patch_transition.py`(신규 1건)
  - 문서: `CLAUDE.md`(v1.15), `docs/reference/{schema,api-spec,policies,glossary}.md`, `batch/README.md`, `TFT_Hideout_WBS.xlsx`(CHAT-36 행), `진행현황.md`

## 사고 경위(요약)

1. 패치 18.4가 10/7부터 매일 자동 감지되지만 `patch_detection_runs`에 매번 `failed`. 수집·정규화 결과(챔피언 74·조합 16 등)는 정상 적재됐고 18.4 임베딩만 0건이었음 → 임베딩 단계 실패.
2. HF API 직접 호출 결과 `402 PrepaidCreditsRequired`. HF billing API(`/api/settings/billing/usage-v2`)상 사용량은 8월 $0.0138, 9월 $0.0027로 매우 적었고, 10/6까지 매일 정상 과금되다 10/7부터 0건, `includedNanoUsd=0`.
3. **원인은 사용량이 아니라 HF 정책 변경**: 2026-10-07부로 무료 계정의 월간 Inference Providers 크레딧($0.10)이 폐지됨(hub-docs PR #2865). 무료 한도가 0이 되어 아무리 적게 써도 거절된다.
4. 챗봇 질문 임베딩도 같은 API를 써서, 추천 계열 4개 의도(comp/item/augment/general_strategy)도 함께 불능 상태였다.
5. `patch_transition.py`가 단계 예외를 출력 없이 삼켜 Actions 로그만으로는 원인을 알 수 없었다.

## 구현

### 1. 검색: pgvector 코사인 거리 → pg_trgm 텍스트 유사도(`hybrid_search.py`)

관련도 = max(이름 점수, 본문 점수 × 0.5).

- **이름 점수(주 신호)**: `word_similarity(문서 이름 키, 질의)`. 이름 키는 metadata의 `name`·`champion`, 그리고 목록 키 `champions`(조합 구성원)·`items`(빌드 아이템, 가중치 0.9). 질문 대부분이 고유명사를 포함하고 줄임말은 CHAT-31 사전이 먼저 정식 명칭으로 바꿔주므로 가장 정확한 신호다.
- **본문 점수(보조 신호)**: `word_similarity(질의, content_text)`. "효과는", "추천" 같은 흔한 단어 때문에 노이즈가 커서(실측: 존재하지 않는 "광폭검 효과는?"도 0.50) 절반만 반영한다. "3코스트 챔피언은?"처럼 이름 없이 속성을 묻는 질문에 쓰인다.

기존 정책은 그대로 유지했다.

| 정책 | 유지 방식 |
|---|---|
| CHAT-15 item/augment 오검색 차단 | 거리 임계값 0.5 → 관련도 최소값 0.6(`NAME_HIT_MIN_SCORE`). `filter_by_name_overlap` 후처리도 그대로 |
| CHAT-18 활성 조합 우선 | 정렬 1순위 그대로 |
| 티어 우선 정렬(2026-08-07) | 그대로. 단 아래 새 규칙이 티어보다 앞선다 |
| general_strategy doc_type 균등 배분, champion 20개 고정 | 그대로 |
| item_build 챔피언당 2개 상한 | 파티션 정렬 기준만 관련도로 교체 |

**새 정렬 규칙(이름 지목 우선)**: 정렬 순서는 활성 여부 → **관련도 0.6 이상(이름 지목) 여부** → 티어 → 관련도 → id다. 이름을 지목하지 않는 일반 질의("요즘 메타 조합?")는 모든 문서가 0.6 미만이라 기존과 똑같이 티어 순이다. 이 규칙을 넣은 이유는, 벡터 시절에는 티어가 거리보다 앞서 있어 top_k 밖의 낮은 티어 조합을 이름으로 물어도 결과에 안 나올 수 있었기 때문이다.

**임계값 0.6의 근거(2026-10-18 실측)**: 정답 이름은 1.00, 조사가 붙은 이름("아리를")은 약 0.67, 글자 일부만 겹치는 다른 아이템("보석 건틀릿 효과는?" 대 '공허 건틀릿')은 0.57이었다.

### 2. 배치: 텍스트만 적재

- `upsert_documents()`: chunk 텍스트·메타데이터만 upsert한다(embedding NULL). 기존 행을 갱신할 때도 embedding을 NULL로 비워, 바뀐 텍스트와 어긋난 옛 벡터가 남지 않게 했다.
- 실행당 500청크 상한을 제거했다. 외부 호출 비용이 없어졌기 때문이다. **이 상한 때문에 18.x 패치에는 champion/item_build 문서가 0건이었다**(18.3 문서 508건이 전부 comp/playstyle/augment/item). 18.4부터는 item_build 650건이 함께 들어간다.
- `patch_transition.py`: 단계 실패 시 `배치 단계 실패: step=... patch_version=...`과 traceback을 출력한다. 크론은 계속 살아 있다.

### 3. 마이그레이션

`CREATE EXTENSION IF NOT EXISTS pg_trgm` + `embedding` NOT NULL 해제. downgrade 시 벡터 없는 행을 지우고 NOT NULL을 복원한다. 기존 벡터 값과 HNSW 인덱스는 이력 보존용으로 남겼다.

## 자체 검증

### 자동화 테스트(로컬 Docker `pgvector/pgvector:pg16`)

```
backend: 470 passed, 1 warning  (변경 전 466 — HF 클라이언트 테스트 삭제, 텍스트 검색·마이그레이션 테스트 추가)
batch:   140 passed             (변경 전 142 — HF 클라이언트·차원 검증 7건 삭제, upsert_documents 4건 + 실패 로그 1건 추가)
ruff check / ruff format: backend·batch 모두 클린
```

**변이 확인**: 새 검색 테스트가 실제로 동작을 검증하는지 보려고 구현을 일부러 망가뜨려 돌려봤다. 4가지 변이 모두 테스트가 잡아냈다. 확인 후 원복했다.

| 변이 | 실패한 테스트 수 |
|---|---|
| 이름 지목 우선 정렬 제거 | 3 |
| item/augment 임계값 제거 | 4 |
| 목록 키(구성원·아이템) 점수 제거 | 2 |
| 본문 점수 제거 | 1 |

### 실데이터 검증(운영 18.4 청크 1,478건, 로컬 검증 DB)

운영 DB를 **읽기 전용**으로 조회해 `collect_chunks("18.4")`를 실행했다. 결과(item_build 650, item 511, augment 285, comp 16, playstyle 16, champion 0)를 로컬 DB에 적재하고 실제 `hybrid_search`로 질의했다. 검색 응답 시간은 4~46ms였다.

| 질의 | 결과 |
|---|---|
| 요즘 메타 조합 추천해줘 | OP 2개 → S 2개 → A 순(티어 우선 유지) ✅ |
| 아지르 들어가는 덱 알려줘 | 처형자 아지르(조합명), 햇빛 유나라(구성원에 아지르) 순 ✅ |
| 아리 아이템 뭐 가요? | 아리 빌드 2개가 1·2위 ✅ |
| 보석 건틀릿 효과랑 누가 쓰는지 알려줘 | 보석 건틀릿·찬란한 보석 건틀릿 설명 + 보석 건틀릿이 들어간 빌드들 ✅ |
| 광폭검 효과는?(존재하지 않음) | item 문서 0건(오검색 차단) ✅ |
| 고독한 방패 증강 어때? | 정확히 1건 ✅ |
| 흥청망청 좋아? / 철갑탄 효과 알려줘 | 해당 증강·아이템 포함 ✅ |
| 골드 많이 주는 증강 추천 | 0건 — 이름 없는 서술형 증강 질문. 기존에도 `filter_by_name_overlap`이 걸러내던 것과 동일 |
| 달빛 세주아니 조합 어때? | ⚠️ 해당 조합이 안 나옴 — 아래 PM 확인 사항 1 |

## PM 확인 사항

1. **비활성 조합을 이름으로 물을 때**: '달빛 세주아니'는 op.gg 상위 10위 밖으로 밀려난 비활성 조합이라, CHAT-18 정책("비활성은 항상 활성 뒤")에 따라 이름을 지목해도 활성 조합에 밀려 결과에 나오지 않는다. 벡터 검색 시절에도 같았던 동작이라 이번 변경의 회귀는 아니다. 정책은 그대로 두었다. 다른 방안은 "질문이 조합명을 직접 지목하면 비활성이어도 포함"하는 것이다. 이 경우 문서에 이미 "상위 10위 밖" 주의 문구가 있어 LLM이 캐비엇을 단다. 원하시면 후속으로 반영하겠다.
2. **Set 18 champion 문서 0건(별도 결함, 이번 범위 밖)**: Set 18 챔피언 ID가 `DA_18_*`, `DA_Amumu18`, `DA_Lux18_Blossom` 등 혼합 형식이다. 그래서 `is_real_champion()`(`TFT{세트}_` 접두어 검사)을 하나도 통과하지 못해 "3코스트 챔피언은?" 같은 질문의 근거 문서가 생성되지 않는다. 검색 방식과 무관하게 Set 18부터 생긴 문제라 별도 TASK 등록을 제안한다.
3. **Supabase Postgres 에러(시간당 112건)**: 해당 시간대에 앱 연결이 전혀 없고 Supabase 내부 컴포넌트만 접속 중이었다. 원인 특정에는 Logs Explorer의 에러 원문이 필요하다(진행현황.md 2026-10-18 이력의 쿼리 참고).
4. **근거 문서 원본**: 개발설계서 docx의 임베딩·벡터 검색 관련 절은 아직 갱신하지 않았다. 참조본(`docs/reference/*.md`)과 CLAUDE.md만 갱신했다.

## 배포 시 참고(승인 후)

- main 머지 → Render 빌드의 `alembic upgrade head`가 `pg_trgm` 설치 + 컬럼 변경을 자동 적용한다. 확장 설치가 실패하면 빌드가 중단되고 기존 버전이 계속 서비스된다.
- 배포 직후 GitHub Actions `Patch Detection & Batch Collection`을 **수동 실행(workflow_dispatch)**하면 다음 날 03:00 KST를 기다리지 않고 18.4가 승격된다. 마이그레이션 전에 배치가 먼저 돌면 NULL 적재가 실패해 승격이 안 될 뿐 데이터는 안전하다. 이 경우 다음 실행에서 자동으로 다시 시도된다.
- GitHub Secrets·Render 환경변수의 `HUGGINGFACE_API_KEY`는 더 이상 쓰지 않으므로 삭제해도 된다(선택).
- 18.3에 남아 있는 텍스트도 그대로 검색되므로, 배포 직후 승격 전까지도 챗봇은 18.3 기준으로 동작한다.
