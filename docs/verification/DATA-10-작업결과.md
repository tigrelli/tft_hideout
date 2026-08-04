# DATA-10 : 작업결과

- **TASK**: 데이터 정규화 및 patch_version 태깅 구현
- **상태**: 완료(PM 승인 2026-08-04)
- **선행 TASK**: DATA-02, DATA-08
- **근거 문서**: PRD 9-2·12장
- **변경 파일**: `batch/normalize.py`(신규), `batch/db_session.py`(신규), `batch/tests/test_data10_normalize.py`(신규), `batch/tests/conftest.py`(신규, backend alembic 재사용), `backend/alembic/versions/202608041000_data10_add_natural_keys_and_unique_constraints.py`(신규 마이그레이션), `backend/db/models.py`(UniqueConstraint·`riot_trait_id`·`riot_comp_id` 추가), `backend/tests/test_data01_migration.py`·`test_data02_migration.py`·`test_api02_tierlist.py`·`test_api03_comp_detail.py`(신규 컬럼 반영), `batch/requirements.txt`/`requirements-dev.txt`

## 착수 전 발견한 스키마 문제 (PM 승인 후 해결)

DoD("동일 엔티티 재수집 시 upsert, 덮어쓰기 아님")를 지키려면 (patch_version, 원본 ID) 기준 UNIQUE 제약이 필요한데, 기존 마이그레이션엔 `champions`/`items`/`augments`에 제약이 없었고 `traits`/`comps`는 원본 ID 컬럼 자체가 없었다. PM 승인(2026-08-04)으로 마이그레이션을 추가해 해결:
- `traits.riot_trait_id`, `comps.riot_comp_id` 컬럼 신규(그린필드라 기존 행 없어 NOT NULL 바로 적용)
- `champions`/`items`/`augments`/`traits`/`comps` 5개 테이블에 `UNIQUE(patch_version, 원본ID)` 추가

## comps 정규화 관련 3가지 결정 (PM 승인)

1. **tier_rank**: op.gg가 주는 값(`OP`/`S`/`A`/...)을 가공 없이 그대로 저장. `OP`→`S` 통합 등은 하지 않고, 배지 색상 매핑은 FE-03에서 결정
2. **playstyle_text**: op.gg 응답엔 설명 텍스트가 없어, `badge`(difficulty/tempo/reroll/honey/ppm) + 캐리 챔피언 이름으로 LLM 없이 결정론적 텍스트 생성(`build_playstyle_text()`). 정확한 문구는 자리표시자 성격 — 추후 다듬을 수 있음
3. **comp_augments**: op.gg 5개 도구 어디에도 조합-증강체 데이터가 없어 이번 TASK 범위에서 제외, 테이블은 비워둠

## 결과 요약

- **champions/traits**: Community Dragon(DATA-09)에서 ko/en 각 1회 조회해 세트 번호로 필터링 후 매핑(op.gg는 표시 이름을 안 줌)
- **items/augments**: op.gg `list_item_combinations`/`list_augments`를 ko/en 각 1회 호출해 이름 2개 언어 확보
- **comps/comp_champions**: op.gg `list_meta_decks` 1회 호출. `comp_champions`는 이미 존재하는 (comp_id, champion_id) 복합 PK가 자연키라 별도 스키마 변경 없이 upsert 가능
- **champion_item_builds**: 안정적 자연키가 없어(빌드 조합 자체가 매번 바뀔 수 있음) 챔피언·패치 단위로 delete 후 insert하는 replace-set 방식 채택
- 모든 upsert는 `ON CONFLICT (patch_version, 원본ID) DO UPDATE` — 같은 패치 재수집은 갱신, 다른 패치는 새 행(policies.md 3번)
- `patches` 행이 없으면 생성하되 `is_current`는 건드리지 않음(DATA-13 몫)
- `batch/db_session.py`는 `backend/db/models.py`를 그대로 import해 재사용 — 테이블 정의를 두 곳에서 따로 관리하면서 어긋나는 위험을 없앰(같은 저장소·같은 DB를 공유하므로). backend/batch가 각각 독립 배포되더라도 소스 트리는 공유되므로 문제 없음

## 자체 검증

- pytest 38/38 통과(기존 20 + 신규 18): 변환 함수 순수 로직 + 실제 마이그레이션 적용된 테스트 DB로 upsert 동작 검증(합성 fixture, `policies.md` 10.2/11)
  - **핵심 케이스**: 같은 patch_version으로 재수집 시 DB id 동일·행 개수 그대로(덮어쓰기 검증), 다른 patch_version은 새 행 생성(덮어쓰지 않음 검증)
  - `ensure_patch`가 이미 `is_current=True`인 기존 patches 행을 건드리지 않는지 검증
  - `comp_champions`에서 champions 테이블에 없는 챔피언(PVE 전용 등)은 건너뛰는지 검증
  - `champion_item_builds`의 replace-set 동작(재수집 시 이전 빌드 목록이 완전히 새 목록으로 교체) 검증
- `ruff check` / `ruff format --check` 통과(backend·batch 모두)
- backend 전체 회귀 100/100 통과(신규 마이그레이션 적용 후, 기존 API-02/03 테스트 fixture에 `riot_comp_id` 추가 반영)
- **WBS DoD("신규 패치 upsert 후 데이터 정합성 확인") 실제 데이터로 검증**: 실제 op.gg + Community Dragon에서 데이터를 가져와 로컬 테스트 DB에 2회 연속 적재 — champions 83·traits 44·items 838·augments 357·comps 10·comp_champions 86, **재수집 후에도 행 개수 완전히 동일**(중복 없음, upsert 정상). 샘플 comp: `"아칼리/잭스/킨드레드 캐리 · 난이도 1 · 리롤 성향 6 · 파워스파이크 속도 high"` — 자동 생성된 playstyle_text 실제 출력 확인

## 다음 세션을 위한 메모

- `comp_augments`는 데이터 소스가 없어 빈 상태 — CHAT-02(하이브리드 검색)가 이 테이블을 참조할 때 이 사실을 감안해야 함
- `champion_item_builds`/`comp_champions` 전체 정규화(모든 챔피언·조합 순회)는 DATA-08 클라이언트를 그대로 재사용하면 되지만, 실제 배치 오케스트레이션(패치 감지→전체 수집→임베딩까지 잇는 최상위 스크립트)은 DATA-11(임베딩)·DATA-12(패치 감지)·DATA-13(원자적 전환) 이후에 하나로 묶일 예정 — 이번 TASK는 정규화 "함수"까지만 제공
- `playstyle_text` 문구는 배지 값의 정확한 의미(예: `ppm`이 정확히 뭘 뜻하는지, `honey`의 값 범위)를 공식 문서로 확인한 게 아니라 관찰된 샘플 1건 기준으로 추정한 라벨이다 — 더 많은 샘플이 쌓이면 재검토 필요
