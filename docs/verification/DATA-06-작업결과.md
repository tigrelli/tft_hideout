# DATA-06 : 작업결과

- **TASK**: TFT DDragon 신규 구조 확인 스파이크
- **상태**: 완료(PM 확인 요청 중)
- **선행 TASK**: -
- **근거 문서**: PRD 12장·13-2
- **산출물**: [`/docs/spike/tft-ddragon.md`](../spike/tft-ddragon.md)

## 결과 요약

PRD가 우려한 "Set 18(2026-08-12)부터 TFT DDragon이 League DDragon에서 분리된다"는 신규 엔드포인트를 추정 도메인 2종(`tftdragon.leagueoflegends.com`, `ddragon.tft.leagueoflegends.com`)으로 직접 확인했으나 둘 다 연결되지 않았다 — **아직 공개되지 않은 것으로 보인다**(Set 18 런칭은 8일 후).

기존 `ddragon.leagueoflegends.com/api/versions.json`은 최신값이 `"16.15.1"`로, TFT 세트/패치 번호(op.gg 기준 "17.8")와 무관한 League 클라이언트 버전임을 확인 — PRD의 우려가 실제로 맞았다(다만 DATA-05에서 이미 op.gg `tft_list_item_combinations.version`을 패치 감지 신호로 확정했으므로 실질적 영향은 없음).

**대안으로 Community Dragon**(`raw.communitydragon.org/latest/cdragon/tft/{lang}.json`, 200 확인)이 이미 TFT 전체 데이터(챔피언/아이템/증강체/특성, 세트별)를 제공 중임을 확인했다. `setData[].mutator`가 `"TFTSet17"`로 op.gg의 `teamCode` 접미사와 정확히 일치하고, op.gg 자체 응답에도 `"type": "cdragon-item"`이 있어 op.gg가 내부적으로 Community Dragon을 쓰고 있음을 시사한다.

## PM 확인 필요

1. DATA-09(ID-이름 매핑)를 Community Dragon 기준으로 설계해도 되는지 — 비공식 커뮤니티 미러(Riot 비공식, ToS/가용성 보장 없음)라는 리스크가 있지만 업계에서 사실상 표준으로 널리 쓰임.
2. Set 18 런칭(2026-08-12) 이후 공식 TFT DDragon 등장 여부를 그때 재확인하는 것으로 충분한지, 아니면 별도 후속 스파이크를 잡을지.

## 자체 검증

- 추정 도메인 2종 접속 시도(결과: 미존재 확인) + 기존 League DDragon versions.json 확인 + Community Dragon 데이터 구조 확인·op.gg와 세트 식별자 교차검증 — WBS DoD("확인 결과 문서화") 충족
- 결과를 `/docs/spike/tft-ddragon.md`에 문서화(테스트 요구사항: 해당 없음(스파이크))
