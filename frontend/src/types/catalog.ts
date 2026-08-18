// backend/routers/catalog.py의 Pydantic 응답 모델과 1:1 대응(API-02, API-06).

export interface CarryChampion {
  champion_id: number;
  name_kr: string;
  square_icon_url: string | null;
}

// API-16: op.gg style 0(미발동)~4(프리즘 등급).
export interface TraitInComp {
  trait_id: number;
  name_kr: string;
  name_en: string;
  style: number;
  num_units: number;
}

export interface CompSummary {
  id: number;
  name: string;
  tier_rank: string;
  avg_place: number;
  play_rate: number;
  win_rate: number | null;
  // DATA-22/API-16: 이 컬럼 추가 전 배치가 채운 조합은 null.
  top4_rate: number | null;
  game_count: number | null;
  playstyle_text: string;
  carry_champions: CarryChampion[];
  traits: TraitInComp[];
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
  square_icon_url: string | null;
  recommended_items: string[];
  recommended_item_names: string[];
  recommended_item_icons: (string | null)[];
  cell_x: number | null;
  cell_y: number | null;
  star_level: number | null;
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
  top4_rate: number | null;
  game_count: number | null;
  playstyle_text: string;
  champions: ChampionInComp[];
  augments: AugmentInComp[];
  traits: TraitInComp[];
}

export interface ItemBuild {
  id: number;
  champion_id: number;
  champion_name_kr: string;
  champion_name_en: string;
  champion_square_icon_url: string | null;
  item_combination: string[];
  item_combination_names: string[];
  item_combination_icons: (string | null)[];
  play_rate: number;
  avg_place: number;
  win_rate: number;
}

export interface ItemBuildsResponse {
  patch_version: string;
  champion_id: number | null;
  builds: ItemBuild[];
}

export interface ItemComponent {
  riot_item_id: string;
  name_kr: string;
  square_icon_url: string | null;
}

export interface ItemSummary {
  riot_item_id: string;
  name_kr: string;
  square_icon_url: string | null;
  components: ItemComponent[];
}

export interface ItemsResponse {
  patch_version: string;
  items: ItemSummary[];
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
  image_url: string | null;
}

export interface AugmentsResponse {
  patch_version: string;
  augments: AugmentSummary[];
}

export interface CurrentPatchResponse {
  version: string;
  set_number: number;
  released_at: string;
  detected_at: string;
}
