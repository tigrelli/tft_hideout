"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { fetchJson } from "@/lib/api-client";
import type { CompDetailResponse } from "@/types/catalog";
import { AugmentList } from "@/components/comp-detail/augment-list";
import { BackButton } from "@/components/comp-detail/back-button";
import { ChampionList } from "@/components/comp-detail/champion-list";
import { CompOverview } from "@/components/comp-detail/comp-overview";
import { HexBoard } from "@/components/comp-detail/hex-board";

// 화면설계서 2.2: single-column — header(back-btn) / overview / champion-list /
// augment-list / chat-widget-slot(전역, layout.tsx). cta(아이템 빌드 더보기)는
// 챔피언 구성 아이템을 이미지로 바로 보여주게 되면서 제거(PM 결정 2026-08-06).
// URL은 쿼리스트링
// (/comps?id=)이라 useSearchParams로 id를 읽어 클라이언트에서 조회한다(PM 결정
// 2026-08-04, FE-04 작업결과 참고).
export function CompDetailView() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id");

  const [comp, setComp] = useState<CompDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      return;
    }
    fetchJson<CompDetailResponse>(`/api/v1/catalog/comps/${id}`)
      .then((data) => {
        setComp(data);
        setError(null);
      })
      .catch(() => {
        setError("조합을 찾을 수 없습니다.");
      });
  }, [id]);

  if (!id) {
    return (
      <p className="text-body text-text-secondary">
        잘못된 접근입니다. 티어리스트에서 조합을 선택해주세요.
      </p>
    );
  }

  if (error) {
    return (
      <div>
        <BackButton patchVersion={null} />
        <p className="text-body text-text-secondary">{error}</p>
      </div>
    );
  }

  if (!comp) {
    return (
      <div>
        <BackButton patchVersion={null} />
        <p className="text-body text-text-secondary">
          불러오는 중입니다. 무료 호스팅 특성상 처음 접속 시 다소 시간이 걸릴 수
          있습니다.
        </p>
      </div>
    );
  }

  return (
    <div>
      <BackButton patchVersion={comp.patch_version} />
      <CompOverview comp={comp} />
      <div className="md:hidden">
        <ChampionList champions={comp.champions} />
      </div>
      <div className="hidden md:block">
        <h2 className="text-h2 text-text-primary">챔피언 구성</h2>
        <div className="mt-2">
          <HexBoard champions={comp.champions} />
        </div>
      </div>
      <AugmentList augments={comp.augments} />
    </div>
  );
}
