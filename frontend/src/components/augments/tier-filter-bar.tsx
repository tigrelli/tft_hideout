import { AUGMENT_TIER_OPTIONS, type AugmentTierValue } from "@/types/catalog";
import { ResponsiveFilter } from "@/components/common/responsive-filter";

interface TierFilterBarProps {
  tier: AugmentTierValue;
  onTierChange: (tier: AugmentTierValue) => void;
}

// 화면설계서 2.4 반응형 동작: 모바일은 filter-tier가 상단 버튼으로 축소되고
// 탭하면 하단 시트로 티어 선택 노출. 태블릿/데스크톱은 드롭다운 유지
// (FE-03 FilterBar와 동일 패턴). 실제 Dropdown/BottomSheet 렌더링은 FE-11
// 공용 컴포넌트(ResponsiveFilter)로 통일(FE-03과 재사용).
export function TierFilterBar({ tier, onTierChange }: TierFilterBarProps) {
  return (
    <div className="mb-4 flex items-center justify-end gap-3">
      <ResponsiveFilter
        dropdownLabel="티어 선택"
        triggerLabel="티어 ▾"
        sheetAriaLabel="티어 선택"
        sheetHeaderText="티어 선택"
        closeAriaLabel="티어 선택 닫기"
        value={tier}
        options={AUGMENT_TIER_OPTIONS}
        onChange={(value) => onTierChange(value as AugmentTierValue)}
      />
    </div>
  );
}
