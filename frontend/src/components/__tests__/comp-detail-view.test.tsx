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
      recommended_items: ["TFT_Item_InfinityEdge"],
      recommended_item_names: ["무한의 대검"],
    },
    {
      champion_id: 20,
      name_kr: "아리",
      name_en: "Ahri",
      is_carry: false,
      recommended_items: [],
      recommended_item_names: [],
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
    expect(screen.getByText("요네")).toBeInTheDocument();
    expect(screen.getByText("완전무장")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /아이템 빌드 더보기/ }),
    ).toHaveAttribute("href", "/items/builds?champion_id=10");
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
