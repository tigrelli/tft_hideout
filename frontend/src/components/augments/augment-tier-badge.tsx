const TIER_CLASS: Record<string, string> = {
  gold: "bg-augment-tier-gold",
  silver: "bg-augment-tier-silver",
  prism: "bg-augment-tier-prism",
};

const TIER_LABEL: Record<string, string> = {
  gold: "골드",
  silver: "실버",
  prism: "프리즘",
};

// 조합 티어(TierBadge, OP~C)와는 다른 축인 증강체 등급 배지(ALLOWED_AUGMENT_TIERS).
export function AugmentTierBadge({ tier }: { tier: string }) {
  return (
    <span
      className={`rounded-badge px-2 py-0.5 text-label text-text-on-brand ${TIER_CLASS[tier] ?? "bg-augment-tier-silver"}`}
    >
      {TIER_LABEL[tier] ?? tier}
    </span>
  );
}
