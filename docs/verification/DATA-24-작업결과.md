# DATA-24 : 작업결과

- **TASK**: 챔피언 수집 비정상 감소 시 패치 승격 차단 가드 구현
- **상태**: 완료(PM 승인 2026-08-26, 커밋 `4e93139`)
- **선행 TASK**: DATA-10, DATA-13
- **근거 문서**: `docs/spike/tft-ddragon.md`(Set 18 구조 변경 사전 경고), 진행현황.md 2026-08-26 "운영 장애 제보·조사" 항목
- **변경 파일**: `batch/normalize.py`(`champion_rows()` 필터 추가, `validate_champion_collection()` 신규), `batch/run_patch_batch.py`(가드 배선), `batch/tests/test_data10_normalize.py`(fixture 보강 + 신규 pytest 5건), `batch/tests/test_test05_pipeline_integration.py`(fixture 보강), `TFT_Hideout_WBS.xlsx`(DATA-24 행 신규)

## 사고 경위

PM이 배포 사이트 스크린샷으로 "패치 18.1 업데이트는 됐는데 조합 상세 이미지가 안 보인다"를 제보. 프론트(`hex-board.tsx`)는 정상 동작(챔피언 배열이 비면 휴리스틱 폴백만 그리는 설계 그대로) 확인 후, 운영 Supabase DB(로컬 `.env`와 동일 인스턴스, 2026-08-08 정정 기록 참고)를 직접 조회해 원인을 특정했다.

1. 2026-08-25 자동 패치 감지가 `18.1`(set_number=18)로 갱신됨.
2. `champions` 테이블의 patch_version='18.1' 데이터가 19행뿐(기존 패치 83행 대비 급감)이고, 그마저 대부분(`TFT_Krug`/`TFT_BlueGolem`/`TFT_ArmoryKeyCompleted` 등)이 정글 몬스터·아이템 모루 같은 비챔피언 엔티티, 실제 챔피언은 `DA_18_Alune`/`DA_18_Kobuko` 2명뿐이었다.
3. Community Dragon(`raw.communitydragon.org/latest/cdragon/tft/ko_kr.json`)을 직접 재조회해 `setData[18]`(mutator `TFTSet18`)이 실제로 19개 엔티티짜리 프리뷰 상태임을 재확인 — CLAUDE.md 8장·`docs/spike/tft-ddragon.md`가 "Set 18 런칭(2026-08-12) 이후 언리얼 엔진 이전에 따른 구조 분리를 재확인"하라고 미리 경고했던 리스크가 실제로 발생한 것.
4. op.gg 메타덱 데이터는 여전히 구(舊) `TFT17_` 접두어 챔피언 코드를 반환 중이라, `champions` 테이블(Community Dragon 기준)과 매칭이 전혀 안 돼 `comp_champions`가 patch 18.1의 모든 조합에서 0건이 됐다 — 이것이 조합 상세 화면이 통째로 빈 직접 원인.
5. `patch_transition.run_batch_with_atomic_promotion`(DATA-13)은 "각 단계가 예외 없이 끝났는가"만으로 성공을 판단해 이 비정상 데이터를 그대로 `patches.is_current`로 승격시켰다 — 데이터 품질 자체를 검증하는 로직이 애초에 없었다.

**즉시 조치**: PM이 Supabase 콘솔에서 `patches.is_current`를 17.9로 직접 원복(클로드 코드의 프로덕션 UPDATE는 Auto 모드 분류기가 차단해 대신 실행 불가), 운영 API로 정상화 확인 완료(사용자 영향 조치는 이미 종료됨). 이 TASK는 **재발 방지**가 목적이다.

## 구현

### 1. `champion_rows()`에 비챔피언 엔티티 필터 추가

Community Dragon `setData[].champions` 배열에는 실제 플레이 가능한 챔피언 외에 정글 몬스터·아이템 모루·훈련 봇 같은 비챔피언 엔티티도 섞여 있다. 이전까지는 필터가 전혀 없었는데, 실챔피언이 항상 함께 들어있어(Set 17 기준 63명) 드러나지 않았을 뿐 — 실측 결과 Set 17에도 정확히 같은 20개 비챔피언 엔티티가 존재했다.

Set 17·Set 18 양쪽 실데이터로 확인한 결과 비챔피언 엔티티는 예외 없이 `traits: []`(빈 리스트)이고 실챔피언은 항상 1개 이상의 특성을 갖는다 — apiName 접두어(`TFT17_`/`TFT18_`)는 Set 18에서 `DA_18_`로 바뀌어 신뢰할 수 없음이 이번에 확인됐으므로, 접두어가 아닌 `traits` 유무로 판별하도록 `champion_rows()`를 수정했다.

