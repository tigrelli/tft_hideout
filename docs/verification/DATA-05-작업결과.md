# DATA-05 : 작업결과

- **TASK**: op.gg MCP 응답 스키마 확인 스파이크
- **상태**: 완료(PM 확인 요청 중)
- **선행 TASK**: -(원래 SET-10 의존이었으나 op.gg는 키 불요로 확인돼 제거)
- **근거 문서**: PRD 13-2·설계서 8장
- **산출물**: [`/docs/spike/opgg-schema.md`](../spike/opgg-schema.md)

## 결과 요약

PM이 제공한 `https://mcp-api.op.gg/mcp`(별도 인증 불필요, Streamable HTTP MCP)에 실접속해 설계서 4.3이 명시한 6개 TFT 도구를 전부 실호출하고 응답 스키마를 확인했다. 상세 내용·샘플 응답은 `docs/spike/opgg-schema.md` 참고.

## 핵심 발견 (PM 확인 필요한 결정 포함)

1. **`patch_version` 상당 필드**: 6개 도구 중 `tft_list_item_combinations`에만 최상위 `set`(17)·`version`("17.8") 필드가 존재하고, 나머지 5개(`tft_list_meta_decks` 등)에는 없음. **제안**: DATA-12(자동 패치 감지)를 이 필드 기준으로 구현하면 PRD 9-1이 대비책으로 제시한 "Riot 챌린저/그마 리더보드 샘플링" 폴백 없이도 패치 감지가 가능하다 — Riot 키(SET-16) 대기와 무관하게 진행 가능. **PM 확인 필요**: 이 방식으로 확정해도 되는지.
2. **`is_legend_related` 라벨**: `tft_list_augments` 357개 증강체 전수 확인 결과 라벨 없음 확정. DATA-07(수동 유지 목록 방식)으로 바로 착수 가능 — 단 Set 17에 Legend 메커니즘 자체가 있는지는 DATA-07에서 별도 확인 필요.
3. **`tft_get_play_style`이 개인 데이터 도구임을 발견**: 입력 스키마가 `region`+`puuid`(Riot 계정 PUUID) 필수. `glossary.md`의 "op.gg는 개인 전적 조회 기능 없음"과 상충하고, DATA-08(카탈로그 배치 워커)이 상정한 "6개 도구 순차 호출"과도 맞지 않는다(PUUID 없이는 호출 불가). **PM 확인 필요**: 이 도구를 DATA-08에서 제외하고 PGA-07(코칭 문장 생성, 이미 사용자 PUUID 확보된 상태) 쪽으로 재배치할지.
4. Set 17 확인(`TFT17_` 접두사, `teamCode` "TFTSet17" 접미사, item `version: "17.8"`) — Set 18 전환(2026-08-12 예정) 전이므로 DATA-06은 현재 Set 17 기준으로 확인하게 됨.

## 자체 검증

- 6개 도구 전부 최소 1회 실호출(파라미터 필요한 도구는 유효 ID로, `tft_get_play_style`은 PUUID가 없어 스키마만 확인) — WBS DoD("확인 결과 스파이크 리포트 문서화") 충족
- 결과를 `/docs/spike/opgg-schema.md`에 문서화(테스트 요구사항: "해당 없음(스파이크)" — 자동화 테스트 대상 아님)

## 다음 세션을 위한 메모

DATA-06(TFT DDragon)·DATA-08(배치 수집 워커) 착수 전에 위 4가지 PM 확인 사항(특히 2, 3번)을 먼저 정리할 것.
