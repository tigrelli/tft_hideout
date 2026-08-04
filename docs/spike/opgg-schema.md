# DATA-05 스파이크 — op.gg MCP 실제 응답 스키마 확인

- **일자**: 2026-08-04
- **방법**: `https://mcp-api.op.gg/mcp`에 Streamable HTTP(JSON-RPC 2.0)로 직접 연결해 `initialize` → `tools/list` → `tools/call`을 curl로 실호출. 별도 API 키/인증 불필요(공개 엔드포인트, `Mcp-Session-Id` 헤더만 세션 유지에 사용).
- **연결 정보(DATA-08 구현 시 재사용)**: `POST /mcp`, 헤더 `Content-Type: application/json`, `Accept: application/json, text/event-stream`. `initialize` 응답의 `Mcp-Session-Id`를 이후 요청에 `Mcp-Session-Id` 헤더로 포함해야 함(세션 없으면 400). LangChain에서는 MCP 클라이언트(예: `langchain-mcp-adapters`)로 동일하게 접속 가능.

## 1. 6개 도구 존재 확인

설계서 4.3(43행)이 명시한 6개 도구가 실제로 `tools/list`에 그대로 존재함을 확인:

`tft_list_meta_decks`, `tft_get_champion_item_build`, `tft_list_item_combinations`, `tft_list_augments`, `tft_list_champions_for_item`, `tft_get_play_style`

(참고: 같은 MCP 서버에 LoL/Valorant 도구도 섞여 있음 — `tools/list` 필터링 시 `tft_` 접두사로 구분 필요)

## 2. patch_version 상당 필드 — 도구별로 다름 (핵심 발견)

**있음/없음이 도구마다 다르다.** 정적 참조 데이터(cdragon 소스) 도구에만 명시적 버전 필드가 있고, 매치 통계 집계 도구에는 없음.

| 도구 | 버전 필드 | 비고 |
|---|---|---|
| `tft_list_item_combinations` | **있음** — 응답 최상위에 `"set": 17, "version": "17.8"` | cdragon 정적 데이터 소스 |
| `tft_list_meta_decks` | 없음 — 대신 `metadata.gameStatDateTime`(집계 시각, 예 `"2026-08-04T00:59:35.000Z"`), `metadata.gameStatCounts`(표본 게임 수) | 매치 통계 집계 |
| `tft_get_champion_item_build` | 없음 | 매치 통계 집계 |
| `tft_list_champions_for_item` | 없음 (응답이 바로 배열) | 매치 통계 집계 |
| `tft_list_augments` | 없음 (`{headers, rows, header_description}` 테이블 포맷) | 정적 데이터인데도 버전 필드 없음 |

**권장**: DATA-12(자동 패치 감지)는 `tft_list_item_combinations`의 `version` 필드(예: `"17.8"`)를 1차 신호로 사용한다. PRD 9-1이 대비책으로 제시한 "필드 없으면 Riot 챌린저/그마 리더보드 샘플링"은 **불필요** — Riot API(SET-16, 발급 대기 중)에 의존하지 않고 op.gg만으로 패치 감지가 가능하다. 다만 `tft_list_meta_decks` 등 나머지 5개 도구는 자체 버전 정보가 없으므로, 배치 워커는 매 수집 사이클마다 `tft_list_item_combinations`로 먼저 버전을 확인한 뒤 나머지 도구를 호출하는 순서를 권장.

## 3. is_legend_related 라벨 — 없음 (DATA-07 선행 확인)

`tft_list_augments` 응답 필드는 `apiName, desc, name, tier, imageUrl` 5개뿐이며 Legend 관련 boolean/라벨 필드가 없다(357개 증강체 전수 확인, "Legend" 문자열은 구버전 이미지 파일명에 우연히 포함된 것 하나뿐이고 실제 라벨 아님). 개발설계서 109행이 예상한 대로 **DATA-07은 수동 유지 목록 방식으로 진행해야 한다.** Set 17에 Legend 메커니즘 자체가 있는지는 이번 스파이크로 확인되지 않아 DATA-07에서 별도 확인 필요.

## 4. 아키텍처 재검토 필요 — `tft_get_play_style`은 개인 데이터 도구 (중요)

