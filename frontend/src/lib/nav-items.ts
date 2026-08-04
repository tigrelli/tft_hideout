// IA v1.2 6.1 글로벌 내비게이션(GNB) — 4개 진입점. 조합 상세(/comps/{id})는
// GNB에 직접 노출하지 않고 티어리스트 경유로만 진입한다. /kpi는 GNB·드로어 미노출.
export const NAV_ITEMS = [
  { label: "티어리스트", href: "/" },
  { label: "아이템 빌드", href: "/items/builds" },
  { label: "증강체 정보", href: "/augments" },
  { label: "전적 분석", href: "/analysis" },
] as const;
