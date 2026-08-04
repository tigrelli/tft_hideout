// design-tokens.md "티어 배지(권장안, 미확정 항목)"의 S/A/B/C에 더해, op.gg 실제
// 응답(opTier)에서 확인된 "OP"(S보다 상위 등급으로 취급, FE-03에서 실 데이터로
// 확인)도 매핑한다. 그 외 값은 회색(C와 동일 취급)으로 방어적으로 렌더링한다.
const TIER_CLASS: Record<string, string> = {
  OP: "bg-tier-op",
  S: "bg-tier-s",
  A: "bg-tier-a",
  B: "bg-tier-b",
  C: "bg-tier-c",
};

export function TierBadge({ tier }: { tier: string }) {
  return (
    <span
      className={`rounded-badge px-2 py-0.5 text-label text-text-on-brand ${TIER_CLASS[tier] ?? "bg-tier-c"}`}
    >
      {tier}
    </span>
  );
}
