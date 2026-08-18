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

## 7. `tft_list_meta_decks`는 랭크(챌린저/그랜드마스터/마스터) 파라미터를 지원하지 않음 (중요, 2026-08-05 재확인)

API-02(GET /catalog/tierlist)가 `rank` 쿼리 파라미터(all/challenger/grandmaster/master)로 필터링을 시도했으나, 실제 데이터가 없어 "전체" 외 모든 랭크에서 빈 결과만 나오는 것을 프론트 실사용 중 발견 — `tools/list`로 `tft_list_meta_decks`의 `inputSchema`를 직접 재확인한 결과:

```json
{ "type": "object", "properties": {}, "required": [] }
```

**파라미터가 전혀 없다.** 랭크 구간을 지정할 방법 자체가 op.gg MCP 쪽에 없으므로, "전체" 통합 데이터 하나만 받을 수 있고 챌린저/그랜드마스터/마스터별로 나눠 받는 것은 이 도구로는 원천적으로 불가능하다. 다른 5개 도구(`tft_get_champion_item_build`/`tft_list_item_combinations`/`tft_list_augments`/`tft_list_champions_for_item`/`tft_get_play_style`)의 `inputSchema`에도 rank/tier 유사 파라미터는 없음(champion_id/item_id/region+puuid만 요구).

**PM 결정(2026-08-05)**: 랭크 필터 기능 자체를 제거한다(향후 재추가 여지 없음 — 기능이 아니라 데이터 소스의 근본적 한계). API-02의 `rank` 쿼리 파라미터·`comps.rank_tier` 컬럼·프론트 랭크 드롭다운(FE-03 FilterBar)을 전부 삭제. 상세: `docs/verification/API-02-작업결과.md`(2026-08-05 갱신), `docs/verification/API-02-rollback-작업결과.md`, 진행현황.md 2026-08-05 항목.

## 8. `tft_list_meta_decks`는 정확히 10개 덱만 반환 — 페이지네이션 파라미터 없음 (2026-08-06 재확인)

PM이 op.gg 웹사이트(20개 이상의 조합이 스크롤 노출됨, 스크린샷 확인)와 우리 티어리스트 페이지(10개 조합만 노출)를 비교해 문의. 파이프라인 전 구간(batch → backend → frontend)을 점검한 결과 이 저장소 코드에는 10개로 자르는 slice/`LIMIT`/`top_n`이 어디에도 없음을 확인(`batch/opgg_client.py:131-133`, `batch/normalize.py:241-262`, `backend/routers/catalog.py`의 `get_tierlist`(195-199행, `.limit()` 없음), `frontend/src/components/tierlist/comp-grid.tsx`(16-21행, `.slice()` 없음) 전부 응답을 그대로 통과시킴).

`OpggMcpClient().list_meta_decks()`를 이 세션에서 직접 재호출해 확인한 결과 **op.gg MCP `tft_list_meta_decks` 자체가 정확히 10개 덱만 반환**(`metadata.gameStatCounts: 2,357,856`, `data` 길이 10). 위 7번 항목에서 이미 확인한 `inputSchema: {"type":"object","properties":{},"required":[]}`(파라미터 전혀 없음)이 그대로이므로, limit/page/cursor로 더 요청할 방법이 없다. 운영 DB(`comps` 테이블)도 patch 17.8 기준 정확히 10행만 존재해 매치.

**결론**: op.gg 웹사이트가 보여주는 20개 이상의 조합은 이 MCP 도구가 아닌 op.gg 자체 내부 데이터 소스(웹사이트 전용 API)에서 온 것으로 추정 — MCP 공개 도구와 op.gg 웹사이트 간의 데이터 범위 차이이며, 이 저장소 코드로는 고칠 수 없는 **데이터 소스 자체의 한계**(7번 랭크 필터 제거 건과 동일한 성격의 제약). 대안이 필요하면 (a) Riot 공식 API(SET-16, PUUID 발급 대기 중)로 별도 랭커 표본을 직접 수집하는 방안, (b) op.gg MCP의 다른 도구나 향후 스키마 변경을 주기적으로 재확인하는 방안 정도이며, 둘 다 신규 TASK로 PM 승인 필요. 현재는 10개가 이 데이터 소스로 확보 가능한 최대치임을 PM에게 보고.

