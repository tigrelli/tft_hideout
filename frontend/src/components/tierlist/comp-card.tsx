import Image from "next/image";
import Link from "next/link";
import type { CompSummary } from "@/types/catalog";
import { TIER_CLASS, TierBadge } from "@/components/tierlist/tier-badge";

// 화면설계서 2.1: Card `comp-card`, 클릭 시 comp-detail로 이동. URL은 IA v1.2
// 원문(`/comps/{comp_id}`) 대신 쿼리스트링(`/comps?id=`)을 쓴다 — 정적 export는
// 빌드 시점에 존재하는 comp_id만 정적 페이지로 만들 수 있어, 패치마다 전부 새
// 행으로 생기는 comp_id 특성상 경로 방식이면 재배포 전까지 새 조합 링크가 전부
// 깨짐(FE-04 작업결과 참고, PM 결정 2026-08-04).
// FE-13: API-02가 carry_champions(이름·square_icon_url)를 내려주므로 실제
// Community Dragon 챔피언 아이콘을 표시한다. 이미지가 없는 챔피언(square_icon_url
// null)은 기존 점(●) placeholder로 폴백(design-tokens.md 그레이박스 placeholder
// 규칙 유지).
export function CompCard({ comp }: { comp: CompSummary }) {
  return (
    <Link
      href={`/comps?id=${comp.id}`}
      className="flex overflow-hidden rounded-card border border-border-default bg-surface-card hover:border-primary"
    >
      <span
        aria-hidden="true"
        className={`w-1.5 shrink-0 ${TIER_CLASS[comp.tier_rank] ?? "bg-tier-c"}`}
      />

      <div className="min-w-0 flex-1 p-4">
        <div className="flex items-center justify-between">
          <span className="text-h2 text-text-primary">{comp.name}</span>
          <TierBadge tier={comp.tier_rank} />
        </div>

        <div
          className="mt-2 flex gap-2"
          aria-label={`캐리 챔피언 ${comp.carry_champions.length}명`}
        >
          {comp.carry_champions.map((champion) =>
            champion.square_icon_url ? (
              <Image
                key={champion.champion_id}
                src={champion.square_icon_url}
                alt={champion.name_kr}
                width={64}
                height={64}
                className="rounded-card border-2 border-accent-carry object-cover"
              />
            ) : (
              <span
                key={champion.champion_id}
                className="h-16 w-16 rounded-card border-2 border-accent-carry bg-border-default"
              />
            ),
          )}
        </div>

        <p className="mt-2 text-caption text-text-secondary">
          <span className="font-bold">
            평균등수 {comp.avg_place.toFixed(1)}
          </span>{" "}
          ·{" "}
          <span className="font-bold">
            픽률 {(comp.play_rate * 100).toFixed(0)}%
          </span>{" "}
          ·{" "}
          <span className="font-bold">
            승률{" "}
            {comp.win_rate !== null
              ? `${(comp.win_rate * 100).toFixed(0)}%`
              : "정보 없음"}
          </span>
        </p>

        <p className="mt-1 text-body text-text-secondary">
          {comp.playstyle_text}
        </p>
      </div>
    </Link>
  );
}
