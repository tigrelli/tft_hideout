"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "@/lib/api-client";
import type { TierlistResponse } from "@/types/catalog";
import { CompGrid } from "@/components/tierlist/comp-grid";
import { PatchBadge } from "@/components/tierlist/patch-badge";

// 화면설계서 2.1: single-column — header(GNB, layout.tsx) / patch-badge / body /
// chat-widget-slot. 정적 export(FE-01) + 클라이언트 사이드 fetch(CSR, PM 결정
// 2026-08-04, FE-03). 랭크 필터(챌린저/그랜드마스터/마스터)는 2026-08-05 PM
// 결정으로 제거됨 — op.gg MCP tft_list_meta_decks가 파라미터를 아예 받지 않아
// (실호출로 확인, docs/spike/opgg-schema.md) 랭크 구간별 데이터 자체를 얻을
// 방법이 없음이 확정됨.
export default function Home() {
  const [tierlist, setTierlist] = useState<TierlistResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchJson<TierlistResponse>("/api/v1/catalog/tierlist")
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
  }, []);

  return (
    <div>
      <div className="mb-4">
        <PatchBadge version={tierlist?.patch_version ?? null} />
      </div>

      {error && <p className="text-body text-text-secondary">{error}</p>}
      {!error && !tierlist && (
        <p className="text-body text-text-secondary">불러오는 중...</p>
      )}
      {!error && tierlist && <CompGrid comps={tierlist.comps} />}
    </div>
  );
}
