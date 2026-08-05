// backend/routers/catalog.py의 Pydantic 응답 모델과 1:1 대응(API-02, API-06).

export interface CompSummary {
  id: number;
  name: string;
  tier_rank: string;
  avg_place: number;
  play_rate: number;
  win_rate: number | null;
  playstyle_text: string;
  carry_champion_ids: number[];
}

export interface TierlistResponse {
  patch_version: string;
  comps: CompSummary[];
}

export interface ChampionInComp {
  champion_id: number;
  name_kr: string;
  name_en: string;
  is_carry: boolean;
  recommended_items: string[];
  recommended_item_names: string[];
}

export interface AugmentInComp {
  augment_id: number;
  name_kr: string;
  name_en: string;
  priority: number;
}

export interface CompDetailResponse {
  id: number;
  patch_version: string;
  name: string;
  tier_rank: string;
  avg_place: number;
  play_rate: number;
  win_rate: number | null;
  playstyle_text: string;
  champions: ChampionInComp[];
  augments: AugmentInComp[];
}

export interface ItemBuild {
  id: number;
  champion_id: number;
  champion_name_kr: string;
  champion_name_en: string;
  item_combination: string[];
  item_combination_names: string[];
  play_rate: number;
  avg_place: number;
  win_rate: number;
}

export interface ItemBuildsResponse {
  patch_version: string;
  champion_id: number | null;
  builds: ItemBuild[];
}

export interface AugmentSummary {
  id: number;
  name_kr: string;
  name_en: string;
  tier: string;
  description: string;
  is_legend_related: boolean;
  win_rate: number | null;
  related_comp_ids: number[];
}

export interface AugmentsResponse {
  patch_version: string;
  augments: AugmentSummary[];
}

// API-05 ALLOWED_AUGMENT_TIERS(backend/routers/catalog.py, DATA-05 스파이크로
// 확정된 op.gg tft_list_augments 실제 tier 값 3종).
export const AUGMENT_TIER_OPTIONS = [
  { value: "all", label: "전체" },
  { value: "gold", label: "골드" },
  { value: "silver", label: "실버" },
  { value: "prism", label: "프리즘" },
] as const;

export type AugmentTierValue = (typeof AUGMENT_TIER_OPTIONS)[number]["value"];

export interface CurrentPatchResponse {
  version: string;
  set_number: number;
  released_at: string;
  detected_at: string;
}
