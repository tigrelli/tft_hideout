import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChampionList } from "@/components/comp-detail/champion-list";
import type { ChampionInComp } from "@/types/catalog";

// ChampionList -> ItemIconRow가 마운트 시 재료 조회(GET /catalog/items)를 내부적으로
// 호출하므로(use-item-recipes.ts), 실제 네트워크 요청이 나가지 않게 fetch를 막는다.
// 이 테스트들은 재료 팝오버를 검증하지 않으므로, 응답이 영영 오지 않는 것으로
// 목을 걸어 테스트 종료 이후 setState가 일어나 act() 경고가 나는 것을 막는다.

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

// WBS FE-04 테스트 요구사항: 캐리/서브 챔피언 보더 스타일 분기
// (design-tokens.md: 캐리는 accent-carry #E59933 2px 보더로 확정).
describe("ChampionList — 캐리/서브 보더 스타일 분기", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {})),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("캐리 챔피언은 border-2 border-accent-carry 클래스를 갖는다", () => {
    render(
      <ChampionList
        champions={[
          makeChampion({ champion_id: 1, name_kr: "요네", is_carry: true }),
        ]}
      />,
    );
    const card = screen.getByText("요네").closest("a") as HTMLElement;
    expect(card.className).toContain("border-2");
    expect(card.className).toContain("border-accent-carry");
  });

  it("서브 챔피언은 기본 보더(border border-border-default)를 갖는다", () => {
    render(
      <ChampionList
        champions={[
          makeChampion({ champion_id: 2, name_kr: "아리", is_carry: false }),
        ]}
      />,
    );
    const card = screen.getByText("아리").closest("a") as HTMLElement;
    expect(card.className).toContain("border-border-default");
    expect(card.className).not.toContain("border-2");
  });

  it("챔피언을 클릭하면 해당 챔피언의 아이템 빌드 화면으로 이동한다", () => {
    render(
      <ChampionList
        champions={[
          makeChampion({ champion_id: 42, name_kr: "요네", is_carry: true }),
        ]}
      />,
    );
    expect(screen.getByRole("link", { name: /요네/ })).toHaveAttribute(
      "href",
      "/items/builds?champion_id=42",
    );
  });

  it("추천 아이템을 이미지로 보여준다(아이콘 없으면 이니셜 폴백)", () => {
    render(
      <ChampionList
        champions={[
          makeChampion({
            name_kr: "요네",
            recommended_item_names: ["무한의 대검", "최후의 속삭임"],
            recommended_item_icons: ["https://x.invalid/ie.png", null],
          }),
        ]}
      />,
    );
    expect(
      screen.getByLabelText("추천 아이템 무한의 대검, 최후의 속삭임"),
    ).toBeInTheDocument();
    expect(screen.getByAltText("무한의 대검")).toBeInTheDocument();
    expect(screen.getByTitle("최후의 속삭임")).toBeInTheDocument();
  });
});
