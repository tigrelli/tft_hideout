import type { ItemBuild } from "@/types/catalog";

// 화면설계서 2.3: Panel `build-priority-detail`, state default/empty(챔피언 미선택).
// 데스크톱/태블릿에서는 인라인 패널로, 모바일에서는 바텀 시트 안에 그대로 재사용된다
// (item-builds-view.tsx에서 래핑).
export function BuildPriorityDetail({ build }: { build: ItemBuild | null }) {
  if (build === null) {
    return (
      <div className="rounded-card border border-border-default bg-surface-card p-4">
        <p className="text-body text-text-secondary">챔피언을 선택해주세요.</p>
      </div>
    );
  }

  return (
    <div className="rounded-card border border-border-default bg-surface-card p-4">
      <p className="text-h2 text-text-primary">
        {build.champion_name_kr}: {build.item_combination_names.join(" → ")}
      </p>
      <p className="mt-2 text-caption text-text-secondary">
        픽률 {(build.play_rate * 100).toFixed(0)}% · 평균등수{" "}
        {build.avg_place.toFixed(1)} · 승률 {(build.win_rate * 100).toFixed(0)}%
      </p>
    </div>
  );
}
