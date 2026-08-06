import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { CompDetailView } from "@/components/comp-detail/comp-detail-view";
import type { CompDetailResponse } from "@/types/catalog";

const mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
}));

const mockCompDetail: CompDetailResponse = {
  id: 1,
  patch_version: "17.8",
  name: "아이오니아 마법사",
  tier_rank: "S",
  avg_place: 3.2,
  play_rate: 0.18,
  win_rate: 0.19,
  playstyle_text: "리롤 성향 강함",
  champions: [
    {
      champion_id: 10,
      name_kr: "요네",
      name_en: "Yone",
      is_carry: true,
      square_icon_url: null,
      recommended_items: ["TFT_Item_InfinityEdge"],
      recommended_item_names: ["무한의 대검"],
      recommended_item_icons: [null],
      cell_x: null,
      cell_y: null,
      star_level: null,
    },
    {
      champion_id: 20,
      name_kr: "아리",
      name_en: "Ahri",
      is_carry: false,
      square_icon_url: null,
      recommended_items: [],
      recommended_item_names: [],
      recommended_item_icons: [],
      cell_x: null,
      cell_y: null,
      star_level: null,
    },
  ],
  augments: [
    { augment_id: 1, name_kr: "완전무장", name_en: "Full Armory", priority: 1 },
  ],
};

// WBS FE-04 테스트 요구사항: mock API 데이터 바인딩(쿼리스트링 id 읽기 포함).
describe("CompDetailView — mock API 데이터 바인딩", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    mockSearchParams.delete("id");
  });

  it("id가 없으면 안내 문구만 보여주고 fetch하지 않는다", () => {
    render(<CompDetailView />);
    expect(
      screen.getByText(
        "잘못된 접근입니다. 티어리스트에서 조합을 선택해주세요.",
      ),
    ).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("id가 있으면 조합 상세를 불러와 렌더링한다", async () => {
    mockSearchParams.set("id", "1");
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockCompDetail,
    } as Response);

    render(<CompDetailView />);

    await waitFor(() =>
      expect(screen.getByText("아이오니아 마법사")).toBeInTheDocument(),
    );
    expect(screen.getByText("패치 17.8")).toBeInTheDocument();
    // 모바일(ChampionList)·태블릿/데스크톱(HexBoard) 두 뷰가 반응형 클래스로
    // 동시에 렌더링되므로(jsdom은 미디어쿼리를 적용하지 않음) 챔피언명이
    // 두 곳에 나타난다.
    expect(screen.getAllByText("요네").length).toBeGreaterThan(0);
    expect(screen.getByText("완전무장")).toBeInTheDocument();
  });

  it("조회 실패 시 에러 문구를 보여준다", async () => {
    mockSearchParams.set("id", "999");
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({}),
    } as Response);

    render(<CompDetailView />);

    await waitFor(() =>
      expect(screen.getByText("조합을 찾을 수 없습니다.")).toBeInTheDocument(),
    );
  });
});
