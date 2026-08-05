import { RANK_OPTIONS, type RankValue } from "@/types/catalog";
import { ResponsiveFilter } from "@/components/common/responsive-filter";
import { PatchBadge } from "@/components/tierlist/patch-badge";

interface FilterBarProps {
  patchVersion: string | null;
  rank: RankValue;
  onRankChange: (rank: RankValue) => void;
}

// 화면설계서 2.1 반응형 동작: 모바일은 filter-bar가 상단 '필터' 버튼으로 축소되고
// 탭하면 하단 시트로 패치·랭크 선택 노출. 태블릿/데스크톱은 드롭다운 유지
// (design-tokens.md "필터 UI: Dropdown / Bottom Sheet"). 실제 Dropdown/BottomSheet
// 렌더링은 FE-11 공용 컴포넌트(ResponsiveFilter)로 통일(FE-06과 재사용).
export function FilterBar({
  patchVersion,
  rank,
  onRankChange,
}: FilterBarProps) {
  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <PatchBadge version={patchVersion} />
      <ResponsiveFilter
        dropdownLabel="랭크"
        triggerLabel="필터 ▾"
        sheetAriaLabel="필터 선택"
        sheetHeaderText="필터"
        closeAriaLabel="필터 닫기"
        value={rank}
        options={RANK_OPTIONS}
        onChange={(value) => onRankChange(value as RankValue)}
      />
    </div>
  );
}
