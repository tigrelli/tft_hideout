import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TierFilterBar } from "@/components/augments/tier-filter-bar";

// WBS FE-06 반응형: 태블릿/데스크톱은 드롭다운 유지, 모바일은 버튼 -> 바텀시트
// (design-tokens.md "필터 UI: Dropdown / Bottom Sheet", FE-03 FilterBar와 동일 패턴).
describe("TierFilterBar — 반응형 티어 필터", () => {
  it("데스크톱/태블릿용 드롭다운은 hidden md:block, 모바일 버튼은 md:hidden 클래스를 갖는다", () => {
    render(<TierFilterBar tier="all" onTierChange={vi.fn()} />);
    const desktopWrapper = screen
      .getByText("티어 선택")
      .closest("div") as HTMLElement;
    expect(desktopWrapper.className).toContain("hidden");
    expect(desktopWrapper.className).toContain("md:block");

    const mobileButton = screen.getByRole("button", { name: /티어/ });
    expect(mobileButton.className).toContain("md:hidden");
  });

  it("데스크톱 드롭다운에서 티어를 바꾸면 onTierChange가 호출된다", async () => {
    const user = userEvent.setup();
    const onTierChange = vi.fn();
    render(<TierFilterBar tier="all" onTierChange={onTierChange} />);
    const select = screen.getByLabelText("티어 선택");
    await user.selectOptions(select, "prism");
    expect(onTierChange).toHaveBeenCalledWith("prism");
  });

  it("모바일 티어 버튼을 누르면 바텀시트가 열리고, 선택 시 닫힌다", async () => {
    const user = userEvent.setup();
    const onTierChange = vi.fn();
    render(<TierFilterBar tier="all" onTierChange={onTierChange} />);
    await user.click(screen.getByRole("button", { name: /티어/ }));
    expect(
      screen.getByRole("dialog", { name: "티어 선택" }),
    ).toBeInTheDocument();

    const [, sheetSelect] = screen.getAllByLabelText("티어 선택");
    await user.selectOptions(sheetSelect, "gold");

    expect(onTierChange).toHaveBeenCalledWith("gold");
    expect(
      screen.queryByRole("dialog", { name: "티어 선택" }),
    ).not.toBeInTheDocument();
  });
});
