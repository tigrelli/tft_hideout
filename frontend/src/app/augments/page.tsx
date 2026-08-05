"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "@/lib/api-client";
import type { AugmentsResponse, AugmentTierValue } from "@/types/catalog";
import { AugmentGrid } from "@/components/augments/augment-grid";
import { TierFilterBar } from "@/components/augments/tier-filter-bar";

// 화면설계서 2.4: single-column — filter-bar(tier) / body(augment-card 그리드) /
// chat-widget-slot(전역, layout.tsx). 정적 export(FE-01) + 클라이언트 사이드
// fetch(CSR, FE-03 결정과 동일 패턴).
export default function AugmentsPage() {
  const [tier, setTier] = useState<AugmentTierValue>("all");
  const [data, setData] = useState<AugmentsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const query = tier === "all" ? "" : `?tier=${tier}`;
    fetchJson<AugmentsResponse>(`/api/v1/catalog/augments${query}`)
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setError(null);
      })
      .catch(() => {
        if (cancelled) return;
        setError("증강체 정보를 불러오지 못했습니다.");
      });
    return () => {
      cancelled = true;
    };
  }, [tier]);

  return (
    <div>
      <TierFilterBar tier={tier} onTierChange={setTier} />

      {error && <p className="text-body text-text-secondary">{error}</p>}
      {!error && !data && (
        <p className="text-body text-text-secondary">불러오는 중...</p>
      )}
      {!error && data && <AugmentGrid augments={data.augments} />}
    </div>
  );
}
