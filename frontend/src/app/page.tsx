"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "@/lib/api-client";
import type { TierlistResponse } from "@/types/catalog";
import { CompGrid } from "@/components/tierlist/comp-grid";
import { PatchBadge } from "@/components/tierlist/patch-badge";
import { InfoTooltip } from "@/components/common/info-tooltip";

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
        {/* FE-16(2026-08-16, PM 요청)에서 처음 추가, 2026-08-18 DATA-23(자체
            티어 스코어링을 opScore 기반 상대 순위로 재정의)에 맞춰 문구 갱신 —
            "자체 계산" 대신 "대중적으로 믿을 만한 조합의 상대 등급"이라는 새
            정의를 명시한다(docs/spike/comp-tier-scoring.md). 정보 아이콘의
            팝업에는 모집단이 op.gg 공식 웹사이트와 다른 이유까지 상세 설명을
            둔다(PM 요청). */}
        <p className="mt-2 flex items-center gap-1 text-caption text-text-tertiary">
          티어 배지는 op.gg 상위 10개 조합 중 대중적으로 꾸준히 강세를 보이는
          조합을 기준으로 매긴 상대 등급입니다. 전체 조합 중 객관적 1위를 뜻하지
          않으며, op.gg 공식 웹사이트와 다를 수 있습니다.
          <InfoTooltip text="op.gg는 랭크 필터 없이 항상 상위 10개 조합만 제공합니다(공식 웹사이트가 보여주는 20개 이상과는 애초에 모집단이 다릅니다). TFT Hideout은 이 10개 안에서 각 조합의 승률뿐 아니라 얼마나 많은 플레이어가 실제로 성공적으로 쓰는지(대중성·안정성)까지 함께 고려해 자체적으로 OP/S/A/B/C 등급을 매깁니다. 따라서 이 배지는 '전체 메타에서 객관적으로 가장 강한 조합'이 아니라 'op.gg가 보여주는 10개 조합 안에서 상대적으로 믿을 만한 조합'을 뜻합니다." />
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
