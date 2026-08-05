import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResponsiveFilter } from "@/components/common/responsive-filter";

const options = [
  { value: "a", label: "옵션 A" },
  { value: "b", label: "옵션 B" },
];

function renderFilter(value: string, onChange = vi.fn()) {
  return render(
    <ResponsiveFilter
      dropdownLabel="테스트 필터"
      triggerLabel="필터 ▾"
      sheetAriaLabel="필터 선택"
      sheetHeaderText="필터"
      closeAriaLabel="필터 닫기"
      value={value}
      options={options}
      onChange={onChange}
    />,
  );
}

// WBS FE-11 테스트 요구사항: 동일 필터 상태를 Dropdown(데스크톱/태블릿)과
// BottomSheet(모바일) 두 컴포넌트가 공유하는지 상태 동기화 테스트.
describe("ResponsiveFilter — Dropdown/BottomSheet 상태 동기화", () => {
  it("바텀시트를 열면 데스크톱 드롭다운과 동일한 현재 값이 표시된다", async () => {
    const user = userEvent.setup();
    renderFilter("b");

    await user.click(screen.getByRole("button", { name: /필터/ }));

    const [desktopSelect, sheetSelect] =
      screen.getAllByLabelText("테스트 필터");
    expect(desktopSelect).toHaveValue("b");
    expect(sheetSelect).toHaveValue("b");
  });

  it("value prop이 바뀌면(부모 상태 갱신) 두 인스턴스가 함께 갱신된다", async () => {
    const user = userEvent.setup();
    const { rerender } = renderFilter("a");

    await user.click(screen.getByRole("button", { name: /필터/ }));
    let [desktopSelect, sheetSelect] = screen.getAllByLabelText("테스트 필터");
    expect(desktopSelect).toHaveValue("a");
    expect(sheetSelect).toHaveValue("a");

    rerender(
      <ResponsiveFilter
        dropdownLabel="테스트 필터"
        triggerLabel="필터 ▾"
        sheetAriaLabel="필터 선택"
        sheetHeaderText="필터"
        closeAriaLabel="필터 닫기"
        value="b"
        options={options}
        onChange={vi.fn()}
      />,
    );

    [desktopSelect, sheetSelect] = screen.getAllByLabelText("테스트 필터");
    expect(desktopSelect).toHaveValue("b");
    expect(sheetSelect).toHaveValue("b");
  });

  it("데스크톱 드롭다운에서 선택하면 onChange가 호출된다", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderFilter("a", onChange);

    const [desktopSelect] = screen.getAllByLabelText("테스트 필터");
    await user.selectOptions(desktopSelect, "b");

    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("바텀시트에서 선택하면 onChange가 호출되고 시트가 닫힌다", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderFilter("a", onChange);

    await user.click(screen.getByRole("button", { name: /필터/ }));
    const [, sheetSelect] = screen.getAllByLabelText("테스트 필터");
    await user.selectOptions(sheetSelect, "b");

    expect(onChange).toHaveBeenCalledWith("b");
    expect(
      screen.queryByRole("dialog", { name: "필터 선택" }),
    ).not.toBeInTheDocument();
  });
});
