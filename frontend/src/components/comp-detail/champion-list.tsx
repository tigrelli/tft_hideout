import Link from "next/link";
import type { ChampionInComp } from "@/types/catalog";
import { ItemIconRow } from "@/components/comp-detail/item-icon-row";

// 화면설계서 2.2: List `champion-list` {"fields":["is_carry/is_sub 구분","recommended_items"]}.
// 모바일(md 미만) 전용 — 세로로 쌓아 스크롤 없이 전부 보이게 한다. 웹/태블릿(md
// 이상)은 HexBoard(hex-board.tsx)가 대신 렌더링된다(comp-detail-view.tsx에서
// 반응형으로 둘 중 하나만 표시).
// 캐리/서브 구분은 design-tokens.md에서 이미 확정된 보더 스펙
// (캐리 accent-carry #E59933 2px, 서브는 기본 보더 1px)을 그대로 적용한다.
// 챔피언을 탭하면 해당 챔피언의 아이템 빌드 화면으로 이동한다(PM 요청
// 2026-08-06). ItemIconRow의 재료 아이콘은 자체 stopPropagation으로 이
// 링크 이동과 충돌하지 않는다.
export function ChampionList({ champions }: { champions: ChampionInComp[] }) {
  return (
    <div>
      <h2 className="text-h2 text-text-primary">챔피언 구성</h2>
      <div className="mt-2 flex flex-col gap-3">
        {champions.map((champion) => (
          <Link
            key={champion.champion_id}
            href={`/items/builds?champion_id=${champion.champion_id}`}
            data-carry={champion.is_carry}
            className={
              "block w-full rounded-card bg-surface-card p-3 hover:border-primary " +
              (champion.is_carry
                ? "border-2 border-accent-carry"
                : "border border-border-default")
            }
          >
            <p className="text-body font-bold text-text-primary">
              {champion.name_kr}
            </p>
            <ItemIconRow
              names={champion.recommended_item_names}
              icons={champion.recommended_item_icons}
              itemIds={champion.recommended_items}
            />
          </Link>
        ))}
      </div>
    </div>
  );
}
