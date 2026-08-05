"use client";

import { useState } from "react";
import {
  FilterDropdown,
  type FilterOption,
} from "@/components/common/filter-dropdown";

// FE-11: 데스크톱/태블릿 Dropdown, 모바일 BottomSheet 공용 컴포넌트
// (디자인가이드 6.2, design-tokens.md "필터 UI: Dropdown / Bottom Sheet").
// FE-03 FilterBar·FE-06 TierFilterBar가 각자 구현하던 동일 패턴을 통합 —
// desktop/mobile 두 렌더링 모두 같은 value/onChange를 공유해 상태가 항상
// 동기화된다(WBS 테스트 요구사항).
export function ResponsiveFilter({
  dropdownLabel,
  triggerLabel,
  sheetAriaLabel,
  sheetHeaderText,
  closeAriaLabel,
  value,
  options,
  onChange,
}: {
  dropdownLabel: string;
  triggerLabel: string;
  sheetAriaLabel: string;
  sheetHeaderText: string;
  closeAriaLabel: string;
  value: string;
  options: readonly FilterOption[];
  onChange: (value: string) => void;
}) {
  const [isSheetOpen, setIsSheetOpen] = useState(false);

  return (
    <>
      {/* 태블릿/데스크톱: 드롭다운 */}
      <div className="hidden md:block">
        <FilterDropdown
          label={dropdownLabel}
          value={value}
          options={options}
          onChange={onChange}
        />
      </div>

      {/* 모바일: 버튼 -> 바텀시트 */}
      <button
        type="button"
        className="rounded-control border border-border-input px-3 py-1.5 text-body text-text-primary md:hidden"
        onClick={() => setIsSheetOpen(true)}
        aria-haspopup="dialog"
      >
        {triggerLabel}
      </button>

      {isSheetOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={sheetAriaLabel}
          className="fixed inset-0 z-50 flex items-end bg-black/40 md:hidden"
          onClick={() => setIsSheetOpen(false)}
        >
          <div
            className="w-full rounded-t-card bg-surface-card p-4"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <span className="text-h2 text-text-primary">
                {sheetHeaderText}
              </span>
              <button
                type="button"
                aria-label={closeAriaLabel}
                onClick={() => setIsSheetOpen(false)}
              >
                ✕
              </button>
            </div>
            <FilterDropdown
              label={dropdownLabel}
              value={value}
              options={options}
              onChange={(nextValue) => {
                onChange(nextValue);
                setIsSheetOpen(false);
              }}
            />
          </div>
        </div>
      )}
    </>
  );
}
