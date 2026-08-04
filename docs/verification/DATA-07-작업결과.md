# DATA-07 : 작업결과

- **TASK**: is_legend_related 판별 방법 확인 스파이크
- **상태**: 완료(PM 확인 요청 중)
- **선행 TASK**: DATA-05
- **근거 문서**: 설계서 5.1·8장
- **산출물**: [`/docs/spike/legend-augment.md`](../spike/legend-augment.md)

## 결과 요약

DATA-05에서 이미 확인한 "op.gg 응답에 라벨 없음"을 재확인하고, 이번 스파이크의 나머지 범위인 "현재 세트에 Legends 메커니즘 자체가 있는지"를 Community Dragon 전체 세트 데이터로 조사했다.

- apiName에 "legend"가 포함된 증강체는 전체 세트를 통틀어 5개뿐이며 전부 `TFT9_` 접두사(과거 Set 9 소속)
- Set 17(`TFTSet17`) 활성 증강체 풀(275개)엔 그중 1개(`TFT9_Augment_Legend_HighEndSector`)가 참조로 남아있지만, op.gg가 실제로 서빙하는 현재 뽑을 수 있는 증강체 목록(357개)에는 없음 — 레거시 데이터 잔재로 판단
- Set 17 네이티브(`TFT17_`) 증강체·특성 어디에도 "legend" 키워드 없음
- Community Dragon 세트 스키마 자체에 "legends"라는 별도 카테고리도 없음(augments/champions/items/traits뿐)

**결론: Set 17에는 활성화된 Legends 메커니즘이 없다.**

## 판별 방법 확정

개발설계서 109행이 제시한 방식 그대로 채택:
- `is_legend_related` 컬럼과 API-05/CHAT-06/FE-06 마스킹 로직은 그대로 구현(세트가 바뀌면 다시 필요해질 수 있으므로 로직을 생략하지 않음)
- Set 17 데이터는 수동 유지 목록을 **빈 배열로 시작** — 모든 증강체 `is_legend_related=false`
- 목록은 세트별 키(`{set_number: [apiName, ...]}`)로 코드 저장소에 시드 데이터 형태로 유지, 위치는 DATA-08/DATA-10 구현 시 확정

## 자체 검증

- op.gg 라벨 부재 재확인 + Community Dragon 전체 세트 검색(5건 전수 확인) — WBS DoD("판별 로직 확정 및 문서화") 충족
- 결과를 `/docs/spike/legend-augment.md`에 문서화(테스트 요구사항: 해당 없음(스파이크))

## 다음 세션을 위한 메모

DATA-08/DATA-10에서 `is_legend_related`는 이 문서의 수동 목록(현재 빈 배열)을 조회해 채운다. Set 18 전환(2026-08-12) 이후 새 세트 증강체 목록에서 동일 방법으로 재확인 필요.
