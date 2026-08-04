# DATA-07 스파이크 — is_legend_related 판별 방법 확인

- **일자**: 2026-08-04
- **배경**: Riot TFT 개발자 정책에 "Legends 및 Legend 기반 증강체의 승률은 표시할 수 없다"는 조항이 있어(PRD 9-1), 어떤 증강체가 그 대상인지 판별하는 방법이 필요하다. DATA-05에서 op.gg 응답에 관련 라벨이 없음은 이미 확인했고, 이번 스파이크는 (1) 라벨 부재 재확인 (2) 현재 세트(17)에 Legends 메커니즘 자체가 존재하는지 확인 (3) 존재한다면 수동 목록 설계까지가 범위다.

## 1. op.gg 응답에 라벨 없음 (DATA-05 재확인)

`tft_list_augments` 필드는 `apiName, desc, name, tier, imageUrl` 5개뿐이고 `tier` 값도 `{gold, silver, prism}` 3종뿐이라 Legend 여부를 나타내는 필드가 없다. (DATA-05에서 이미 확인된 사실, 재검증 완료)

## 2. Set 17에 "Legends" 메커니즘이 실제로 존재하는지 — 없음으로 판단

Community Dragon 전체 TFT 데이터(모든 세트)에서 apiName에 `legend`가 들어간 증강체를 검색한 결과 5개 전부 `TFT9_` 접두사(과거 세트 9의 증강체)였다:

```
TFT9_Augment_Legend_BardPlaybook2
TFT9_Augment_Legend_HighEndSector
TFT9_Augment_Legend_PandorasItems2
TFT9_Augment_Legend_PandorasRadiantBox
TFT9_Augment_Legend_PumpingUp2
```

Set 17(`TFTSet17`)의 활성 증강체 풀(275개) 안에는 이 중 `TFT9_Augment_Legend_HighEndSector` **하나만 참조로 남아있으나**, op.gg가 실제로 서빙하는 현재 증강체 목록(357개, 실제 플레이 가능한 것만 포함하는 것으로 보임)에는 이 apiName이 **없다** — 즉 실제 게임에서 뽑을 수 있는 상태가 아닌 것으로 보인다(레거시 데이터 잔재로 추정). Set 17 네이티브(`TFT17_` 접두사) 증강체 중에는 "legend" 키워드가 하나도 없고, Set 17 특성(traits) 목록에도 없다. Community Dragon의 세트 데이터 스키마 자체에도 `legends`라는 별도 카테고리가 없다(augments/champions/items/traits뿐).

**결론: Set 17에는 활성화된 "Legends" 증강체 메커니즘이 없다.**

## 3. 판별 방법 확정

개발설계서 109행이 이미 제시한 방식을 그대로 채택한다:

> "op.gg 응답에 이 라벨이 있다는 보장이 없어 있으면 그대로 사용하고 없으면 세트별 Legend 증강체를 수동으로 유지하는 목록으로 대체한다. 현재 세트에 Legends 메커니즘 자체가 없으면 전 행 false로 두면 되므로 로직은 그대로 두고 값만 비워두면 된다."

- `is_legend_related` 컬럼과 API-05/CHAT-06/FE-06의 마스킹 로직은 그대로 구현한다(정책은 세트가 바뀌면 언제든 다시 필요해질 수 있으므로 로직 자체를 생략하지 않는다).
- **Set 17 데이터는 수동 유지 목록을 빈 배열로 시작** — 모든 증강체 행에 `is_legend_related=false`.
- 코드 저장소 내 시드 데이터로 세트별 수동 목록을 관리한다(예: `backend/data/legend_augments.py` 또는 마이그레이션 시드 — DATA-08/DATA-10 구현 시 위치 확정). 목록 형식: `{set_number: [apiName, ...]}`.
- 향후 세트 전환 시 Legends 메커니즘이 재도입되면, 그 시점에 새 세트 번호 키로 목록을 채운다(별도 TASK 불필요, 목록 갱신만).

## 다음 세션을 위한 메모

DATA-08/DATA-10 구현 시 `is_legend_related` 값은 이 문서의 수동 목록(현재 Set 17은 빈 배열)을 조회해 채운다. Set 18 전환(2026-08-12) 이후에는 새 세트의 증강체 목록에서 이 스파이크와 동일한 방법(apiName "legend" 키워드 검색 + 활성 목록 대조)으로 재확인해야 한다.
