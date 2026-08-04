import type { CompSummary } from "@/types/catalog";
import { CompCard } from "@/components/tierlist/comp-card";

// design-tokens.md 카탈로그 그리드: 데스크톱 3~4열(gap 16px) · 태블릿 2열(gap 16px)
// · 모바일 1열 스택(gap 12px). CLAUDE.md 브레이크포인트(모바일 기본/md:태블릿/lg:데스크톱)
// 그대로 매핑.
export function CompGrid({ comps }: { comps: CompSummary[] }) {
  if (comps.length === 0) {
    return (
      <p className="text-body text-text-secondary">
        조건에 맞는 조합이 없습니다.
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 md:gap-4 lg:grid-cols-3">
      {comps.map((comp) => (
        <CompCard key={comp.id} comp={comp} />
      ))}
    </div>
  );
}