## 9. `tft_list_item_combinations` 아이템 객체에 `desc`(효과 설명) 필드가 있음 — DATA-19/CHAT-14 착수 전 확인 (2026-08-08)

PM이 챗봇 답변에 아이템 효과 설명(예: "보석 건틀릿은 스킬에 치명타 판정을 부여하고...")을 포함할 수 있는지 문의. `OpggMcpClient().list_item_combinations(lang="ko_KR")`을 직접 재호출해 아이템 객체 필드를 확인한 결과 `apiName, associatedTraits, composition, desc, effects, from, icon, id, incompatibleTraits, name, tags, unique, category, org, _key, imageUrl` — **`desc` 필드가 이미 있음**(op.gg가 `"type": "cdragon-item"`이라고 밝히듯 Community Dragon 원본 그대로, `raw.communitydragon.org/latest/cdragon/tft/ko_kr.json`의 `items[]`와 동일 값으로 직접 대조 확인).

- **커버리지 실측**: 완성 아이템(`composition` 2개, 71개) 중 68개(96%)는 `<br>`/`<tftitemrules>` 같은 HTML 유사 태그만 정리하면 완전한 문장(예: "정령의 형상" → "매초 잃은 체력의 2%만큼 체력 회복"). DATA-16이 증강체 설명(`clean_augment_description()`)에서 이미 만든 정리 로직을 그대로 재사용/일반화할 수 있다.
- **미해석 참조 — 전체 838개 중 84개(10%)**: distinct 플레이스홀더 토큰을 세어보니 두 종류로 나뉜다.
  1. `@TFTUnitProperty...@` 형태(37개 토큰, 대부분) — DATA-16이 증강체에서 이미 다뤄본 것과 동일한 "미해석 수치 템플릿" 패턴("(수치 정보 없음)" 등으로 치환).
  2. `{{TFT_Keyword_...}}` 형태 — **정밀(Precision)/화상(Burn)/냉각(Chill)/상처(Wound) 딱 4종뿐.** 예: "보석 건틀릿" desc가 `"<TFTKeyword>정밀</TFTKeyword>을 얻습니다.<br><br>{{TFT_Keyword_Precision}}"`로 끝나 "정밀이 뭘 주는 효과인지"는 이 데이터만으론 알 수 없음(PM이 예시로 든 문장이 바로 이 케이스).
- **키워드 글로서리는 어디에도 없음**: `CommunityDragonClient().fetch_tft_data(lang="ko_kr")` 전체 응답의 top-level 키는 `items/setData/sets`뿐이라(재확인), `{{TFT_Keyword_*}}`를 해석해줄 별도 엔드포인트가 op.gg·Community Dragon 어디에도 없다. 4종뿐이라 DATA-07(is_legend_related)과 같은 성격의 **수동 유지 사전**으로 보강하는 것이 유일한 방법(PM 승인 필요, 정확한 문구는 착수 시 함께 정함).
- **결론**: DATA-19/CHAT-14 진행 가능. `items.description` 컬럼 + DATA-16 클렌징 로직 재사용 + 4개 키워드 수동 사전으로 대부분의 아이템에 대해 PM이 원하는 수준의 설명을 만들 수 있다.

## 10. `tft_list_meta_decks` 덱 1건의 전체 필드 구조 (2026-08-18 재확인, 미사용 필드 다수 발견)

PM이 "승률/픽률/평균등수 외에 더 받아올 수 있는 정보가 있는지" 문의(TEST-11 카테고리 G 논의 중). 실호출로 덱 1건 전체를 확인한 결과, 6번 항목의 `stat` 샘플은 `deck` 하위 필드만 보여준 요약이었고 실제로는 훨씬 많은 필드가 있음이 확인됨. 현재 `batch/normalize.py`의 `comp_rows()`/`comp_champion_rows()`가 쓰는 필드는 극히 일부뿐:

**현재 사용 중**: `id`, `name`(ko_KR만), `stat.deck.{avgPlacement,pickRate,winRate}`, `units[].{key,items,tier,cell,isCore}`

