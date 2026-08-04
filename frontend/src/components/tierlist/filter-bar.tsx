"use client";

import { useState } from "react";
import { RANK_OPTIONS, type RankValue } from "@/types/catalog";
import { PatchBadge } from "@/components/tierlist/patch-badge";

interface FilterBarProps {
  patchVersion: string | null;
  rank: RankValue;
  onRankChange: (rank: RankValue) => void;
}

// 화면설계서 2.1 반응형 동작: 모바일은 filter-bar가 상단 '필터' 버튼으로 축소되고
// 탭하면 하단 시트로 패치·랭크 선택 노출. 태블릿/데스크톱은 드롭다운 유지
// (design-tokens.md "필터 UI: Dropdown / Bottom Sheet").
export function FilterBar({
  patchVersion,
  rank,
  onRankChange,
}: FilterBarProps) {
  const [isSheetOpen, setIsSheetOpen] = useState(false);

  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <PatchBadge version={patchVersion} />

      {/* 태블릿/데스크톱: 드롭다운 */}
      <div className="hidden md:block">
        <RankSelect rank={rank} onRankChange={onRankChange} />
      </div>

      {/* 모바일: 버튼 -> 바텀시트 */}
      <button
        type="button"
        className="rounded-control border border-border-input px-3 py-1.5 text-body text-text-primary md:hidden"
        onClick={() => setIsSheetOpen(true)}
        aria-haspopup="dialog"
      >
        필터 ▾
      </button>

      {isSheetOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="필터 선택"
          className="fixed inset-0 z-50 flex items-end bg-black/40 md:hidden"
          onClick={() => setIsSheetOpen(false)}
        >
          <div
            className="w-full rounded-t-card bg-surface-card p-4"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <span className="text-h2 text-text-primary">필터</span>
              <button
                type="button"
                aria-label="필터 닫기"
                onClick={() => setIsSheetOpen(false)}
              >
                ✕
              </button>
            </div>
            <RankSelect
              rank={rank}
              onRankChange={(value) => {
                onRankChange(value);
                setIsSheetOpen(false);
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function RankSelect({
  rank,
  onRankChange,
}: {
  rank: RankValue;
  onRankChange: (rank: RankValue) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-body text-text-primary">
      랭크
      <select
        value={rank}
        onChange={(event) => onRankChange(event.target.value as RankValue)}
        className="rounded-control border border-border-input px-2 py-1.5"
      >
        {RANK_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
