import type { CompDetailResponse } from "@/types/catalog";
import { TierBadge } from "@/components/tierlist/tier-badge";

// 화면설계서 2.2: Card `comp-overview` {"fields":["이름","tier_rank","avg_place","playstyle_text"]}
export function CompOverview({ comp }: { comp: CompDetailResponse }) {
  return (
    <div className="mb-4 rounded-card border border-border-default bg-surface-card p-4">
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
  );
}