`glossary.md`는 "op.gg MCP: ... 개인 전적 조회 기능 없음"이라고 명시하지만, 실제로 `tft_get_play_style`의 입력 스키마는 `region`(필수)과 `puuid`(필수, "Riot Account PUUID... lol_get_summoner_profile 응답 또는 외부 Riot API 응답에서 얻음")를 요구한다. 즉 **이 도구 하나는 특정 플레이어의 PUUID가 있어야 호출 가능한 개인화 도구**이며, DATA-08(배치 수집 워커)이 상정한 "6개 도구 순차 호출"(패치 단위로 무작위 배치 실행) 방식과 맞지 않는다.

- 나머지 5개 도구는 파라미터 없음(`{}`) 또는 champion/item ID만 필요해 배치로 순회 호출 가능.
- **PM 결정(2026-08-04)**: `tft_get_play_style`은 DATA-08(카탈로그 배치)에서 제외하고 PGA-07(코칭 문장 생성)로 이동. PGA-01~02에서 이미 확보한 사용자 PUUID를 그대로 재사용해 호출한다. DATA-08은 이제 5개 도구만 순차 호출(WBS.xlsx 반영 완료).

## 5. 확인된 세트/버전 표기

`TFT17_` 접두사(챔피언·아이템 ID), `teamCode` 끝에 `TFTSet17` 접미사, `tft_list_item_combinations`의 `"set": 17, "version": "17.8"` — 2026-08-04 기준 현재 데이터는 **Set 17**이다. Set 18(언리얼 엔진 전환, 2026-08-12 예정) 전환 전이므로 DATA-06 스파이크(TFT DDragon 신규 구조 확인)는 아직 Set 17 구조로 확인하게 되며, 2026-08-12 전후 재확인이 필요할 수 있다.

## 6. 샘플 응답 (필드 구조 참고용, DATA-08 fixture는 반드시 합성 값으로 재작성)

`tft_list_meta_decks` 덱 1건의 `stat` 필드:
```json
{
  "originHash": "996ba2910376e3664c023245f5afe379",
  "opTier": "OP",
  "opScore": 1.53,
  "deck": { "totalCount": 1445187, "winRate": 0.2167, "top4Rate": 0.8032, "pickRate": 0.0103, "avgPlacement": 3.01 }
}
```

`tft_list_champions_for_item`(`TFT_Item_Deathblade`) 원소 1건:
```json
{ "characterId": "TFT17_MissFortune", "totalCount": 88483, "winRate": 0.1899, "top4Rate": 0.6432, "avgPlacement": 3.72 }
```

`tft_list_item_combinations` 최상위:
```json
{ "set": 17, "version": "17.8", "type": "cdragon-item", "lang": "ko_KR", "data": [ /* 아이템 배열 */ ] }
```

`tft_list_augments` (`{headers, rows}` 테이블 포맷) 1행:
```json
["TFT17_Augment_EkkoGodAugment", "이상 현상을 획득합니다...", "에코의 은총", "gold", "https://c-tft-api.op.gg/img/set/17/tft-augment/GodAugmentEkko_II.TFT_Set17.png"]
```
(순서는 `headers: [apiName, desc, name, tier, imageUrl]`와 대응)

## 다음 세션을 위한 메모

- DATA-08 구현 시 이 문서의 연결 방식(세션 핸드셰이크)과 도구별 응답 구조를 그대로 fixture 스키마 근거로 사용할 것. 값은 정책(CLAUDE.md 10.2)에 따라 합성 데이터로 치환.
- DATA-12(패치 감지)는 `tft_list_item_combinations.version` 기준으로 진행 확정(PM 승인 2026-08-04). Riot 키 확보 후 리더보드 샘플링을 보조 신호로 추가할 수도 있음 — 그때 가서 판단.
- `tft_get_play_style`은 PGA-07로 이동 확정(PM 승인 2026-08-04, WBS.xlsx DATA-08/PGA-07 TASK 설명 갱신 완료).
- DATA-07(is_legend_related)은 op.gg 라벨 없음 확정 — 수동 목록 방식으로 바로 착수 가능(Set 17 Legend 메커니즘 존재 여부만 별도 확인). 이 필드는 Riot TFT 개발자 정책("Legends/Legend 기반 증강체 승률 표시 금지", PRD 9-1)을 지키기 위한 것 — API-05/CHAT-06/FE-06의 승률 마스킹 대상을 가리는 플래그.
