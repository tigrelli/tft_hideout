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
  rank: string;
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

export interface CurrentPatchResponse {
  version: string;
  set_number: number;
  released_at: string;
  detected_at: string;
}

// API-02 ALLOWED_RANKS(backend/routers/catalog.py). "all" 외 나머지는 실제 랭크
// 구간 데이터가 아직 없어(DATA-05 스파이크 이후 확정 필요) 선택은 가능하나 결과가
// 비어있을 수 있다.
export const RANK_OPTIONS = [
  { value: "all", label: "전체" },
  { value: "challenger", label: "챌린저" },
  { value: "grandmaster", label: "그랜드마스터" },
  { value: "master", label: "마스터" },
] as const;

export type RankValue = (typeof RANK_OPTIONS)[number]["value"];
