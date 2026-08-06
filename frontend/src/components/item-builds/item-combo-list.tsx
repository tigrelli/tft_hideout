import type { ItemBuild } from "@/types/catalog";
import { ItemIconRow } from "@/components/comp-detail/item-icon-row";

// 화면설계서 2.3: List `item-combo-list` {"fields":["item_combination","play_rate",
// "avg_place","win_rate"]}. 행 탭 시 build-priority-detail이 갱신되고 모바일에서는
// 하단 시트가 열린다(반응형 동작표).
export function ItemComboList({
  builds,
  championSelected,
  selectedBuildId,
  onSelectBuild,
}: {
  builds: ItemBuild[];
  championSelected: boolean;
  selectedBuildId: number | null;
  onSelectBuild: (buildId: number) => void;
}) {
  if (!championSelected) {
    return (
      <p className="text-body text-text-secondary">
        챔피언을 선택하면 아이템 조합 리스트가 표시됩니다.
      </p>
    );
  }

  if (builds.length === 0) {
    return (
      <p className="text-body text-text-secondary">
        아직 집계된 아이템 빌드 데이터가 없습니다.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {builds.map((build) => (
        <li key={build.id}>
          <button
            type="button"
            onClick={() => onSelectBuild(build.id)}
            aria-pressed={build.id === selectedBuildId}
            className={`w-full rounded-card border p-4 text-left ${
              build.id === selectedBuildId
                ? "border-primary"
                : "border-border-default hover:border-primary"
            } bg-surface-card`}
          >
            <p className="text-body font-bold text-text-primary">
              {build.item_combination_names.join(" + ")}
            </p>
            <ItemIconRow
              names={build.item_combination_names}
              icons={build.item_combination_icons}
              itemIds={build.item_combination}
              size={40}
            />
            <p className="mt-1 text-caption text-text-secondary">
              픽률 {(build.play_rate * 100).toFixed(0)}% · 평균등수{" "}
              {build.avg_place.toFixed(1)} · 승률{" "}
              {(build.win_rate * 100).toFixed(0)}%
            </p>
          </button>
        </li>
      ))}
    </ul>
  );
}
