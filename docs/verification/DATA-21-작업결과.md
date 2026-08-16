# DATA-21 : 작업결과 (완료 — PM 승인 2026-08-16)

- **TASK**: 메타 조합(comps) 자체 티어 스코어링 도입(승률·평균등수 기반 뱃지 재계산)
- **계기**: PM이 op.gg 웹사이트와 TFT Hideout 티어리스트의 OP/S/A 뱃지가 같은 조합에서 다르게 표시되는 캡처를 제보. 조사 결과 op.gg MCP 도구(`tft_list_meta_decks`)가 랭크 필터 없이 정확히 10개 조합만 반환해(DATA-05 스파이크) op.gg 웹사이트(20개 이상, 랭크 필터 가능)와 모집단 자체가 다름을 확인 — 완전 일치는 불가능하나, 확보한 표본 안에서라도 뱃지가 실제 수치와 어긋나지 않도록 자체 계산으로 전환하기로 PM 결정.

## 계산 방식 (PM 확인: 상대순위/퍼센타일 방식 채택)

`batch/normalize.py`의 `assign_self_tiers()`:

1. 같은 배치(패치 1회 수집 단위, 통상 10개 조합)에서 `avg_place` 오름차순 순위와 `win_rate` 내림차순 순위를 각각 매긴다(동점은 평균 순위 공유 — 아래 "구현 중 발견한 버그" 참고).
2. 두 순위를 더한 종합순위(Borda count 방식)로 정렬한다.
3. 종합순위를 백분위(구간 중앙값 기준: `(순번+0.5)/전체개수`)로 환산해 5단계로 분배: **OP(상위 10%) · S(~30%) · A(~60%) · B(~85%) · C(나머지)**.
4. `win_rate`가 없는 행(op.gg 응답 결측)은 그 축에서 항상 최하위로 취급.

10개 배치 기준 분포 예시: OP 1개 · S 2개 · A 3개 · B 3개 · C 1개.

`op.gg`가 준 `opTier` 값은 더 이상 저장하지 않는다(완전 대체). `comp_rows()`가 `run_patch_batch.py`(최초 배치)·`comps_refresh.py`(DATA-18 주기 재수집) 양쪽에서 공유되는 단일 함수라 두 경로 모두 자동 반영됨.

## 구현 중 발견한 버그 (수정 완료)

`avg_place`가 동점인 두 조합 중 하나만 `win_rate`가 있는 경우를 테스트하다가, 순위를 "리스트에서 먼저 나온 순서"로 매기면(단순 위치 기반) 동점 처리가 불공정하게 작동해 **`win_rate`가 없는 조합이 단지 리스트에 먼저 있었다는 이유만으로 더 좋은 티어를 받는** 문제를 실제로 재현·확인. 동점 값은 평균 순위를 공유하도록(`_ascending_ranks`) 수정해 해결 — 단위 테스트(`test_assign_self_tiers_missing_win_rate_ranks_last_on_that_axis`)로 회귀 방지.

## 변경 파일

- `batch/normalize.py`: `_ascending_ranks()`, `assign_self_tiers()` 신규 추가, `comp_rows()`가 `stat.get("opTier")` 대신 `assign_self_tiers()` 결과를 사용하도록 변경.
- `batch/tests/test_data10_normalize.py`: 기존 `test_comp_rows_maps_fields_from_deck`의 기대값을 op.gg 원본("OP")에서 자체 계산 값("A", 배치 내 조합 1개일 때 중앙 백분위)으로 갱신. `assign_self_tiers` 단위 테스트 6개 신규 추가(빈 리스트, 단일 조합, 10개 배치 분포, win_rate 결측 처리, 등수·승률 트레이드오프).

## 자체 검증

- `batch/tests/` 전체 **135 passed**(도커 테스트 DB 사용, DATA-18 소프트 삭제·재활성화 로직 등 comps 관련 기존 테스트도 회귀 없음 확인).
- `backend/tests/` 전체 **352 passed**(comps API가 배치가 채운 `tier_rank`를 그대로 응답하는 구조라 영향 없음, 회귀 확인차 재실행).
- `ruff check`/`ruff format --check` 통과.

## PM에게 필요한 결정

1. 계산 방식(상대순위/백분위 OP 10%·S 30%·A 60%·B 85%·C 100%) 승인 여부.
2. 승인 시 커밋·push. 실제 운영 반영은 다음 배치 실행(DATA-14, 1일 1회 03:00 KST 스케줄 또는 DATA-18 주기 재수집) 시점부터 새 `tier_rank`로 채워짐 — 기존에 이미 DB에 저장된 행은 다음 배치 전까지 이전 값(op.gg opTier) 그대로 남아있음(별도 백필 스크립트는 이번 범위에 포함하지 않음, 필요하면 후속 논의).
