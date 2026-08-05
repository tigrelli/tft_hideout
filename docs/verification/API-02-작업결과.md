# API-02 : 작업결과

- **TASK**: GET /catalog/tierlist 구현
- **상태**: 완료(PM 승인 2026-08-03)
- **선행 TASK**: DATA-02,API-01
- **커밋**: f8c2ad5

## 결과 요약

GET /api/v1/catalog/tierlist 구현(patch/rank 필터, patch 미지정 시 현재 패치 기본값). API-01의 라우터 prefix가 api-spec.md 기준(/api/v1/...)과 달라 이번에 수정. comps에 rank_tier 컬럼 추가(기본값 'all', 실제 랭크 구간 값은 DATA-05 스파이크 후 확정 필요). 공통 에러 응답 포맷 핸들러({"error":{"code","message"}}) main.py에 추가 — 이후 API-* TASK 공용

## 2026-08-05 갱신 — 랭크 필터 제거(PM 결정)

`tft_list_meta_decks`의 `inputSchema`를 직접 재확인한 결과 파라미터가 전혀 없음(`{"type":"object","properties":{},"required":[]}`)을 확인 — 랭크 구간별 데이터를 op.gg에서 얻을 방법 자체가 없음이 확정됨(`docs/spike/opgg-schema.md` 7번). PM 결정으로 랭크 필터 기능 전체 제거:
- `GET /catalog/tierlist`의 `rank` 쿼리 파라미터·`ALLOWED_RANKS`·응답의 `rank` 필드 삭제(patch 필터만 유지)
- `comps.rank_tier` 컬럼 삭제(마이그레이션 `2fdcd6f417ba`)
- 프론트 랭크 드롭다운(`FilterBar`) 컴포넌트·타입(`RANK_OPTIONS`/`RankValue`) 삭제, 티어리스트 페이지는 패치 배지만 표시
- backend pytest 3건 갱신(rank 관련 2건 제거), batch/frontend 전체 회귀 통과. 상세: `docs/verification/API-02-rollback-작업결과.md`

---
*이 파일은 CLAUDE.md v1.8(2026-08-03) 컨벤션 도입 시점에 진행현황.md 변경 이력을 근거로 소급 작성됨.*
