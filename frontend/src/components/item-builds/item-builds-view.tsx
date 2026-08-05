"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { fetchJson } from "@/lib/api-client";
import type { ItemBuild, ItemBuildsResponse } from "@/types/catalog";
import { BuildPriorityDetail } from "@/components/item-builds/build-priority-detail";
import { ChampionSelect } from "@/components/item-builds/champion-select";
import { ItemComboList } from "@/components/item-builds/item-combo-list";

// 화면설계서 2.3: single-column — filter-bar(champion-select) / body(item-combo-list +
// build-priority-detail) / chat-widget-slot(전역, layout.tsx). GET /catalog/items/builds
// 응답이 챔피언별 상위 빌드까지 포함하므로(API-04, TOP_BUILDS_PER_CHAMPION cap) 1회
// 조회 결과에서 챔피언 드롭다운 옵션과 빌드 리스트를 함께 파생한다.
export function ItemBuildsView() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const initialChampionId = searchParams.get("champion_id");

  const [data, setData] = useState<ItemBuildsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedChampionId, setSelectedChampionId] = useState<number | null>(
    initialChampionId ? Number(initialChampionId) : null,
  );
  const [selectedBuildId, setSelectedBuildId] = useState<number | null>(null);
  const [isSheetOpen, setIsSheetOpen] = useState(false);

  useEffect(() => {
    fetchJson<ItemBuildsResponse>("/api/v1/catalog/items/builds")
      .then((result) => {
        setData(result);
        setError(null);
      })
      .catch(() => {
        setError("아이템 빌드를 불러오지 못했습니다.");
      });
  }, []);

  const champions = useMemo(() => {
    if (!data) return [];
    const nameByChampionId = new Map<number, string>();
    for (const build of data.builds) {
      if (!nameByChampionId.has(build.champion_id)) {
        nameByChampionId.set(build.champion_id, build.champion_name_kr);
      }
    }
    return [...nameByChampionId.entries()]
      .map(([championId, nameKr]) => ({ championId, nameKr }))
      .sort((a, b) => a.nameKr.localeCompare(b.nameKr, "ko"));
  }, [data]);

  const filteredBuilds = useMemo(() => {
    if (!data || selectedChampionId === null) return [];
    return data.builds.filter((b) => b.champion_id === selectedChampionId);
  }, [data, selectedChampionId]);

  // 챔피언을 바꾸면 이전 선택 id가 새 리스트에 없어질 수 있어, 렌더링 시점에
  // 유효성을 다시 계산한다(state+effect로 동기화하면 캐스케이딩 렌더가 생김).
  const effectiveBuildId = useMemo(() => {
    if (filteredBuilds.some((b) => b.id === selectedBuildId)) {
      return selectedBuildId;
    }
    return filteredBuilds[0]?.id ?? null;
  }, [filteredBuilds, selectedBuildId]);

  // 화면설계서 2.3 인터랙션: 챔피언 필터 선택 -> URL 쿼리(champion_id, patch)와 동기화.
  function handleChampionChange(championId: number) {
    setSelectedChampionId(championId);
    const params = new URLSearchParams();
    params.set("champion_id", String(championId));
    if (data) {
      params.set("patch", data.patch_version);
    }
    router.replace(`${pathname}?${params.toString()}`);
  }

  function handleSelectBuild(buildId: number) {
    setSelectedBuildId(buildId);
    setIsSheetOpen(true);
  }

  const selectedBuild: ItemBuild | null =
    filteredBuilds.find((b) => b.id === effectiveBuildId) ?? null;

  if (error) {
    return <p className="text-body text-text-secondary">{error}</p>;
  }

  if (!data) {
    return <p className="text-body text-text-secondary">불러오는 중...</p>;
  }

  return (
    <div>
      <ChampionSelect
        champions={champions}
        value={selectedChampionId}
        onChange={handleChampionChange}
      />

      <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-start">
        <div className="lg:flex-1">
          <ItemComboList
            builds={filteredBuilds}
            championSelected={selectedChampionId !== null}
            selectedBuildId={effectiveBuildId}
            onSelectBuild={handleSelectBuild}
          />
        </div>

        {/* 태블릿: item-combo-list 아래로 상하 스택(기본 흐름) / 데스크톱(lg): 좌우 분할 */}
        <div className="hidden md:block lg:flex-1">
          <BuildPriorityDetail build={selectedBuild} />
        </div>
      </div>

      {/* 모바일: build-priority-detail이 사이드 패널 대신 리스트 행 탭 시 열리는
          하단 시트(모달)로 전환(화면설계서 2.3 반응형 동작표) */}
      {isSheetOpen && selectedBuild && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="빌드 우선순위 상세"
          className="fixed inset-0 z-50 flex items-end bg-black/40 md:hidden"
          onClick={() => setIsSheetOpen(false)}
        >
          <div
            className="w-full rounded-t-card bg-surface-card p-4"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <span className="text-h2 text-text-primary">
                빌드 우선순위 상세
              </span>
              <button
                type="button"
                aria-label="닫기"
                onClick={() => setIsSheetOpen(false)}
              >
                ✕
              </button>
            </div>
            <BuildPriorityDetail build={selectedBuild} />
          </div>
        </div>
      )}
    </div>
  );
}
