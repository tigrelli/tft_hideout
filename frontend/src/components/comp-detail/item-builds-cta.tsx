import Link from "next/link";

// 화면설계서 2.2: Button `cta-item-builds` {"label":"이 조합의 아이템 빌드 더보기"}
// -> item-builds 화면 이동(champion_id 전달). 반응형: 모바일 full-width, 태블릿/
// 데스크톱은 기존 레이아웃 유지(WBS FE-04 테스트 요구사항: CTA 버튼 모바일 full-width).
export function ItemBuildsCta({ championId }: { championId: number | null }) {
  if (championId === null) {
    return null;
  }

  return (
    <Link
      href={`/items/builds?champion_id=${championId}`}
      className="mt-4 block w-full rounded-control bg-primary px-5 py-3 text-center text-body font-bold text-text-on-brand md:inline-block md:w-auto"
    >
      이 조합의 아이템 빌드 더보기 →
    </Link>
  );
}
