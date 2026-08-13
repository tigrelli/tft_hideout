"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "@/lib/api-client";
import type { AugmentsResponse } from "@/types/catalog";
import { AugmentGrid } from "@/components/augments/augment-grid";

// 화면설계서 2.4: single-column — body(augment-card 그리드) / chat-widget-slot
// (전역, layout.tsx). 정적 export(FE-01) + 클라이언트 사이드 fetch(CSR, FE-03
// 결정과 동일 패턴). 티어 선택 필터는 PM 요청으로 제거(2026-08-06) — 항상 전체
// 티어를 보여준다(백엔드 GET /catalog/augments의 tier 쿼리 파라미터 자체는
// 남겨둔다, 다른 곳에서 재사용 가능).
export default function AugmentsPage() {
  const [data, setData] = useState<AugmentsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchJson<AugmentsResponse>("/api/v1/catalog/augments")
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
  }, []);

  return (
    <div>
      {error && <p className="text-body text-text-secondary">{error}</p>}
      {!error && !data && (
        <p className="text-body text-text-secondary">
          불러오는 중입니다. 무료 호스팅 특성상 처음 접속 시 다소 시간이 걸릴 수
          있습니다.
        </p>
      )}
      {!error && data && <AugmentGrid augments={data.augments} />}
    </div>
  );
}