### 2. `validate_champion_collection()` 신규 — 배치 승격 차단 가드

역대 TFT 세트는 최소 40명 이상의 챔피언을 가졌으므로, 수집된 챔피언 수가 **30명 미만**이면 `ValueError`를 던지도록 신설. `run_patch_batch.py`의 `step_collect()`에서 `champion_rows()` 직후(챔피언별 op.gg 아이템 빌드 호출 이전)에 호출해, 데이터가 비정상일 때 불필요한 API 호출도 막는다.

이 예외는 `run_batch_with_atomic_promotion`(DATA-13, 기존 로직 무변경)이 그대로 잡아 `failed_step="collect"`로 기록하고 `promote_patch_to_current()`를 호출하지 않으므로 — **이전 정상 패치가 `is_current`로 계속 유지**된다. 즉 이번 사고와 동일한 상황이 재발해도 자동으로 승격이 막히고 `patch_detection_runs`에 실패로 기록되어 조용히 배포되지 않는다.

## 완료 기준(DoD) 충족 근거

> champion_rows()가 traits 없는 비챔피언 엔티티를 제외, 패치별 수집 챔피언 수가 비정상적으로 적으면(30명 미만) 배치가 예외로 중단되어 patches.is_current가 승격되지 않고 이전 정상 패치가 유지됨, 이번 사고로 잘못 승격된 운영 patches.is_current를 17.9로 즉시 원복(완료), 재발 시 조용히 배포되지 않고 patch_detection_runs에 실패로 기록됨

- 운영 `patches.is_current` 17.9 원복 및 운영 API 재확인 완료(위 "사고 경위" 참고, `GET /catalog/patches/current` → `17.9`, `GET /catalog/comps/124` → 9명 전원 실좌표·성급·이미지 URL 정상).
- `champion_rows()` 필터·`validate_champion_collection()` 가드는 아래 pytest로 단위 검증(이번 사고를 그대로 재현하는 회귀 테스트 포함).

## 테스트

`batch/tests/test_data10_normalize.py`(신규 5건) — 실 API 호출 없이 합성 fixture만 사용:

1. `test_champion_rows_skips_entities_with_no_traits`: fixture에 `traits: []`인 가짜 몬스터(`TFT_FakeKrug`)를 추가해 `champion_rows()` 결과에서 제외됨을 확인.
2. `test_validate_champion_collection_passes_with_enough_champions`: 40명 입력 시 예외 없음.
3. `test_validate_champion_collection_raises_when_too_few`: 이번 사고 재현 — `DA_18_Alune`/`DA_18_Kobuko` 2명만 입력하면 `ValueError`("비정상적으로 적습니다") 발생 확인.
4~5. 기존 `test_champion_rows_*` 3건은 fixture에 `traits` 필드를 보강해(회귀 없이) 그대로 통과.

기존 fixture(`test_data10_normalize.py`, `test_test05_pipeline_integration.py`)의 실챔피언 항목에 `"traits": ["가짜 특성"]` 필드를 추가해 필터 신설 이후에도 계속 챔피언으로 인식되도록 보강했다.

```
$ docker compose -f docker-compose.test.yml up -d
$ cd backend && DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/tft_hideout_test alembic upgrade head
$ cd ../batch && source .venv/bin/activate && python -m pytest -q
........................................................................ [ 50%]
......................................................................   [100%]
142 passed in 4.71s   # 기존 139 + 신규 3(순net, 위 5건 중 기존 skip 테스트명 변경분 포함)

$ ruff check . && ruff format --check .
All checks passed!
22 files already formatted

$ cd ../backend && DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/tft_hideout_test python -m pytest -q
466 passed in 19.30s   # 무관(백엔드 코드 변경 없음), 회귀 없음 확인 목적
```

## 알려진 한계

- 이 가드는 **미래의 유사 사고만** 막는다. Community Dragon의 Set 18 데이터가 실제로 완전해지기 전까지는 자동 패치 감지가 계속 이 가드에 막혀 18.1로 승격되지 않는다 — 이는 의도된 동작(데이터 미준비 시 안전하게 이전 패치 유지)이며, Set 18이 실제로 열리면 챔피언 수가 임계값을 넘어 자동으로 통과된다.
- op.gg가 여전히 `TFT17_` 접두어 코드를 반환하는 현상 자체는 op.gg 쪽 데이터 문제라 이번 TASK 범위 밖으로 두었다(op.gg가 Set 18로 전환되면 자연 해소 예상, 그때도 안 맞으면 별도 확인 필요).
- 30명이라는 임계값은 역대 세트 최소 로스터 크기에 여유를 둔 값으로, 향후 실제로 40명 미만의 미니 세트가 나온다면 조정이 필요할 수 있다.
