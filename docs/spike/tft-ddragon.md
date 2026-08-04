# DATA-06 스파이크 — TFT DDragon 신규 구조 확인

- **일자**: 2026-08-04(Set 18 전환 2026-08-12 이전 시점)
- **배경**: PRD 12장·13-2는 "TFT가 Set 18부터 언리얼 엔진으로 이전하며 기존 League Data Dragon에서 별도 TFT DDragon으로 분리된다"는 Riot 발표(2026-06-12)를 전제로, 이 PRD가 가정한 "League ddragon과 동일한 versions.json 폴링" 구조가 개발 착수 시점엔 바뀌어 있을 가능성을 점검하라고 명시.

## 1. 결론 — 별도 "TFT DDragon" 공식 엔드포인트는 아직 확인되지 않음

Riot이 발표한 신규 분리 엔드포인트로 추정되는 도메인을 직접 확인했으나 아직 존재하지 않는다(DNS 자체가 뜨지 않음):

- `https://tftdragon.leagueoflegends.com/api/versions.json` → 연결 실패
- `https://ddragon.tft.leagueoflegends.com/api/versions.json` → 연결 실패

Set 18 런칭(2026-08-12)에 맞춰 공식 발표될 가능성이 높다 — **8일 후 재확인 필요**(DATA-08 구현 직전 또는 그 이후 한 번 더 점검 권장).

## 2. 기존 League DDragon은 TFT 패치 신호로 더 이상 못 씀 (PRD 우려 확인됨)

`https://ddragon.leagueoflegends.com/api/versions.json` 호출 결과 최신값은 `"16.15.1"` — 이건 **리그 오브 레전드 클라이언트 버전**이지 TFT 세트/패치 번호(op.gg가 보여준 "17.8")와 무관하다. PRD가 우려한 대로, League ddragon의 `versions.json` 폴링은 TFT 패치 감지 신호로 쓸 수 없음이 확인됐다(어차피 DATA-05 결론대로 `tft_list_item_combinations.version`을 1차 신호로 쓰기로 했으므로 실제 영향은 없음).

## 3. 대안 — Community Dragon(비공식이지만 업계 표준 미러)이 이미 실사용 가능한 상태

`https://raw.communitydragon.org/latest/cdragon/tft/{lang}.json`(예: `en_us.json`, `ko_kr.json`)에서 TFT 전체 데이터(챔피언/아이템/증강체/특성/세트별 목록)를 200으로 확인:

- 최상위 키: `items`(전체 세트 아이템 통합 목록), `setData`(세트별 상세, `number`/`mutator`/`champions`/`augments`/`items`/`traits`), `sets`(세트 번호를 키로 한 딕셔너리 — 현재 `"1","3","4","5","7","13","14","15","16","17"`까지 존재, `"18"`은 아직 없음)
- `setData`에서 `number: 17`인 항목의 `mutator`가 `"TFTSet17"` — **DATA-05에서 확인한 op.gg의 `teamCode` 접미사 "TFTSet17"과 정확히 일치**. 두 소스가 같은 세트 식별자 체계를 쓴다는 뜻이라 ID↔이름 매핑(DATA-09)에서 안전하게 조인 가능.
- 버전 신호: `https://raw.communitydragon.org/latest/content-metadata.json` → `{"version": "16.15.8013452+branch.releases-16-15.content.release"}` — 이 역시 League 클라이언트 빌드 버전이라 TFT 세트 번호와 별개. "최신" 여부만 확인하는 용도로만 쓸 수 있음(TFT 패치 감지 신호는 여전히 DATA-05 결론인 op.gg `version` 사용).
- **추가 근거**: DATA-05에서 확인한 op.gg `tft_list_item_combinations` 응답의 `"type"` 필드 값이 정확히 `"cdragon-item"`이었다 — **op.gg 자체가 내부적으로 Community Dragon 데이터를 쓰고 있음을 시사**한다. 같은 소스를 우리도 ID↔이름 매핑에 쓰면 op.gg 응답의 ID(`TFT17_...`)와 어긋날 위험이 낮다.

## 권장 사항 (DATA-09 ID-이름 매핑 갱신 로직 설계 시 반영)

1. ID↔이름 매핑은 `raw.communitydragon.org/latest/cdragon/tft/{lang}.json`을 소스로 사용한다(공식 "TFT DDragon"이 아직 없으므로).
2. 세트 판별은 `setData[].mutator`(예: `"TFTSet17"`)를 op.gg `teamCode`/`patch_version`과 대조하는 방식으로 조인한다.
3. Community Dragon은 **비공식 커뮤니티 미러**(Riot 공식 아님, ToS/가용성 보장 없음)라는 점을 리스크로 인지한다 — 다만 LoL/TFT 개발 커뮤니티에서 사실상 표준으로 널리 쓰이는 소스다.
4. Set 18 런칭(2026-08-12) 직후 위 도메인·`sets` 딕셔너리에 `"18"` 키가 나타나는지, 공식 TFT DDragon 도메인이 그때 공개되는지 재확인 필요(DATA-08/09 구현 착수 전).

## 다음 세션을 위한 메모

DATA-09(ID-이름 매핑 갱신 로직) 착수 전에 이 문서를 먼저 참고. Set 18 런칭일(2026-08-12)이 지난 뒤라면 위 1번 재확인 단계부터 다시 밟을 것.

## 정정(2026-08-04, FE-04 착수 중 재확인) — 공식 TFT Data Dragon이 실제로는 연결됨

위 1번 결론("별도 TFT DDragon 엔드포인트 미확인")을 정정한다. FE-04에서 챔피언/아이템 이름 조회 방법을 다시 조사하며 Riot 공식 개발자 문서(`developer.riotgames.com/docs/tft`)를 WebSearch/WebFetch로 대조한 결과:

- **당시 시도한 도메인 자체가 틀렸다**: `tftdragon.leagueoflegends.com`·`ddragon.tft.leagueoflegends.com`은 존재하지 않는 추정 도메인이었음. 실제로는 **기존 `ddragon.leagueoflegends.com` 도메인 그대로**, 파일명만 `tft-champion.json`/`tft-item.json`/`tft-augments.json`로 분리돼 있었다: `https://ddragon.leagueoflegends.com/cdn/{version}/data/{locale}/tft-champion.json` — 실제로 `16.15.1`/`ko_KR`로 호출해 200 확인, Set 17 데이터 존재(`TFTSet17/Shop/TFT17_Briar` 형식 키).
- 이 키 형식(`TFT17_XXX`)이 **Community Dragon 기반으로 이미 채워둔 `champions.riot_champion_id`와 정확히 동일**함을 확인(DATA-09가 그대로 유효).
- **그래도 데이터 소스를 바꾸지 않기로 함**: 이미 Community Dragon으로 채운 데이터가 실사용 중이고(comp_champions.champion_id 86/86, recommended_items 아이템 ID 29/29 전부 정상 매칭 확인), 공식 Data Dragon 전환은 이점 대비 리스크(버전 넘버링이 TFT 세트와 무관해 "몇 버전을 언제 갱신할지"를 새로 설계해야 함)가 커서 지금 굳이 바꿀 이유가 없다고 판단. 다만 향후 Community Dragon 가용성 문제가 생기면 대체 소스로 이 URL 패턴을 우선 시도할 것.
- Set 18(2026-08-12) 런칭 이후 재확인할 때도 이 URL 패턴(`tft-champion.json` 등)을 함께 확인하는 걸 권장.
