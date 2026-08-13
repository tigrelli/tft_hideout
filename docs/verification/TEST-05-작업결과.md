# TEST-05 : 작업결과

- **TASK**: 배치 파이프라인 통합 테스트
- **상태**: 완료(PM 승인 2026-08-13)
- **선행 TASK**: DATA-05, DATA-08, DATA-09, DATA-10, DATA-11, DATA-12, DATA-13, DATA-14, DATA-15
- **완료 기준(DoD)**: 정상/중간실패 시나리오 모두 검증
- **변경 파일**:
  - `batch/tests/test_test05_pipeline_integration.py`(신규)

## 배경 및 범위

DATA-08~15는 각자 자기 단계만 단위 테스트한다. `run_patch_batch.py`가 이 단계들을 실제로 잇긴 하지만, `step_collect`/`step_embed` 내부에서 진짜 op.gg MCP·Community Dragon·HuggingFace 클라이언트를 직접 생성해 호출하는 구조라(정책상 실호출 자체를 못 씀) 자동화 테스트에서 그대로 실행할 수 없다. DATA-13 자신의 테스트(`test_data13_patch_transition.py`)도 이미 BatchStep 오케스트레이션의 성공/중간실패는 촘촘히 검증하지만, 손으로 만든 fake 스텝(`lambda: None`, 가짜 Champion 1개 직접 add)만 쓴다.

이번 TEST-05는 `run_patch_batch.py`의 `_build_steps()`와 같은 모양으로, **외부 I/O 경계(op.gg/cdragon 수집 결과, HuggingFace 임베딩 벡터)만 고정 fixture/fake로 바꾸고 나머지(정규화 DB 반영·임베딩 DB 반영·원자적 전환)는 전부 실제 구현을 그대로 실행**해, "실제 정규화·임베딩 결과물"이 원자적 전환과 맞물려도 DATA-13이 설계한 대로 동작하는지 확인했다.

## 구현

`batch/tests/test_test05_pipeline_integration.py` 신규 2건(DoD가 요구하는 정상/중간실패 각 1건):

1. **정상 시나리오** `test_normal_scenario_full_chain_promotes_patch_with_real_data` — `ensure_patch`(DATA-13) → 실제 `normalize.py` upsert 함수들(챔피언/특성/아이템/증강체/조합/조합-챔피언) → 실제 `embeddings.py`의 `collect_chunks`+`upsert_embeddings`(HuggingFace 호출 자리만 고정 벡터로 대체) → `run_batch_with_atomic_promotion`(DATA-13)까지 전체 체인이 성공하면, `is_current`가 새 패치로 전환되고 실제 챔피언/조합/임베딩 문서가 새 patch_version으로 정상 조회되는지 확인.
2. **중간실패 시나리오** `test_mid_failure_scenario_normalize_persists_but_patch_stays_old` — 정규화 단계까지는 실제로 성공·커밋되지만 임베딩 단계에서 실패(HuggingFace API 오류 흉내)하면, (a) `is_current`는 이전 패치를 그대로 유지하고, (b) 정규화 단계가 이미 커밋한 새 patch_version 태깅 데이터는 `patch_transition.py` docstring이 명시한 대로 DB에 남아있으며(의도된 동작), (c) 임베딩은 실행되지 못했으므로 새 패치용 `meta_document_embeddings`는 전혀 없어 챗봇(CHAT-02)이 반쯤 완성된 새 패치 데이터를 검색해 답하는 사고로 이어지지 않는지, (d) `patch_detection_runs`에 실패로 기록되는지까지 확인.

## 자체 검증

- 신규 2건 전체 통과, 회귀 없음: `batch` 전체 pytest **130/130** 통과(기존 128 + 신규 2).
- 첫 실행에 2건 모두 통과(버그 발견 없음, DATA-13의 원자적 전환 설계가 실제 정규화·임베딩 산출물과 맞물려도 정확히 동작함을 확인).
- `ruff check` / `ruff format` 통과.
- Docker(`docker-compose.test.yml`) test-db(5433)로 로컬에서 직접 실행.

## PM 확인 결과

2026-08-13 PM 승인.
