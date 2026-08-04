import type { AugmentInComp } from "@/types/catalog";

// 화면설계서 2.2: List `augment-list` {"sortBy":"priority"} — API-03가 이미
// priority 순으로 정렬해서 내려주므로 그대로 렌더링, 가로 스크롤.
export function AugmentList({ augments }: { augments: AugmentInComp[] }) {
  if (augments.length === 0) {
    return null;
  }

  return (
    <div className="mt-4">
      <h2 className="text-h2 text-text-primary">추천 증강체</h2>
      <div className="mt-2 flex gap-3 overflow-x-auto pb-2">
        {augments.map((augment) => (
          <div
            key={augment.augment_id}
            className="shrink-0 rounded-badge border border-border-default bg-surface-card px-3 py-2 text-body text-text-primary"
          >
            {augment.name_kr}
          </div>
        ))}
      </div>
    </div>
  );
}
