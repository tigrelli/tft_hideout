import Link from "next/link";
import type { AugmentSummary } from "@/types/catalog";
import { AugmentTierBadge } from "@/components/augments/augment-tier-badge";

// 화면설계서 2.4: Card `augment-card` {"fields":["이름","티어","설명",
// "승률(is_legend_related=true면 숨김)"]}, state default/no-winrate. 검증 규칙:
// is_legend_related=true인 항목은 승률 필드 미표시(PRD 10-1·12장, policies.md 1번
// — 정책상 비표시일 뿐 에러 아님). 백엔드(API-05)가 이미 win_rate를 null로
// 강제하지만, 프론트에서도 is_legend_related만 보고 문구를 결정해 숫자가 DOM에
// 남을 가능성을 원천 차단한다(이중 방어).
// whitespace-pre-line: DATA-16이 배치에서 <br>를 실제 개행(\n)으로 정리하므로
// 여기서 그 개행을 그대로 렌더링한다.
export function AugmentCard({ augment }: { augment: AugmentSummary }) {
  return (
    <div className="rounded-card border border-border-default bg-surface-card p-4">
      <div className="flex items-center justify-between">
        <span className="text-h2 text-text-primary">{augment.name_kr}</span>
        <AugmentTierBadge tier={augment.tier} />
      </div>

      <p className="mt-2 wrap-break-word whitespace-pre-line text-body text-text-secondary">
        {augment.description}
      </p>

      <p className="mt-2 text-caption text-text-secondary">
        {augment.is_legend_related
          ? "승률 표시 안함 (Riot 정책)"
          : augment.win_rate !== null
            ? `승률 ${(augment.win_rate * 100).toFixed(0)}%`
            : "승률 정보 없음"}
      </p>

      {augment.related_comp_ids.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {augment.related_comp_ids.map((compId) => (
            <Link
              key={compId}
              href={`/comps?id=${compId}`}
              className="text-caption text-primary hover:underline"
            >
              관련 조합 보기 →
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
