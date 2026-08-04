import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { HeaderShell } from "../header-shell";

// WBS FE-01 테스트 요구사항: Tailwind 브레이크포인트 클래스 적용 여부 확인

describe("HeaderShell", () => {
  it("데스크톱 내비게이션은 md 이상에서만 보이도록 hidden/md:flex 클래스를 적용한다", () => {
    render(<HeaderShell />);
    const nav = screen.getByText("티어리스트").closest("nav");
    expect(nav).not.toBeNull();
    expect(nav?.className).toContain("hidden");
    expect(nav?.className).toContain("md:flex");
  });

  it("모바일 메뉴 버튼은 md 이상에서 숨김(md:hidden) 처리된다", () => {
    render(<HeaderShell />);
    const menuButton = screen.getByRole("button", { name: "메뉴 열기" });
    expect(menuButton.className).toContain("md:hidden");
  });

  it("좌우 패딩이 모바일 px-4, md 이상 px-10으로 브레이크포인트에 따라 전환된다", () => {
    render(<HeaderShell />);
    const nav = screen.getByText("티어리스트").closest("nav");
    const row = nav?.parentElement;
    expect(row?.className).toContain("px-4");
    expect(row?.className).toContain("md:px-10");
  });
});
