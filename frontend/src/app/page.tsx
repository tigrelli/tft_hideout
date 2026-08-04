"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "@/lib/api-client";
import type { RankValue, TierlistResponse } from "@/types/catalog";
import { CompGrid } from "@/components/tierlist/comp-grid";
import { FilterBar } from "@/components/tierlist/filter-bar";

// 화면설계서 2.1: single-column — header(GNB, layout.tsx) / filter-bar / body / chat-widget-slot.
// 정적 export(FE-01) + 클라이언트 사이드 fetch(CSR, PM 결정 2026-08-04, FE-03).
export default function Home() {
  const [rank, setRank] = useState<RankValue>("all");
  const [tierlist, setTierlist] = useState<TierlistResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchJson<TierlistResponse>(`/api/v1/catalog/tierlist?rank=${rank}`)
      .then((data) => {
        if (cancelled) return;
        setTierlist(data);
        setError(null);
      })
      .catch(() => {
        if (cancelled) return;
        setError("티어리스트를 불러오지 못했습니다.");
      });
    return () => {
      cancelled = true;
    };
  }, [rank]);

  return (
    <div>
      <FilterBar
        patchVersion={tierlist?.patch_version ?? null}
        rank={rank}
        onRankChange={setRank}
      />

      {error && <p className="text-body text-text-secondary">{error}</p>}
      {!error && !tierlist && (
        <p className="text-body text-text-secondary">불러오는 중...</p>
      )}
      {!error && tierlist && <CompGrid comps={tierlist.comps} />}
    </div>
  );
}
