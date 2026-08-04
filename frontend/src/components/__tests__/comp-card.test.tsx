import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CompCard } from "@/components/tierlist/comp-card";
import type { CompSummary } from "@/types/catalog";

const comp: CompSummary = {
  id: 42,
  name: "아이오니아 마법사",
  tier_rank: "S",
  avg_place: 3.2,
  play_rate: 0.18,
  win_rate: 0.19,
  playstyle_text: "리롤 성향 강함",
  carry_champion_ids: [10, 20, 30],
};

describe("CompCard", () => {
  it("조합명·티어·통계·플레이스타일을 렌더링한다", () => {
    render(<CompCard comp={comp} />);
    expect(screen.getByText("아이오니아 마법사")).toBeInTheDocument();
    expect(screen.getByText("S")).toBeInTheDocument();
    expect(screen.getByText(/평균등수 3\.2/)).toBeInTheDocument();
    expect(screen.getByText(/픽률 18%/)).toBeInTheDocument();
    expect(screen.getByText(/승률 19%/)).toBeInTheDocument();
    expect(screen.getByText("리롤 성향 강함")).toBeInTheDocument();
  });

  it("win_rate가 null이면 '정보 없음'으로 표시한다", () => {
    render(<CompCard comp={{ ...comp, win_rate: null }} />);
    expect(screen.getByText(/승률 정보 없음/)).toBeInTheDocument();
  });

  it("carry_champion_ids 개수만큼 표시 점을 렌더링한다", () => {
    render(<CompCard comp={comp} />);
    expect(screen.getByLabelText("캐리 챔피언 3명")).toBeInTheDocument();
  });

  it("조합 상세 페이지(/comps?id={id})로 링크된다", () => {
    render(<CompCard comp={comp} />);
    expect(screen.getByRole("link")).toHaveAttribute("href", "/comps?id=42");
  });
});
