# schema.md — DB 스키마 경량 참조본

> 원본: 개발설계서 v1.6 5장. 실제 컬럼은 DATA-05~07 스파이크 결과에 따라 조정될 수 있음 — 조정 시 이 파일도 함께 갱신.
> 이 파일은 세션 시작 시 원본 .docx 대신 먼저 참조한다 (CLAUDE.md 2장). 상세 설계 근거가 필요하면 개발설계서 5장 원문 대조.

## 구조화 DB (PostgreSQL / Supabase)

| 테이블 | 주요 컬럼 | 설명 |
|---|---|---|
| `patches` | id, version, set_number, released_at, is_current, detected_at | 패치 버전 관리. `is_current`는 배치 전체 성공 시에만 트랜잭션 전환(DATA-13) |
| `champions` | id, patch_version, riot_champion_id, name_kr, name_en, cost | 패치별 챔피언 정보 |
| `traits` | id, patch_version, name_kr, name_en, tier_thresholds(jsonb) | 시너지 정보 |
| `champion_traits` | champion_id, trait_id | 챔피언-특성 매핑(junction) |
| `items` | id, patch_version, name_kr, name_en, item_type, riot_item_id, components(jsonb), stats(jsonb) | `riot_item_id`는 Match-V1 조인용 필수 외부키 |
| `augments` | id, patch_version, name_kr, name_en, tier, description, **is_legend_related**, riot_augment_id | `is_legend_related=true`면 win_rate 웹사이트·챗봇 양쪽에서 마스킹 필수 |
| `comps` | id, patch_version, name, tier_rank, rank_tier, avg_place, play_rate, win_rate(nullable), playstyle_text, **is_active**, updated_at | 메타 조합. `rank_tier`는 API-02 구현 중 PRD의 "랭크별 필터" 요구사항에 맞춰 추가(기본값 "all") — 실제 op.gg 랭크 구간 값은 DATA-05 스파이크 완료 후 재확정 필요. `is_active`(기본 true, DATA-17)는 op.gg 상위 10위 밖으로 밀려난 조합의 소프트 삭제 플래그 — 하드 삭제하면 comp_champions/comp_augments/match_analyses.matched_comp_id/meta_document_embeddings 참조가 끊겨 플래그만 끔(사이트 티어리스트는 API-02가 필터, 챗봇 RAG는 CHAT-18이 랭킹 후순위+캐비엇으로 처리) |
| `comp_champions` | comp_id, champion_id, is_carry, recommended_items(jsonb) | 조합-챔피언 매핑, 캐리 가중치 계산(PGA-04)의 기준 |
| `comp_augments` | comp_id, augment_id, priority | 조합-증강체 매핑 |
| `champion_item_builds` | id, champion_id, patch_version, item_combination(jsonb), play_rate, avg_place, win_rate | 챔피언별 아이템 빌드 |
| `match_analyses` | id, match_id, puuid, patch_version, comp_deviation, item_concentration, augment_synergy, matched_comp_id(FK comps.id, nullable), coaching_text, created_at | 사후 패인 분석 결과 캐시. 동일 match_id+puuid 재요청 시 재사용(PGA-03). matched_comp_id는 매칭되는 메타 조합이 없을 수 있어 nullable(DATA-03에서 확정) |

## 벡터 DB (pgvector)

| 테이블 | 주요 컬럼 | 설명 |
|---|---|---|
| `meta_document_embeddings` | id, patch_version, doc_type(comp/augment/item_build/playstyle), source_table, source_id, content_text, embedding(vector 1024), metadata(jsonb) | BGE-M3 임베딩. HNSW(vector_cosine_ops, m=16/ef_construction=64) 인덱스 + (patch_version,doc_type) btree 복합 인덱스. ivfflat 사용 금지(재빌드 필요, 패치 배치 구조와 불일치) |

## 로그 / KPI 테이블

| 테이블 | 주요 컬럼 | 설명 |
|---|---|---|
| `chat_logs` | id, session_id, patch_version, user_query, intent, retrieved_doc_ids(jsonb), answer, latency_ms, cold_start, created_at | 챗봇 Q&A·근거 로깅, RAGAS 평가 입력 |
| `link_click_events` | id, session_id, chat_log_id(nullable), target_page, clicked_at | 챗봇→웹사이트 전환율 계측 |
| `account_link_events` | id, riot_id_hash, region, event_type(link/analysis_request), match_id(nullable), latency_ms, created_at | 계정연동·분석요청 이벤트 |
| `patch_detection_runs` | id, triggered_at, patch_version_before, patch_version_after, duration_ms, status | 자동 패치 감지 실행 로그 |
| `ragas_eval_results` | id, eval_date, sample_query, faithfulness_score, answer_relevancy_score, patch_version | RAG 품질 주간 평가(Faithfulness·Answer Relevancy 2종만, Context Precision/Recall은 범위 제외) |
| `chat_answer_cache` | id, cache_key(unique), patch_version, answer, created_at | 챗봇 첫 턴 답변 캐시(v1.7 신설, Redis 대체). cache_key=hash(정규화 질문+patch_version). patch_version 불일치로 자연 무효화, 패치 배치 완료 후 이전 patch_version 행은 DATA-15가 DELETE. DATA-03에서 컬럼 확정(개발설계서 v1.7 4.6절 캐시 전략 표 기반, 컬럼 단위 명세는 원래 없어 DATA-03 구현 시 신규 확정) |
| `puuid_cache` | id, cache_key(unique), puuid, expires_at, created_at | Riot ID→PUUID 변환 결과 단기 캐시(v1.7 신설, Redis 대체). cache_key=hash(riot_id+region), expires_at=생성시점+1시간(Personal Key 레이트리밋 보호). DATA-03에서 컬럼 확정 |

## 정합성 규칙 (반드시 지킬 것)

- 모든 레코드에 `patch_version` 태깅 — 구버전 데이터 혼입 방지
- `items`/`augments`의 `riot_item_id`/`riot_augment_id`는 Match-V1 원본 키 조인용 필수 컬럼(없으면 PGA-05 아이템 집중도 계산 자체가 불가)
- `patches.is_current` 전환은 6개 op.gg 도구 호출 + 임베딩 생성이 전부 성공한 마지막 순간에만(DATA-13)
