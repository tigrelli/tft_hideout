import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CompGrid } from "@/components/tierlist/comp-grid";
import type { CompSummary } from "@/types/catalog";

function makeComp(overrides: Partial<CompSummary> = {}): CompSummary {
  return {
    id: 1,
    name: "아이오니아 마법사",
    tier_rank: "S",
    avg_place: 3.2,
    play_rate: 0.18,
    win_rate: 0.19,
    top4_rate: 0.72,
    game_count: 1000,
    playstyle_text: "리롤 성향 강함",
    carry_champions: [
      { champion_id: 10, name_kr: "요네", square_icon_url: null },
      { champion_id: 20, name_kr: "아리", square_icon_url: null },
    ],
    traits: [],
    ...overrides,
  };
}

// WBS FE-03 테스트 요구사항: 카드 그리드 컬럼 수 브레이크포인트별 렌더링
// (design-tokens.md: 데스크톱 3~4열 · 태블릿 2열 · 모바일 1열 — GNB 테스트와
// 동일하게 jsdom엔 실제 미디어쿼리가 없어 Tailwind 클래스명으로 검증).
describe("CompGrid — 브레이크포인트별 컬럼 수", () => {
  it("모바일 기본 1열(grid-cols-1), 태블릿 2열(md:grid-cols-2), 데스크톱 3열(lg:grid-cols-3) 클래스를 갖는다", () => {
    const { container } = render(<CompGrid comps={[makeComp()]} />);
    const grid = container.firstChild as HTMLElement;
    expect(grid.className).toContain("grid-cols-1");
    expect(grid.className).toContain("md:grid-cols-2");
    expect(grid.className).toContain("lg:grid-cols-3");
  });

  it("comps 배열 길이만큼 카드를 렌더링한다", () => {
    const comps = [
      makeComp({ id: 1, name: "조합 A" }),
      makeComp({ id: 2, name: "조합 B" }),
      makeComp({ id: 3, name: "조합 C" }),
    ];
    render(<CompGrid comps={comps} />);
    expect(screen.getByText("조합 A")).toBeInTheDocument();
    expect(screen.getByText("조합 B")).toBeInTheDocument();
    expect(screen.getByText("조합 C")).toBeInTheDocument();
  });

  it("빈 배열이면 안내 문구를 보여준다", () => {
    render(<CompGrid comps={[]} />);
    expect(
      screen.getByText("조건에 맞는 조합이 없습니다."),
    ).toBeInTheDocument();
  });
});
