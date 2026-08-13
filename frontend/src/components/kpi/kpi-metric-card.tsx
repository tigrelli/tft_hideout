import type { ReactNode } from "react";

// design-tokens.md 카드 스펙(보더 #D9D9D9 1px, radius 8px, 패딩 16px) 재사용.
export function KpiMetricCard({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-card border border-border-default bg-surface-card p-4">
      <h2 className="text-h2 text-text-primary">{label}</h2>
      <div className="mt-2 flex flex-col gap-1 text-body text-text-primary">
        {children}
      </div>
    </div>
  );
}
