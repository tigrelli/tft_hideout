import { FilterDropdown } from "@/components/common/filter-dropdown";

export interface ChampionOption {
  championId: number;
  nameKr: string;
}

// 화면설계서 2.3: Dropdown `filter-champion` {"label":"챔피언 선택"}, state
// default/open. 반응형 동작표에 이 드롭다운 자체는 별도 명시가 없어(바텀시트로
// 전환되는 건 build-priority-detail 패널뿐, 모바일 와이어프레임도 이 드롭다운을
// 그대로 상단에 유지) 브레이크포인트와 무관하게 동일한 셀렉트로 구현한다(FE-11
// 공용 FilterDropdown 재사용, 값 타입만 숫자 id<->문자열로 이 자리에서 변환).
export function ChampionSelect({
  champions,
  value,
  onChange,
}: {
  champions: ChampionOption[];
  value: number | null;
  onChange: (championId: number) => void;
}) {
  return (
    <FilterDropdown
      label="챔피언 선택"
      value={value !== null ? String(value) : ""}
      options={champions.map((champion) => ({
        value: String(champion.championId),
        label: champion.nameKr,
      }))}
      placeholder="챔피언을 선택하세요"
      onChange={(nextValue) => onChange(Number(nextValue))}
    />
  );
}
