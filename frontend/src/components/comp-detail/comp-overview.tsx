import type { CompDetailResponse } from "@/types/catalog";
import { TIER_CLASS, TierBadge } from "@/components/tierlist/tier-badge";

// 화면설계서 2.2: Card `comp-overview` {"fields":["이름","tier_rank","avg_place","playstyle_text"]}
// 티어 색상 강조 바는 comp-card(티어리스트)와 동일 규칙(TIER_CLASS 공유).
export function CompOverview({ comp }: { comp: CompDetailResponse }) {
  return (
    <div className="mb-4 flex overflow-hidden rounded-card border border-border-default bg-surface-card">
      <span
        aria-hidden="true"
        className={`w-1.5 shrink-0 ${TIER_CLASS[comp.tier_rank] ?? "bg-tier-c"}`}
      />
      <div className="min-w-0 flex-1 p-4">
        <div className="flex items-center justify-between">
          <span className="text-h2 text-text-primary">{comp.name}</span>
          <TierBadge tier={comp.tier_rank} />
        </div>
        <p className="mt-2 text-caption text-text-secondary">
          평균등수 {comp.avg_place.toFixed(1)}
        </p>
        <p className="mt-1 text-body text-text-secondary">
          {comp.playstyle_text}
        </p>
      </div>
    </div>
  );
}
