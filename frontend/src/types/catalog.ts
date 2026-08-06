// backend/routers/catalog.py의 Pydantic 응답 모델과 1:1 대응(API-02, API-06).

export interface CarryChampion {
  champion_id: number;
  name_kr: string;
  square_icon_url: string | null;
}

export interface CompSummary {
  id: number;
  name: string;
  tier_rank: string;
  avg_place: number;
  play_rate: number;
  win_rate: number | null;
  playstyle_text: string;
  carry_champions: CarryChampion[];
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
