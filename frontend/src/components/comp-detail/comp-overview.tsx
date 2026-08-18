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
        {/* API-16/FE-18: top4_rate·game_count는 DATA-22 컬럼 추가 전 배치가
            채운 조합에서는 null이라 조건부로만 이어붙인다. */}
        <p className="mt-2 text-caption text-text-secondary">
          평균등수 {comp.avg_place.toFixed(1)}
          {comp.top4_rate !== null &&
            ` · 4등 이내 ${Math.round(comp.top4_rate * 100)}%`}
          {comp.game_count !== null &&
            ` · 표본 ${comp.game_count.toLocaleString()}게임`}
        </p>
        <p className="mt-1 text-body text-text-secondary">
          {comp.playstyle_text}
        </p>
      </div>
    </div>
  );
}
