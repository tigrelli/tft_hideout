import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { HexBoard } from "@/components/comp-detail/hex-board";
import type { ChampionInComp } from "@/types/catalog";

function makeChampion(overrides: Partial<ChampionInComp> = {}): ChampionInComp {
  return {
    champion_id: 1,
    name_kr: "요네",
    name_en: "Yone",
    is_carry: false,
    square_icon_url: null,
    recommended_items: [],
    recommended_item_names: [],
    recommended_item_icons: [],
    cell_x: null,
    cell_y: null,
    star_level: null,
    ...overrides,
  };
}

// HexTile -> ItemIconRow가 마운트 시 재료 조회(GET /catalog/items)를 내부적으로
// 호출하므로(use-item-recipes.ts), 실제 네트워크 요청이 나가지 않게 fetch를 막는다.
// 이 테스트들은 재료 팝오버를 검증하지 않으므로, 응답이 영영 오지 않는 것으로
// 목을 걸어 테스트 종료 이후 setState가 일어나 act() 경고가 나는 것을 막는다.
describe("HexBoard — cell_x/cell_y 없으면 is_carry 기반 휴리스틱 배치로 폴백", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {})),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("캐리·서브 챔피언 이름을 모두 렌더링한다", () => {
    render(
      <HexBoard
        champions={[
          makeChampion({ champion_id: 1, name_kr: "요네", is_carry: true }),
          makeChampion({ champion_id: 2, name_kr: "아리", is_carry: false }),
        ]}
      />,
    );
    // square_icon_url이 없으면 이름 앞 두 글자 폴백도 함께 렌더링되는데
    // "요네"/"아리"는 이미 두 글자라 폴백과 이름 라벨 텍스트가 같다.
    expect(screen.getAllByText("요네").length).toBeGreaterThan(0);
    expect(screen.getAllByText("아리").length).toBeGreaterThan(0);
  });

  it("실제 추천 배치가 아님을 굵은 글씨로 안내한다", () => {
    render(<HexBoard champions={[makeChampion()]} />);
    const notice = screen.getByText(
      "실제 사용할 수 있는 추천 배치가 아닌 휴리스틱으로 시각화되었습니다.",
    );
    expect(notice).toBeInTheDocument();
    expect(notice.className).toContain("font-bold");
  });

  it("square_icon_url이 없으면 이름 앞 두 글자를 폴백으로 보여준다", () => {
    render(
      <HexBoard
        champions={[makeChampion({ name_kr: "징크스", square_icon_url: null })]}
      />,
    );
    expect(screen.getByText("징크")).toBeInTheDocument();
  });

  it("일부 챔피언만 좌표가 있으면(구 데이터 혼재) 전체를 휴리스틱 배치로 폴백한다", () => {
    render(
      <HexBoard
        champions={[
          makeChampion({
            champion_id: 1,
            name_kr: "요네",
            cell_x: 4,
            cell_y: 1,
          }),
          makeChampion({
            champion_id: 2,
            name_kr: "아리",
            cell_x: null,
            cell_y: null,
          }),
        ]}
      />,
    );
    expect(
      screen.getByText(
        "실제 사용할 수 있는 추천 배치가 아닌 휴리스틱으로 시각화되었습니다.",
      ),
    ).toBeInTheDocument();
  });

  it("챔피언(헥스 타일)을 클릭하면 해당 챔피언의 아이템 빌드 화면으로 이동한다", () => {
    render(
      <HexBoard
        champions={[makeChampion({ champion_id: 42, name_kr: "요네" })]}
      />,
    );
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "/items/builds?champion_id=42",
    );
  });
});

describe("HexBoard — 모든 챔피언에 cell_x/cell_y가 있으면 실좌표 그리드로 배치", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {})),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("휴리스틱 안내 문구 대신 실좌표 안내 문구를 보여준다", () => {
    render(
      <HexBoard
        champions={[
          makeChampion({
            champion_id: 1,
            name_kr: "요네",
            cell_x: 4,
            cell_y: 1,
          }),
          makeChampion({
            champion_id: 2,
            name_kr: "아리",
            cell_x: 1,
            cell_y: 3,
          }),
        ]}
      />,
    );
    expect(
      screen.getByText(
        "op.gg 실제 랭커 배치 좌표를 그대로 반영한 헥스 배치도입니다.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(
        "실제 사용할 수 있는 추천 배치가 아닌 휴리스틱으로 시각화되었습니다.",
      ),
    ).not.toBeInTheDocument();
  });

  it("cell_x는 그대로, cell_y는 전열/후열이 화면과 맞도록 반전해 grid-row에 배치한다", () => {
    render(
      <HexBoard
        champions={[
          makeChampion({
            champion_id: 1,
            name_kr: "요네",
            cell_x: 4,
            cell_y: 1,
          }),
        ]}
      />,
    );
    const link = screen.getByRole("link");
    expect(link.style.gridColumnStart).toBe("4");
    // GRID_ROWS(4) + 1 - cell_y(1) = 4행(화면 맨 아래, 전열)
    expect(link.style.gridRowStart).toBe("4");
  });

  it("화면상 짝수 번째 행(뒤집힌 grid-row가 짝수)은 벌집 모양을 위해 오른쪽으로 반 칸 밀린다", () => {
    render(
      <HexBoard
        champions={[
          makeChampion({
            champion_id: 1,
            name_kr: "요네",
            cell_x: 1,
            cell_y: 1,
          }),
          makeChampion({
            champion_id: 2,
            name_kr: "아리",
            cell_x: 1,
            cell_y: 2,
          }),
        ]}
      />,
    );
    const links = screen.getAllByRole("link");
    // cell_y:1 -> grid-row 4행(짝수, 오프셋 O), cell_y:2 -> grid-row 3행(홀수, 오프셋 X)
    const evenDisplayRow = links.find((el) => el.style.gridRowStart === "4");
    const oddDisplayRow = links.find((el) => el.style.gridRowStart === "3");
    expect(oddDisplayRow?.style.transform).toBe("");
    expect(evenDisplayRow?.style.transform).toContain("translateX");
  });
});

describe("HexBoard — 성급(★) 표시(FE-15)", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {})),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("3성은 별 3개를 레드(tier-op) 색상으로 표시한다", () => {
    render(<HexBoard champions={[makeChampion({ star_level: 3 })]} />);
    const stars = screen.getByRole("img", { name: "3성" });
    expect(stars).toHaveTextContent("★★★");
    expect(stars.className).toContain("text-tier-op");
  });

  it("2성은 별 2개를 골드(tier-s) 색상으로 표시한다", () => {
    render(<HexBoard champions={[makeChampion({ star_level: 2 })]} />);
    const stars = screen.getByRole("img", { name: "2성" });
    expect(stars).toHaveTextContent("★★");
    expect(stars.className).toContain("text-tier-s");
  });

  it("star_level이 없으면 별 표시를 생략한다", () => {
    render(<HexBoard champions={[makeChampion({ star_level: null })]} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("실좌표 모드에서도 성급 별 표시가 함께 렌더링된다", () => {
    render(
      <HexBoard
        champions={[
          makeChampion({
            champion_id: 1,
            cell_x: 4,
            cell_y: 1,
            star_level: 3,
          }),
        ]}
      />,
    );
    expect(screen.getByRole("img", { name: "3성" })).toBeInTheDocument();
  });
});
