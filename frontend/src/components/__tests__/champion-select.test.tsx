import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChampionSelect } from "@/components/item-builds/champion-select";

const champions = [
  {
    championId: 10,
    nameKr: "요네",
    squareIconUrl: "https://x.invalid/yone.png",
  },
  { championId: 20, nameKr: "아리", squareIconUrl: null },
];

describe("ChampionSelect — 텍스트 입력 자동완성", () => {
  it("입력값으로 챔피언 후보를 필터링한다", async () => {
    const user = userEvent.setup();
    render(
      <ChampionSelect champions={champions} value={null} onChange={vi.fn()} />,
    );

    const input = screen.getByLabelText("챔피언 선택");
    await user.type(input, "요");

    expect(screen.getByRole("button", { name: "요네" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "아리" }),
    ).not.toBeInTheDocument();
  });

  it("후보를 클릭하면 onChange가 호출되고 입력값이 채워진다", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ChampionSelect champions={champions} value={null} onChange={onChange} />,
    );

    const input = screen.getByLabelText("챔피언 선택");
    await user.type(input, "아리");
    await user.click(screen.getByRole("button", { name: "아리" }));

    expect(onChange).toHaveBeenCalledWith(20);
    expect(input).toHaveValue("아리");
  });

  it("선택된 챔피언의 아이콘 이미지를 입력창 안에 보여준다", () => {
    render(
      <ChampionSelect champions={champions} value={10} onChange={vi.fn()} />,
    );
    const image = screen.getByAltText("");
    // next/image는 next.config.ts images.unoptimized(정적 export 설정)를 개발
    // 빌드에서만 적용하므로 Vitest(jsdom)에서는 /_next/image?url=... 프록시
    // 형태로 렌더링될 수 있다 — 원본 URL 포함 여부만 확인한다.
    expect(decodeURIComponent(image.getAttribute("src") ?? "")).toContain(
      "yone.png",
    );
  });

  it("아이콘이 없으면 이니셜 폴백을 보여준다", () => {
    render(
      <ChampionSelect champions={champions} value={20} onChange={vi.fn()} />,
    );
    expect(screen.getByText("아")).toBeInTheDocument();
  });

  it("선택 후 입력값을 지우면 입력창 안의 이전 챔피언 아이콘이 사라진다", () => {
    render(
      <ChampionSelect champions={champions} value={10} onChange={vi.fn()} />,
    );
    const input = screen.getByLabelText("챔피언 선택");
    const label = input.closest("label") as HTMLElement;
    expect(within(label).getByAltText("")).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "" } });

    // 지우면 후보 목록(listbox)이 열리며 같은 챔피언 아이콘이 목록 쪽에 다시
    // 나타날 수 있으므로, 입력창(label) 범위로 한정해 확인한다.
    expect(within(label).queryByAltText("")).not.toBeInTheDocument();
  });
});
