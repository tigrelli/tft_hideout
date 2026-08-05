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
  carry_champions: [
    {
      champion_id: 10,
      name_kr: "요네",
      square_icon_url: "https://raw.communitydragon.org/fake-yone.png",
    },
    { champion_id: 20, name_kr: "아리", square_icon_url: null },
    { champion_id: 30, name_kr: "징크스", square_icon_url: null },
  ],
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

  it("carry_champions 개수만큼 표시(이미지 또는 점)를 렌더링한다", () => {
    render(<CompCard comp={comp} />);
    expect(screen.getByLabelText("캐리 챔피언 3명")).toBeInTheDocument();
  });

  it("square_icon_url이 있으면 실제 챔피언 이미지를 렌더링한다", () => {
    render(<CompCard comp={comp} />);
    const image = screen.getByAltText("요네");
    expect(image.tagName).toBe("IMG");
    // next/image는 next.config.ts images.unoptimized(정적 export 설정)를
    // 개발 빌드에서만 적용하므로, Vitest(jsdom)에서는 /_next/image?url=...
    // 프록시 형태로 렌더링될 수 있다 — 원본 URL이 포함돼 있는지만 확인한다.
    expect(decodeURIComponent(image.getAttribute("src") ?? "")).toContain(
      "https://raw.communitydragon.org/fake-yone.png",
    );
  });

  it("square_icon_url이 없으면 점 placeholder를 렌더링한다(이미지 아님)", () => {
    render(<CompCard comp={comp} />);
    expect(screen.queryByAltText("아리")).not.toBeInTheDocument();
    expect(screen.queryByAltText("징크스")).not.toBeInTheDocument();
  });

  it("조합 상세 페이지(/comps?id={id})로 링크된다", () => {
    render(<CompCard comp={comp} />);
    expect(screen.getByRole("link")).toHaveAttribute("href", "/comps?id=42");
  });
});
