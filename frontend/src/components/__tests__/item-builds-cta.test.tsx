import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ItemBuildsCta } from "@/components/comp-detail/item-builds-cta";

// WBS FE-04 테스트 요구사항: CTA 버튼 모바일 full-width 렌더링 테스트.
describe("ItemBuildsCta — 반응형 full-width", () => {
  it("모바일 기본 w-full, 태블릿/데스크톱 md:w-auto 클래스를 갖는다", () => {
    render(<ItemBuildsCta championId={7} />);
    const link = screen.getByRole("link", { name: /아이템 빌드 더보기/ });
    expect(link.className).toContain("w-full");
    expect(link.className).toContain("md:w-auto");
  });

  it("champion_id=7로 아이템 빌드 페이지에 링크된다", () => {
    render(<ItemBuildsCta championId={7} />);
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "/items/builds?champion_id=7",
    );
  });

  it("championId가 없으면(캐리 챔피언 없음) 렌더링하지 않는다", () => {
    const { container } = render(<ItemBuildsCta championId={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
