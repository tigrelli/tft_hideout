# API-02 랭크 필터 롤백 : 작업결과

- **성격**: 신규 TASK가 아니라 이미 완료된 API-02(GET /catalog/tierlist)·FE-03(FilterBar)의 랭크 필터 기능을 PM 결정으로 전체 제거하는 작업.
- **상태**: 완료(PM 승인 2026-08-05)
- **관련 TASK**: API-02, FE-03, FE-11(간접 — ResponsiveFilter 공용 컴포넌트는 FE-05·FE-06에서 계속 사용, FE-03만 사용 중단)
- **근거 문서**: `docs/spike/opgg-schema.md` 7번(op.gg `tft_list_meta_decks` inputSchema 재확인)

## 배경

사용자(PM)가 로컬 브라우저로 티어리스트 화면을 확인하던 중 "랭크"를 "챌린저"/"마스터"로 바꾸면 "조건에 맞는 조합이 없습니다"만 나오는 것을 발견해 문의. 확인해보니 API-02 구현 당시(2026-08-03) 이미 "실제 랭크 구간 값은 DATA-05 스파이크 완료 후 확정 — 지금은 all만 실사용"으로 알려진 미완 상태였음(주석에 기록돼 있었음). 이번에 `tools/list`로 `tft_list_meta_decks`의 `inputSchema`를 직접 재조회해 **파라미터가 전혀 없음**(`{"type":"object","properties":{},"required":[]}`)을 확인 — 랭크 구간별 데이터 자체를 op.gg에서 받을 방법이 없다는 게 "언젠가 풀릴 수도 있는 미확정"이 아니라 **데이터 소스의 확정적 한계**임이 밝혀졌다. PM이 랭크 필터 기능을 완전히 제거하기로 결정.

## 변경 파일

- **문서**: `docs/spike/opgg-schema.md`(7번 신설), `docs/verification/API-02-작업결과.md`(갱신 섹션 추가)
- **backend**: `routers/catalog.py`(`ALLOWED_RANKS`·`rank` 쿼리 파라미터·`TierlistResponse.rank`·`Comp.rank_tier` 필터 제거), `db/models.py`(`Comp.rank_tier` 컬럼 제거), `alembic/versions/202608051800_api02_drop_comps_rank_tier_column.py`(신규 마이그레이션), `tests/test_api02_tierlist.py`(rank 관련 테스트 2건 제거, 나머지 fixture에서 `rank_tier` 제거), `tests/test_data02_migration.py`(`EXPECTED_TABLES`에서 `rank_tier` 제거), `tests/test_api03_comp_detail.py`(fixture에서 `rank_tier="all"` 2곳 제거)
- **frontend**: `src/app/page.tsx`(rank state·쿼리 제거, PatchBadge 인라인 표시로 단순화), `src/components/tierlist/filter-bar.tsx`(삭제), `src/components/__tests__/filter-bar.test.tsx`(삭제), `src/types/catalog.ts`(`RANK_OPTIONS`/`RankValue` 제거, `TierlistResponse.rank` 필드 제거), `src/app/__tests__/page.test.tsx`(rank 관련 테스트 1건 제거, mock에서 `rank` 필드 제거)

## 자체 검증

- **backend**: pytest **180/180 통과**(rank 전용 테스트 2건 제거 후), 로컬 테스트 DB에 신규 마이그레이션(컬럼 삭제) 재적용 확인, ruff check/format 통과
- **batch**: 회귀 **80/80 통과**(batch 코드는 애초에 `rank_tier`를 직접 다루지 않아 영향 없음 — DB server_default에 의존)
- **frontend**: Vitest **54/54 통과**(filter-bar.test.tsx 4건 + page.test.tsx 1건 제거 후), `tsc --noEmit`/eslint/prettier/`next build`(정적 export, 4개 페이지 정상 생성) 전부 통과

## 참고 — FE-11에 미치는 영향

FE-11(필터 UI 반응형 공용 컴포넌트) 완료 당시 DoD "3개 화면(티어리스트/아이템빌드/증강체)에서 재사용 확인"을 충족했었으나, 이번 롤백으로 티어리스트(FE-03)가 더 이상 `ResponsiveFilter`/`FilterDropdown`을 사용하지 않게 되어 실제 재사용 화면은 2개(아이템빌드 FE-05, 증강체 FE-06)로 줄었다. `FilterDropdown`/`ResponsiveFilter` 컴포넌트 자체나 FE-11의 구현 방식에는 문제가 없어 별도 수정하지 않음 — 재사용 화면 수가 줄어든 것은 FE-03 자체가 기능을 잃었기 때문이며, 공용 컴포넌트 설계 결함이 아니다.
