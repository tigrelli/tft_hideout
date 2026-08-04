import Link from "next/link";
import type { CompSummary } from "@/types/catalog";
import { TierBadge } from "@/components/tierlist/tier-badge";

// 화면설계서 2.1: Card `comp-card`, 클릭 시 comp-detail로 이동. URL은 IA v1.2
// 원문(`/comps/{comp_id}`) 대신 쿼리스트링(`/comps?id=`)을 쓴다 — 정적 export는
// 빌드 시점에 존재하는 comp_id만 정적 페이지로 만들 수 있어, 패치마다 전부 새
// 행으로 생기는 comp_id 특성상 경로 방식이면 재배포 전까지 새 조합 링크가 전부
// 깨짐(FE-04 작업결과 참고, PM 결정 2026-08-04).
// champion_thumbnails는 API-02 응답에 챔피언 이름/이미지가 없어(carry_champion_ids만
// 제공) 화면설계서 v1.2 모바일 와이어프레임 스케치의 "● ● ●" 점 표기를 그대로
// placeholder로 사용한다(design-tokens.md "챔피언 아이콘은 그레이박스 placeholder").
export function CompCard({ comp }: { comp: CompSummary }) {
  return (
    <Link
      href={`/comps?id=${comp.id}`}
      className="block rounded-card border border-border-default bg-surface-card p-4 hover:border-primary"
    >
      <div className="flex items-center justify-between">
        <span className="text-h2 text-text-primary">{comp.name}</span>
        <TierBadge tier={comp.tier_rank} />
      </div>

      <div
        className="mt-2 flex gap-1"
        aria-label={`캐리 챔피언 ${comp.carry_champion_ids.length}명`}
      >
        {comp.carry_champion_ids.map((championId) => (
          <span
            key={championId}
            className="h-3 w-3 rounded-full border-2 border-accent-carry bg-border-default"
          />
        ))}
      </div>

      <p className="mt-2 text-caption text-text-secondary">
        평균등수 {comp.avg_place.toFixed(1)} · 픽률{" "}
        {(comp.play_rate * 100).toFixed(0)}% · 승률{" "}
        {comp.win_rate !== null
          ? `${(comp.win_rate * 100).toFixed(0)}%`
          : "정보 없음"}
      </p>

      <p className="mt-1 text-body text-text-secondary">
        {comp.playstyle_text}
      </p>
    </Link>
  );
}
