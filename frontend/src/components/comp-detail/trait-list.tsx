import type { TraitInComp } from "@/types/catalog";

// API-16/FE-18: comp_traits(DATA-22)를 화면에 노출. 별도 style(0~4, 프리즘
// 등급) 색상 토큰이 design-tokens.md에 아직 정의돼 있지 않아(미확정 항목
// 아님, 이번 TASK 범위 밖) 이름+발동 유닛 수만 중립 배지로 표시한다.
// 조합당 시너지 개수가 적어(보통 5~8개) augment-list.tsx의 가로 스크롤 대신
// flex-wrap으로 줄바꿈해 스크롤 없이 한 화면에 다 보이게 한다(PM 요청
// 2026-08-18 — 시너지 구성은 스크롤 없이 바로 보이는 게 더 자연스러움).
export function TraitList({ traits }: { traits: TraitInComp[] }) {
  if (traits.length === 0) {
    return null;
  }

  return (
    <div className="mt-4">
      <h2 className="text-h2 text-text-primary">시너지 구성</h2>
      <div className="mt-2 flex flex-wrap gap-3">
        {traits.map((trait) => (
          <div
            key={trait.trait_id}
            className="rounded-badge border border-border-default bg-surface-card px-3 py-2 text-body text-text-primary"
          >
            {trait.name_kr} {trait.num_units}
          </div>
        ))}
      </div>
    </div>
  );
}
