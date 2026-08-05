"use client";

import { useState } from "react";
import { AUGMENT_TIER_OPTIONS, type AugmentTierValue } from "@/types/catalog";

interface TierFilterBarProps {
  tier: AugmentTierValue;
  onTierChange: (tier: AugmentTierValue) => void;
}

// 화면설계서 2.4 반응형 동작: 모바일은 filter-tier가 상단 버튼으로 축소되고
// 탭하면 하단 시트로 티어 선택 노출. 태블릿/데스크톱은 드롭다운 유지
// (FE-03 FilterBar와 동일 패턴, design-tokens.md "필터 UI: Dropdown / Bottom Sheet").
export function TierFilterBar({ tier, onTierChange }: TierFilterBarProps) {
  const [isSheetOpen, setIsSheetOpen] = useState(false);

  return (
    <div className="mb-4 flex items-center justify-end gap-3">
      {/* 태블릿/데스크톱: 드롭다운 */}
      <div className="hidden md:block">
        <TierSelect tier={tier} onTierChange={onTierChange} />
      </div>

      {/* 모바일: 버튼 -> 바텀시트 */}
      <button
        type="button"
        className="rounded-control border border-border-input px-3 py-1.5 text-body text-text-primary md:hidden"
        onClick={() => setIsSheetOpen(true)}
        aria-haspopup="dialog"
      >
        티어 ▾
      </button>

      {isSheetOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="티어 선택"
          className="fixed inset-0 z-50 flex items-end bg-black/40 md:hidden"
          onClick={() => setIsSheetOpen(false)}
        >
          <div
            className="w-full rounded-t-card bg-surface-card p-4"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <span className="text-h2 text-text-primary">티어 선택</span>
              <button
                type="button"
                aria-label="티어 선택 닫기"
                onClick={() => setIsSheetOpen(false)}
              >
                ✕
              </button>
            </div>
            <TierSelect
              tier={tier}
              onTierChange={(value) => {
                onTierChange(value);
                setIsSheetOpen(false);
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function TierSelect({
  tier,
  onTierChange,
}: {
  tier: AugmentTierValue;
  onTierChange: (tier: AugmentTierValue) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-body text-text-primary">
      티어 선택
      <select
        value={tier}
        onChange={(event) =>
          onTierChange(event.target.value as AugmentTierValue)
        }
        className="rounded-control border border-border-input px-2 py-1.5"
      >
        {AUGMENT_TIER_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
