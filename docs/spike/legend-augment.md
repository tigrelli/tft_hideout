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

- `is_legend_related` 컬럼과 API-05/CHAT-06/FE-06의 마스킹 로직 자체는 그대로 구현한다(정책은 세트가 바뀌면 언제든 다시 필요해질 수 있으므로 로직을 생략하지 않는다).
- **PM 결정(2026-08-04)**: Set 17엔 추적할 대상이 아예 없으므로 목록 관리 인프라(시드 파일 등)를 지금 만들지 않는다. DATA-08/DATA-10은 `is_legend_related`를 **무조건 `false`로 채운다.** 실제 세트별 수동 목록 구조는 Legends 메커니즘이 있는 세트가 등장했을 때 그 시점에 필요한 만큼만 만든다(YAGNI — 없는 것을 관리하는 빈 인프라를 미리 짓지 않는다).
- 참고로 Riot 정책이 실제로 금지하는 건 Set 9/9.5 당시의 "Legend(플레이어가 고르는 캐릭터) 자체의 승률"과 "그 Legend 전용 증강체의 승률"이며, **조합(comp) 단위 승률은 이 정책 대상이 아니다** — `comps.win_rate`는 이 정책과 무관하게 항상 노출 가능(policies.md 1번 참고, 아래 섹션 4).

## 4. (참고) 조합 단위 승률은 별개 — 챗봇 메타 조회 정책

"S티어 덱 알려줘"/"강한 리롤 덱 알려줘"/"AP 덱 추천해줘" 같은 질문은 `is_legend_related` 마스킹과 무관하다. 이 질문들은 glossary.md의 챗봇 의도 4분류 중 **1번 "조합 추천"**(검색 대상: `comps`, `comp_champions`, `comp_augments`)에 해당하고, `comps.win_rate`는 그대로 답변에 포함해도 된다.

- "S티어 덱" → `comps.tier_rank`(구조화 필드, S/A/B/C)로 직접 필터
- "리롤 덱"/"AP 덱" → 구조화 필드가 없어 `comps.playstyle_text`(자유 텍스트)를 임베딩한 벡터 검색으로 대응(CHAT-02 하이브리드 검색이 담당, 아직 미착수)

즉 정책 변경이나 스키마 추가 없이 기존 설계(4분류 의도 + comps 검색)로 이미 커버된다.

## 다음 세션을 위한 메모

DATA-08/DATA-10 구현 시 `is_legend_related` 값은 이 문서의 수동 목록(현재 Set 17은 빈 배열)을 조회해 채운다. Set 18 전환(2026-08-12) 이후에는 새 세트의 증강체 목록에서 이 스파이크와 동일한 방법(apiName "legend" 키워드 검색 + 활성 목록 대조)으로 재확인해야 한다.
