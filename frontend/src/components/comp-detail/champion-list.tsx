import type { ChampionInComp } from "@/types/catalog";

// 화면설계서 2.2: List `champion-list` {"fields":["is_carry/is_sub 구분","recommended_items"]},
// 가로 스크롤. 캐리/서브 구분은 design-tokens.md에서 이미 확정된 보더 스펙
// (캐리 accent-carry #E59933 2px, 서브는 기본 보더 1px)을 그대로 적용한다.
export function ChampionList({ champions }: { champions: ChampionInComp[] }) {
  return (
    <div>
      <h2 className="text-h2 text-text-primary">챔피언 구성</h2>
      <div className="mt-2 flex gap-3 overflow-x-auto pb-2">
        {champions.map((champion) => (
          <div
            key={champion.champion_id}
            data-carry={champion.is_carry}
            className={
              "w-32 shrink-0 rounded-card bg-surface-card p-3 " +
              (champion.is_carry
                ? "border-2 border-accent-carry"
                : "border border-border-default")
            }
          >
            <p className="text-body font-bold text-text-primary">
              {champion.name_kr}
            </p>
            {champion.recommended_item_names.length > 0 && (
              <p className="mt-1 text-caption text-text-secondary">
                {champion.recommended_item_names.join(", ")}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
