import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ItemBuildsView } from "@/components/item-builds/item-builds-view";
import type { ItemBuildsResponse } from "@/types/catalog";

const mockSearchParams = new URLSearchParams();
const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => "/items/builds",
  useSearchParams: () => mockSearchParams,
}));

const mockItemBuilds: ItemBuildsResponse = {
  patch_version: "17.8",
  champion_id: null,
  builds: [
    {
      id: 1,
      champion_id: 10,
      champion_name_kr: "요네",
      champion_name_en: "Yone",
      champion_square_icon_url: "https://x.invalid/yone.png",
      item_combination: ["ie", "gs", "lw"],
      item_combination_names: ["무한의 대검", "거인의 학살자", "최후의 속삭임"],
      item_combination_icons: [],
      play_rate: 0.3,
      avg_place: 3.8,
      win_rate: 0.18,
    },
    {
      id: 2,
      champion_id: 10,
      champion_name_kr: "요네",
      champion_name_en: "Yone",
      champion_square_icon_url: "https://x.invalid/yone.png",
      item_combination: ["bt", "gs", "ie"],
      item_combination_names: ["피바라기", "거인의 학살자", "무한의 대검"],
      item_combination_icons: [],
      play_rate: 0.1,
      avg_place: 4.0,
      win_rate: 0.15,
    },
    {
      id: 3,
      champion_id: 20,
      champion_name_kr: "아리",
      champion_name_en: "Ahri",
      champion_square_icon_url: null,
      item_combination: ["ludens"],
      item_combination_names: ["루덴의 메아리"],
      item_combination_icons: [],
      play_rate: 0.2,
      avg_place: 4.2,
      win_rate: 0.11,
    },
  ],
};

// WBS FE-05 테스트 요구사항: 챔피언 필터 선택 시 URL 쿼리 동기화, 모바일 바텀시트
// 오픈/클로즈 테스트.
describe("ItemBuildsView — 챔피언 필터·아이템 빌드", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    mockSearchParams.delete("champion_id");
    mockReplace.mockClear();
  });

  it("로드 후 챔피언 미선택 상태에서는 안내 문구만 보여준다", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockItemBuilds,
    } as Response);

    render(<ItemBuildsView />);

    await waitFor(() =>
      expect(screen.getByLabelText("챔피언 선택")).toBeInTheDocument(),
    );
    expect(
      screen.getByText("챔피언을 선택하면 아이템 조합 리스트가 표시됩니다."),
    ).toBeInTheDocument();
  });

  it("챔피언 필터 선택 시 URL 쿼리(champion_id, patch)가 동기화되고 리스트가 갱신된다", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockItemBuilds,
    } as Response);

    render(<ItemBuildsView />);

    const input = await screen.findByLabelText("챔피언 선택");
    await user.type(input, "요네");
    await user.click(screen.getByRole("button", { name: "요네" }));

    expect(mockReplace).toHaveBeenCalledWith(
      "/items/builds?champion_id=10&patch=17.8",
    );
    expect(
      screen.getByText("무한의 대검 + 거인의 학살자 + 최후의 속삭임"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("피바라기 + 거인의 학살자 + 무한의 대검"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/루덴의 메아리/)).not.toBeInTheDocument();
  });

  it("URL의 champion_id로 초기 선택되고, 리스트 행을 탭하면 모바일 바텀시트가 열리고 닫힌다", async () => {
    const user = userEvent.setup();
    mockSearchParams.set("champion_id", "10");
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockItemBuilds,
    } as Response);

    render(<ItemBuildsView />);

    const row = await screen.findByText(
      "무한의 대검 + 거인의 학살자 + 최후의 속삭임",
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(row);
    expect(
      screen.getByRole("dialog", { name: "빌드 우선순위 상세" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "닫기" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
