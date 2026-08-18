# DATA-23 : 작업결과 (PM 확인 요청 중)

- **TASK**: 자체 티어 스코어링(DATA-21)을 opScore 기반 상대임계값 간격 클러스터링으로 재설계
- **계기**: TEST-11 카테고리 G 논의 중 "op.gg MCP top-10 표본만으로 계산한 승률 기반 OP/S 티어링이 적절한지" PM 검토 요청(2026-08-18) → 실측 결과 DATA-21의 avg_place·win_rate 두 축 순위합 방식이 표본 크기·픽률을 반영하지 않아 최소표본·최저픽률 조합이 자체 계산으로 "OP"를 받는 역전이 확인됨. 상세 조사·후보 비교·최종 알고리즘 확정 과정은 `docs/spike/comp-tier-scoring.md`(설계 근거)·`docs/devlog/2026-08-18-comp-tier-scoring.md`(과정 서사) 참고.

## 확정 알고리즘

1. `comps.op_score`(op.gg `stat.opScore` 원값)를 같은 배치(10개) 안에서 0~100 Min-Max 정규화
2. 내림차순 정렬
3. 인접 순위 간 점수 격차(gap) 계산
4. 평균 격차 × 1.3을 넘는 지점만 "진짜 경계"로 인정(고정 5단계 강제 배분 폐지, 그날 분포에 따라 3~5단계 가변)
5. OP부터 순서대로 라벨 부여
6. `op_score`가 없는 행(op.gg 응답 결측)은 항상 "C" 고정

**목표 재정의**: "객관적 최강 조합 판별"은 이 데이터 소스(모집단이 이미 top-10으로 필터링됨, 선택편향, 맥락정보 부재, "강함"의 다차원성)로는 원천적으로 불가능해 — "op.gg top-10 안에서 op_score(사실상 대중성·신뢰도 대리 지표, avg_place·win_rate·top4_rate와는 거의 무관(r≈-0.2)하고 pickRate와 r=0.984로 거의 완벽히 상관됨을 실측 확인) 기준으로 믿을 만하게 강한 대중적 조합의 상대 순위"로 목표를 재정의했다.

## 변경 파일

- `backend/db/models.py`: `Comp`에 `op_score`(Float, nullable) 컬럼 추가.
- `backend/alembic/versions/202608181300_data23_add_comps_op_score_column.py`: 마이그레이션 신규.
- `batch/normalize.py`: `comp_rows()`에 `op_score` 매핑(`stat.get("opScore")`) 추가, `upsert_comps()`의 `on_conflict_do_update`에 반영. `assign_self_tiers()`를 avg_place·win_rate 두 축 순위합(`_ascending_ranks`, DATA-21) 방식에서 위 알고리즘으로 전면 재작성(`_ascending_ranks` 삭제, `_TIER_LABELS`를 퍼센타일 컷오프 튜플에서 라벨 리스트로 변경, `_GAP_THRESHOLD_FACTOR = 1.3` 신규).
- `batch/tests/test_data10_normalize.py`: `FAKE_DECK.stat`에 `opScore` 추가, `test_comp_rows_maps_fields_from_deck`에 `op_score` 검증 추가. 기존 avg_place/win_rate 기반 `assign_self_tiers` 테스트 5건을 전부 op_score 기반 테스트로 교체(`test_assign_self_tiers_empty_list_is_no_op`(유지)·`test_assign_self_tiers_single_scored_comp_lands_in_neutral_tier`·`test_assign_self_tiers_missing_op_score_gets_lowest_tier`·`test_assign_self_tiers_all_tied_scores_land_in_single_top_tier`·`test_assign_self_tiers_reproduces_real_snapshot_clusters`(2026-08-18 실측 스냅샷 10개 그대로 사용, op.gg 원본과 일치했던 3단계 분포 회귀 방지)·`test_assign_self_tiers_never_exceeds_five_labels`(연속 6개 유의미한 격차가 있어도 라벨이 5단계를 안 넘고 "C"에 누적됨을 검증)).
- `backend/tests/test_data02_migration.py`: `EXPECTED_TABLES["comps"]`에 `op_score` 추가.

## 자체 검증

- 도커 테스트 DB로 재검증: **backend 전체 353/353 통과**, **batch 전체 139/139 통과**(DATA-22 이후 138+신규 1 — 정확히는 5개 테스트를 6개로 교체해 순증 1).
- `ruff check .`·`ruff format --check` 전체 클린.
- **실제 op.gg 라이브 데이터로 배포된 함수(`comp_rows`+`assign_self_tiers`) 자체를 직접 실행해 재검증**(2026-08-18, 세션 중 실호출) — 현재 patch의 10개 조합 전부 op.gg 원본 opTier 라벨과 **10/10 완벽 일치**(트페·NOVA=OP, 자야·조이=S, 나머지 6개=A로 3단계 자연 분할, 고정 5단계를 강제하지 않았음에도 op.gg 원본과 정확히 일치).

## ⚠️ PM이 반드시 인지해야 할 한계 (과적합 위험)

`_GAP_THRESHOLD_FACTOR = 1.3`은 **2026-08-18 단일 스냅샷(같은 배치 10개)에서 탐색적으로 찾은 값**이다. 오늘 재검증에서도 10/10이 나왔지만, 이는 아직 "같은 날 다시 확인"한 것일 뿐 **다른 날짜·다른 패치의 스냅샷으로는 아직 검증하지 못했다.** 이 값이 과적합됐을 가능성을 배제할 수 없다.

**후속 조치 필요(DoD 원안이 요구한 "여러 날짜/패치 스냅샷 재검증")**: 앞으로 며칠간 배치가 실행될 때마다(1일 1회, DATA-14 스케줄) 그날의 `comps.op_score` 분포로 이 알고리즘을 재확인하고, op.gg 원본 opTier와의 일치율이 안정적으로 유지되는지 추적할 것을 권장한다. 이번 세션에서는 시간상 여러 날짜에 걸친 재검증을 완료하지 못했다 — **PM 확인 시 이 부분을 명확히 인지하고, "잠정 배포 후 며칠간 관찰" vs "재검증 완료 전까지는 보류" 중 방향을 결정해달라.**

## PM에게 필요한 결정

1. 위 과적합 위험을 감수하고 지금 커밋·배포할지, 아니면 재검증 기간을 먼저 가질지.
2. (배포 결정 시) 다음 배치 실행부터 새 `tier_rank`로 채워짐 — 기존 저장된 행은 다음 배치 전까지 이전 값(DATA-21 계산값) 그대로 남음(DATA-21과 동일한 정책, 별도 백필 스크립트 범위 밖).