**미사용 필드(전체 목록)**:
- `stat.deck.{totalCount,compsCount,winCount,top4Count,top4Rate}` — **totalCount가 실제 표본 게임 수**(예 1,336,188), **top4Rate는 4등 이내 확률**(승률과 별개 핵심 지표, 예 0.8107). 둘 다 op.gg 웹사이트 카드에 흔히 노출되는 정보인데 이 저장소는 안 씀.
- `stat.opScore` — op.gg 자체 종합 점수(DATA-21이 자체 tier_rank로 대체했지만 opScore 자체는 참고용으로 남겨둘 수 있음)
- `stat.label{}` — `stat.deck`과 동일 구조(totalCount/avgPlacement/winRate/top4Rate 등)의 **별도 집계 세트** — `deck` vs `label`의 정확한 의미 차이(변형 통합 여부로 추정)는 미확인, 필요시 추가 조사.
- `traits[]` — 조합이 실제 발동하는 시너지 목록: `{key, style(0~4, 브론즈~프리즘), numUnits}`. 조합 상세 페이지에 시너지 구성을 보여주려면 필요한데 현재 DB 미반영.
- `badge[]` — 플레이스타일 배지: `{key: "difficulty"|"tempo"|"reroll"|"honey"|"ppm", value}`. `difficulty`(정수)·`reroll`(정수)은 의미가 비교적 명확하나 `honey`(boolean)·`ppm`(문자열 "high" 등)은 의미 불명확 — 사용하려면 op.gg 표기 대조 등 추가 조사 필요.
- `early{}` / `middle{}` — 레벨 5(초반)·레벨 7(중반) 시점 스냅샷: `units[]`(챔피언+셀, 아이템 정보는 없음), `traits[]`, `play`/`win`/`lose`(그 시점 표본 게임수). 초반→중반 전환 경로를 보여주는 플레이 가이드용 데이터인데 완전 미사용.
- `cost` — 조합 총 코스트 합
- `teamCode` — op.gg 내부 조합 인코딩 문자열(용도 불명, 아마 웹사이트 URL/공유 코드용)
- `metadata.gameStatCounts`/`metadata.gameStatDateTime` — 최상위(개별 덱이 아닌 전체) 표본수·집계시각, `_parse_updated_at()`이 `gameStatDateTime`만 이미 사용 중.

**참고**: 이 구조는 2026-08-04(DATA-05) 이후 재확인이라 필드가 그때와 달라졌을 가능성 배제 못함(예: `stat.label`은 이번에 처음 관찰) — 실제 활용 TASK 착수 시 다시 한번 raw 응답을 확인할 것.

## 다음 세션을 위한 메모

- DATA-08 구현 시 이 문서의 연결 방식(세션 핸드셰이크)과 도구별 응답 구조를 그대로 fixture 스키마 근거로 사용할 것. 값은 정책(CLAUDE.md 10.2)에 따라 합성 데이터로 치환.
- DATA-12(패치 감지)는 `tft_list_item_combinations.version` 기준으로 진행 확정(PM 승인 2026-08-04). Riot 키 확보 후 리더보드 샘플링을 보조 신호로 추가할 수도 있음 — 그때 가서 판단.
- `tft_get_play_style`은 PGA-07로 이동 확정(PM 승인 2026-08-04, WBS.xlsx DATA-08/PGA-07 TASK 설명 갱신 완료).
- DATA-07(is_legend_related)은 op.gg 라벨 없음 확정 — 수동 목록 방식으로 바로 착수 가능(Set 17 Legend 메커니즘 존재 여부만 별도 확인). 이 필드는 Riot TFT 개발자 정책("Legends/Legend 기반 증강체 승률 표시 금지", PRD 9-1)을 지키기 위한 것 — API-05/CHAT-06/FE-06의 승률 마스킹 대상을 가리는 플래그.
- DATA-19(아이템 효과 설명) 착수 시 위 9번 항목 그대로 사용: `items[].desc` 정리는 DATA-16 `clean_augment_description()` 재사용, 정밀/화상/냉각/상처 4개 키워드만 수동 사전 필요(전체 재조사 불필요).
