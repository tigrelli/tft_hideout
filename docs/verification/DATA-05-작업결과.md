# DATA-05 : 작업결과

- **TASK**: op.gg MCP 응답 스키마 확인 스파이크
- **상태**: 완료(PM 승인 2026-08-04)
- **선행 TASK**: -(원래 SET-10 의존이었으나 op.gg는 키 불요로 확인돼 제거)
- **근거 문서**: PRD 13-2·설계서 8장
- **산출물**: [`/docs/spike/opgg-schema.md`](../spike/opgg-schema.md)

## 결과 요약

PM이 제공한 `https://mcp-api.op.gg/mcp`(별도 인증 불필요, Streamable HTTP MCP)에 실접속해 설계서 4.3이 명시한 6개 TFT 도구를 전부 실호출하고 응답 스키마를 확인했다. 상세 내용·샘플 응답은 `docs/spike/opgg-schema.md` 참고.

## 핵심 발견 및 PM 결정 (2026-08-04)

1. **`patch_version` 상당 필드**: 6개 도구 중 `tft_list_item_combinations`에만 최상위 `set`(17)·`version`("17.8") 필드가 존재하고, 나머지 5개(`tft_list_meta_decks` 등)에는 없음. **PM 결정**: DATA-12(자동 패치 감지)를 이 필드 기준으로 구현 확정 — PRD 9-1의 "Riot 챌린저/그마 리더보드 샘플링" 폴백 없이도 Riot 키(SET-16) 대기와 무관하게 진행 가능. Riot 키 확보 후 리더보드 샘플링을 보조 신호로 추가하는 것도 가능(트리거 체크 함수 하나만 손대면 되는 구조).
2. **`is_legend_related` 라벨**: `tft_list_augments` 357개 증강체 전수 확인 결과 라벨 없음 확정. DATA-07(수동 유지 목록 방식)으로 바로 착수 가능 — 단 Set 17에 Legend 메커니즘 자체가 있는지는 DATA-07에서 별도 확인 필요. (이 필드의 용도: Riot TFT 개발자 정책 "Legends/Legend 기반 증강체 승률 표시 금지"를 지키기 위해 API-05/CHAT-06/FE-06이 승률을 마스킹할 대상을 가리는 플래그, PRD 9-1)
3. **`tft_get_play_style`이 개인 데이터 도구임을 발견**: 입력 스키마가 `region`+`puuid`(Riot 계정 PUUID) 필수. `glossary.md`의 "op.gg는 개인 전적 조회 기능 없음"과 상충하고, DATA-08(카탈로그 배치 워커)이 상정한 "6개 도구 순차 호출"과도 맞지 않음(PUUID 없이는 호출 불가). **PM 결정**: DATA-08에서 제외하고 PGA-07(코칭 문장 생성, PGA-01~02에서 이미 확보한 PUUID 재사용)로 이동. WBS.xlsx DATA-08("5개 도구 순차 호출")·PGA-07 TASK 설명 갱신 완료.
4. Set 17 확인(`TFT17_` 접두사, `teamCode` "TFTSet17" 접미사, item `version: "17.8"`) — Set 18 전환(2026-08-12 예정) 전이므로 DATA-06은 현재 Set 17 기준으로 확인하게 됨.

## 자체 검증

- 6개 도구 전부 최소 1회 실호출(파라미터 필요한 도구는 유효 ID로, `tft_get_play_style`은 PUUID가 없어 스키마만 확인) — WBS DoD("확인 결과 스파이크 리포트 문서화") 충족
- 결과를 `/docs/spike/opgg-schema.md`에 문서화(테스트 요구사항: "해당 없음(스파이크)" — 자동화 테스트 대상 아님)

## 다음 세션을 위한 메모

위 4가지 모두 PM 결정 완료. DATA-06(TFT DDragon)·DATA-08(배치 수집 워커, 5개 도구)·PGA-07(tft_get_play_style 포함) 착수 시 이 문서와 `docs/spike/opgg-schema.md`를 그대로 참고.
