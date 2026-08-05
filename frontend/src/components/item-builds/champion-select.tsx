export interface ChampionOption {
  championId: number;
  nameKr: string;
}

// 화면설계서 2.3: Dropdown `filter-champion` {"label":"챔피언 선택"}, state
// default/open. 반응형 동작표에 이 드롭다운 자체는 별도 명시가 없어(바텀시트로
// 전환되는 건 build-priority-detail 패널뿐, 모바일 와이어프레임도 이 드롭다운을
// 그대로 상단에 유지) 브레이크포인트와 무관하게 동일한 셀렉트로 구현한다.
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
    <label className="flex items-center gap-2 text-body text-text-primary">
      챔피언 선택
      <select
        value={value ?? ""}
        onChange={(event) => onChange(Number(event.target.value))}
        className="rounded-control border border-border-input px-2 py-1.5"
      >
        <option value="" disabled>
          챔피언을 선택하세요
        </option>
        {champions.map((champion) => (
          <option key={champion.championId} value={champion.championId}>
            {champion.nameKr}
          </option>
        ))}
      </select>
    </label>
  );
}
