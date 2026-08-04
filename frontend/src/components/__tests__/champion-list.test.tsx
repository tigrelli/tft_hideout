import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChampionList } from "@/components/comp-detail/champion-list";
import type { ChampionInComp } from "@/types/catalog";

function makeChampion(overrides: Partial<ChampionInComp> = {}): ChampionInComp {
  return {
    champion_id: 1,
    name_kr: "요네",
    name_en: "Yone",
    is_carry: false,
    recommended_items: [],
    recommended_item_names: [],
    ...overrides,
  };
}

// WBS FE-04 테스트 요구사항: 캐리/서브 챔피언 보더 스타일 분기
// (design-tokens.md: 캐리는 accent-carry #E59933 2px 보더로 확정).
describe("ChampionList — 캐리/서브 보더 스타일 분기", () => {
  it("캐리 챔피언은 border-2 border-accent-carry 클래스를 갖는다", () => {
    render(
      <ChampionList
        champions={[
          makeChampion({ champion_id: 1, name_kr: "요네", is_carry: true }),
        ]}
      />,
    );
    const card = screen.getByText("요네").closest("div") as HTMLElement;
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
    const card = screen.getByText("아리").closest("div") as HTMLElement;
    expect(card.className).toContain("border-border-default");
    expect(card.className).not.toContain("border-2");
  });

  it("추천 아이템 이름을 함께 보여준다", () => {
    render(
      <ChampionList
        champions={[
          makeChampion({
            name_kr: "요네",
            recommended_item_names: ["무한의 대검", "최후의 속삭임"],
          }),
        ]}
      />,
    );
    expect(screen.getByText("무한의 대검, 최후의 속삭임")).toBeInTheDocument();
  });
});
