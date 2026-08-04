import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FilterBar } from "@/components/tierlist/filter-bar";

// WBS FE-03 반응형: 태블릿/데스크톱은 드롭다운 유지, 모바일은 '필터' 버튼 ->
// 바텀시트(design-tokens.md "필터 UI: Dropdown / Bottom Sheet").
describe("FilterBar — 반응형 필터 UI", () => {
  it("데스크톱/태블릿용 드롭다운은 hidden md:block, 모바일 버튼은 md:hidden 클래스를 갖는다", () => {
    render(<FilterBar patchVersion="17.8" rank="all" onRankChange={vi.fn()} />);
    const desktopDropdownWrapper = screen
      .getByText("랭크")
      .closest("div") as HTMLElement;
    expect(desktopDropdownWrapper.className).toContain("hidden");
    expect(desktopDropdownWrapper.className).toContain("md:block");

    const mobileButton = screen.getByRole("button", { name: /필터/ });
    expect(mobileButton.className).toContain("md:hidden");
  });

  it("현재 패치 버전을 배지로 보여준다", () => {
    render(<FilterBar patchVersion="17.8" rank="all" onRankChange={vi.fn()} />);
    expect(screen.getByText("패치 17.8")).toBeInTheDocument();
  });

  it("데스크톱 드롭다운에서 랭크를 바꾸면 onRankChange가 호출된다", async () => {
    const user = userEvent.setup();
    const onRankChange = vi.fn();
    render(
      <FilterBar patchVersion="17.8" rank="all" onRankChange={onRankChange} />,
    );
    const select = screen.getByLabelText("랭크");
    await user.selectOptions(select, "challenger");
    expect(onRankChange).toHaveBeenCalledWith("challenger");
  });

  it("모바일 필터 버튼을 누르면 바텀시트가 열리고, 랭크 선택 시 닫힌다", async () => {
    const user = userEvent.setup();
    const onRankChange = vi.fn();
    render(
      <FilterBar patchVersion="17.8" rank="all" onRankChange={onRankChange} />,
    );
    await user.click(screen.getByRole("button", { name: /필터/ }));
    expect(
      screen.getByRole("dialog", { name: "필터 선택" }),
    ).toBeInTheDocument();

    const [, sheetSelect] = screen.getAllByLabelText("랭크");
    await user.selectOptions(sheetSelect, "master");

    expect(onRankChange).toHaveBeenCalledWith("master");
    expect(
      screen.queryByRole("dialog", { name: "필터 선택" }),
    ).not.toBeInTheDocument();
  });
});
