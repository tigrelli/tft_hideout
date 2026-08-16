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
        {/* FE-16(2026-08-16, PM 요청): 티어 배지가 op.gg 공식 웹사이트와 다르게 보인다는
            제보를 조사한 결과 데이터 소스 자체가 다름을 확인(DATA-21 작업결과 참고) —
            DATA-21에서 뱃지를 자체 계산으로 전환한 사실을 사용자에게 안내한다. */}
        <p className="mt-2 text-caption text-text-tertiary">
          티어 배지는 op.gg 공개 데이터(MCP)의 승률·평균 등수를 바탕으로 자체
          계산한 값으로, op.gg 공식 웹사이트와 다를 수 있습니다.
        </p>
      </div>

      {error && <p className="text-body text-text-secondary">{error}</p>}
      {!error && !tierlist && (
        <p className="text-body text-text-secondary">
          불러오는 중입니다. 무료 호스팅 특성상 처음 접속 시 다소 시간이 걸릴 수
          있습니다.
        </p>
      )}
      {!error && tierlist && <CompGrid comps={tierlist.comps} />}
    </div>
  );
}
