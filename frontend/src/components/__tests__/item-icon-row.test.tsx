import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { ItemIconRow } from "@/components/comp-detail/item-icon-row";
import type { ItemsResponse } from "@/types/catalog";

const mockItems: ItemsResponse = {
  patch_version: "17.8",
  items: [
    {
      riot_item_id: "TFT_Item_InfinityEdge",
      name_kr: "무한의 대검",
      square_icon_url: "https://x.invalid/ie.png",
      components: [
        {
          riot_item_id: "TFT_Item_BFSword",
          name_kr: "장검",
          square_icon_url: "https://x.invalid/bf.png",
        },
        {
          riot_item_id: "TFT_Item_SparringGloves",
          name_kr: "장갑",
          square_icon_url: null,
        },
      ],
    },
    {
      riot_item_id: "TFT_Item_BFSword",
      name_kr: "장검",
      square_icon_url: "https://x.invalid/bf.png",
      components: [],
    },
    {
      // 같은 재료를 2개 조합하는 아이템(예: 곡궁+곡궁) — 실사용 중 재료 목록의
      // React key가 riot_item_id만 쓰면 중복돼 경고가 발생하는 버그가
      // 있었다(2026-08-06 발견, 인덱스도 함께 key에 포함해 수정).
      riot_item_id: "TFT_Item_GuinsoosRageblade",
      name_kr: "긴수아의 격노검",
      square_icon_url: "https://x.invalid/gr.png",
      components: [
        {
          riot_item_id: "TFT_Item_RecurveBow",
          name_kr: "곡궁",
          square_icon_url: "https://x.invalid/bow.png",
        },
        {
          riot_item_id: "TFT_Item_RecurveBow",
          name_kr: "곡궁",
          square_icon_url: "https://x.invalid/bow.png",
        },
      ],
    },
  ],
};

// 재료(GET /catalog/items) 조회는 마운트 시 백그라운드로 시작돼 언제 끝날지
// 테스트에서 보장할 수 없다 — userEvent의 hover/click처럼 실제 타이머 지연이
// 섞인 인터랙션과 경합하면 간헐적으로 실패할 수 있어(관찰됨), 항상 먼저
// "로딩 완료" 신호(hasRecipe=true일 때만 붙는 cursor-pointer 클래스)를
// waitFor로 기다린 다음에만 fireEvent로 결정론적으로 상호작용을 검증한다.
async function renderAndWaitForRecipe(props: {
  names: string[];
  icons: (string | null)[];
  itemIds: string[];
}): Promise<HTMLElement> {
  render(<ItemIconRow {...props} />);
  const trigger = screen
    .getByAltText(props.names[0])
    .closest('[role="button"]') as HTMLElement;
  await waitFor(() => {
    expect(trigger).toHaveClass("cursor-pointer");
  });
  return trigger;
}

describe("ItemIconRow", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockItems,
      } as Response),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("아이템이 없으면 아무것도 렌더링하지 않는다", async () => {
    const { container } = render(<ItemIconRow names={[]} icons={[]} />);
    expect(container).toBeEmptyDOMElement();

    // 렌더링은 일찍 null을 반환하지만 useItemRecipes 훅 자체는 여전히
    // 호출돼 백그라운드 fetch가 걸린다 — act() 경고 방지용 flush.
    await act(async () => {
      await Promise.resolve();
    });
  });

  it("아이콘이 있으면 이미지로, 없으면 이니셜 폴백으로 렌더링한다", async () => {
    render(
      <ItemIconRow
        names={["무한의 대검", "최후의 속삭임"]}
        icons={["https://x.invalid/ie.png", null]}
      />,
    );
    expect(screen.getByAltText("무한의 대검")).toBeInTheDocument();
    expect(screen.getByTitle("최후의 속삭임")).toHaveTextContent("최");

    // itemIds를 안 줘서 재료 조회 결과와 무관하지만, 백그라운드 fetch가 테스트
    // 종료 후에 끝나 act() 경고가 나지 않도록 완료를 기다려준다.
    await act(async () => {
      await Promise.resolve();
    });
  });

  it("완성 아이템에 마우스를 올리면 조합 재료를 이미지+이름으로 보여준다", async () => {
    const trigger = await renderAndWaitForRecipe({
      names: ["무한의 대검"],
      icons: ["https://x.invalid/ie.png"],
      itemIds: ["TFT_Item_InfinityEdge"],
    });

    fireEvent.mouseEnter(trigger);

    expect(screen.getByText("장검 + 장갑")).toBeInTheDocument();
    expect(screen.getByAltText("장검")).toBeInTheDocument();
  });

  it("마우스를 떼면 재료 팝오버가 사라진다", async () => {
    const trigger = await renderAndWaitForRecipe({
      names: ["무한의 대검"],
      icons: ["https://x.invalid/ie.png"],
      itemIds: ["TFT_Item_InfinityEdge"],
    });

    fireEvent.mouseEnter(trigger);
    expect(screen.getByText("장검 + 장갑")).toBeInTheDocument();

    fireEvent.mouseLeave(trigger);
    expect(screen.queryByText("장검 + 장갑")).not.toBeInTheDocument();
  });

  it("재료가 없는(기본) 아이템은 클릭해도 팝오버가 뜨지 않는다", async () => {
    render(
      <ItemIconRow
        names={["장검"]}
        icons={["https://x.invalid/bf.png"]}
        itemIds={["TFT_Item_BFSword"]}
      />,
    );
    const trigger = screen
      .getByAltText("장검")
      .closest('[role="button"]') as HTMLElement;

    // 재료 조회가 끝나도(hasRecipe=false 그대로) cursor-default를 유지하는지
    // 확인해 로딩 완료 이후에도 팝오버가 안 뜨는 것까지 함께 검증한다.
    await act(async () => {
      await Promise.resolve();
    });
    expect(trigger).toHaveClass("cursor-default");

    fireEvent.click(trigger);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("클릭(탭)으로도 재료 팝오버를 토글할 수 있다", async () => {
    const trigger = await renderAndWaitForRecipe({
      names: ["무한의 대검"],
      icons: ["https://x.invalid/ie.png"],
      itemIds: ["TFT_Item_InfinityEdge"],
    });

    fireEvent.click(trigger);
    expect(screen.getByRole("tooltip")).toBeInTheDocument();

    fireEvent.click(trigger);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("같은 재료를 2개 조합하는 아이템도 React key 경고 없이 둘 다 렌더링한다", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    const trigger = await renderAndWaitForRecipe({
      names: ["긴수아의 격노검"],
      icons: ["https://x.invalid/gr.png"],
      itemIds: ["TFT_Item_GuinsoosRageblade"],
    });

    fireEvent.mouseEnter(trigger);

    expect(screen.getAllByAltText("곡궁")).toHaveLength(2);
    expect(screen.getByText("곡궁 + 곡궁")).toBeInTheDocument();
    expect(consoleError).not.toHaveBeenCalledWith(
      expect.stringContaining("same key"),
    );
    consoleError.mockRestore();
  });
});
