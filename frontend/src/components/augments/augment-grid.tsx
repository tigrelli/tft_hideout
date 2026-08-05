import type { AugmentSummary } from "@/types/catalog";
import { AugmentCard } from "@/components/augments/augment-card";

// 화면설계서 2.4 반응형 동작표: 모바일 1열 스택 / 태블릿 2열 그리드 / 데스크톱
// 기존 카드 그리드 유지 — CompGrid와 동일한 브레이크포인트 매핑.
export function AugmentGrid({ augments }: { augments: AugmentSummary[] }) {
  if (augments.length === 0) {
    return (
      <p className="text-body text-text-secondary">
        조건에 맞는 증강체가 없습니다.
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 md:gap-4 lg:grid-cols-3">
      {augments.map((augment) => (
        <AugmentCard key={augment.id} augment={augment} />
      ))}
    </div>
  );
}
