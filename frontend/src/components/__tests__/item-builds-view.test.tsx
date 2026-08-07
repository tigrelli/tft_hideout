import { useSyncExternalStore } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ItemBuildsView } from "@/components/item-builds/item-builds-view";
import type { ItemBuildsResponse } from "@/types/catalog";

// ItemBuildsView가 selectedChampionId를 state로 따로 안 들고 매 렌더마다
// searchParams에서 직접 계산하도록 바뀌어서(2026-08-07, URL 단일 진실 공급원),
// router.replace 호출이 실제로 useSearchParams()의 반환값을 바꾸고 컴포넌트를
// 리렌더시켜야 테스트가 실제 동작을 재현한다 — useSyncExternalStore로 최소
// 구현한 mock router.
const mockSearchParamsState: { current: URLSearchParams } = {
  current: new URLSearchParams(),
};
const mockSearchParamsListeners = new Set<() => void>();
const mockReplace = vi.fn((url: string) => {
  const query = url.includes("?") ? url.slice(url.indexOf("?") + 1) : "";
  mockSearchParamsState.current = new URLSearchParams(query);
  mockSearchParamsListeners.forEach((listener) => listener());
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => "/items/builds",
  useSearchParams: () =>
    useSyncExternalStore(
      (listener) => {
        mockSearchParamsListeners.add(listener);
        return () => mockSearchParamsListeners.delete(listener);
      },
      () => mockSearchParamsState.current,
    ),
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
    mockSearchParamsState.current = new URLSearchParams();
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
    mockSearchParamsState.current = new URLSearchParams("champion_id=10");
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

  it("이미 페이지에 머문 채(재마운트 없이) 다른 champion_id로 URL이 바뀌면 화면도 갱신된다", async () => {
    // 2026-08-07 PM 피드백: 챗봇 답변에서 첫 번째 챔피언 링크는 잘 넘어가는데
    // 두 번째 챔피언 링크부터는 URL만 바뀌고 화면이 안 바뀌던 문제 — 같은
    // 경로(/items/builds)라 컴포넌트가 재마운트되지 않는 상태에서, 여기서는
    // Next.js Link 네비게이션을 재현하기 위해 컴포넌트를 거치지 않고 mock
    // 라우터 상태를 직접 바꾼다(실제로는 Link가 라우터를 통해 이 상태를 갱신).
    mockSearchParamsState.current = new URLSearchParams("champion_id=10");
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockItemBuilds,
    } as Response);

    render(<ItemBuildsView />);

    await screen.findByText("무한의 대검 + 거인의 학살자 + 최후의 속삭임");

    await act(async () => {
      mockSearchParamsState.current = new URLSearchParams("champion_id=20");
      mockSearchParamsListeners.forEach((listener) => listener());
    });

    expect(await screen.findByText("루덴의 메아리")).toBeInTheDocument();
    expect(
      screen.queryByText("무한의 대검 + 거인의 학살자 + 최후의 속삭임"),
    ).not.toBeInTheDocument();
  });
});
