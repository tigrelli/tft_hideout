import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Gnb } from "../gnb";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

// WBS FE-02 테스트 요구사항: 3개 브레이크포인트(모바일/태블릿/데스크톱)에서
// GNB 렌더링 분기(가로바/드로어) 테스트. 태블릿·데스크톱은 디자인가이드 6.1상
// 동일 구조를 공유하므로 Tailwind 기본 브레이크포인트 md: 하나로 검증한다.

describe("Gnb — 브레이크포인트 분기", () => {
  it("가로 메뉴는 md 미만에서 숨김, md 이상에서 노출된다(hidden md:flex)", () => {
    render(<Gnb />);
    const nav = screen.getByRole("navigation", { name: "주요 메뉴" });
    expect(nav.className).toContain("hidden");
    expect(nav.className).toContain("md:flex");
  });

  it("모바일 메뉴(햄버거) 버튼은 md 이상에서 숨김 처리된다(md:hidden)", () => {
    render(<Gnb />);
    const menuButton = screen.getByRole("button", { name: "메뉴 열기" });
    expect(menuButton.className).toContain("md:hidden");
  });

  it("4개 진입점(티어리스트/아이템 빌드/증강체 정보/전적 분석)을 노출한다", () => {
    render(<Gnb />);
    const nav = screen.getByRole("navigation", { name: "주요 메뉴" });
    for (const label of [
      "티어리스트",
      "아이템 빌드",
      "증강체 정보",
      "전적 분석",
    ]) {
      expect(nav).toHaveTextContent(label);
    }
  });

  it("현재 페이지 메뉴는 Bold+text-primary, 나머지는 text-secondary로 구분한다", () => {
    render(<Gnb />);
    const nav = screen.getByRole("navigation", { name: "주요 메뉴" });
    const active = screen.getAllByRole("link", { name: "티어리스트" })[0];
    expect(active.className).toContain("font-bold");
    expect(active.className).toContain("text-text-primary");

    const inactive = Array.from(nav.querySelectorAll("a")).find(
      (a) => a.textContent === "아이템 빌드",
    );
    expect(inactive?.className).toContain("text-text-secondary");
  });
});

describe("Gnb — 모바일 드로어", () => {
  it("초기 상태에는 드로어가 렌더링되지 않는다", () => {
    render(<Gnb />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("햄버거 버튼을 누르면 전체화면 드로어가 열리고 4개 진입점을 보여준다", async () => {
    const user = userEvent.setup();
    render(<Gnb />);

    await user.click(screen.getByRole("button", { name: "메뉴 열기" }));

    const drawer = screen.getByRole("dialog", { name: "모바일 메뉴" });
    expect(drawer).toBeInTheDocument();
    expect(drawer).toHaveAttribute("aria-modal", "true");
    for (const label of [
      "티어리스트",
      "아이템 빌드",
      "증강체 정보",
      "전적 분석",
    ]) {
      expect(drawer).toHaveTextContent(label);
    }
  });

  it("닫기 버튼을 누르면 드로어가 닫힌다", async () => {
    const user = userEvent.setup();
    render(<Gnb />);

    await user.click(screen.getByRole("button", { name: "메뉴 열기" }));
    await user.click(screen.getByRole("button", { name: "메뉴 닫기" }));

    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("드로어에서 메뉴 항목을 클릭하면 드로어가 닫힌다", async () => {
    const user = userEvent.setup();
    render(<Gnb />);

    await user.click(screen.getByRole("button", { name: "메뉴 열기" }));
    const drawer = screen.getByRole("dialog", { name: "모바일 메뉴" });
    await user.click(
      Array.from(drawer.querySelectorAll("a")).find(
        (a) => a.textContent === "아이템 빌드",
      )!,
    );

    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
