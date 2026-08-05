import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import Home from "@/app/page";
import type { TierlistResponse } from "@/types/catalog";

const mockTierlist: TierlistResponse = {
  patch_version: "17.8",
  comps: [
    {
      id: 1,
      name: "아이오니아 마법사",
      tier_rank: "S",
      avg_place: 3.2,
      play_rate: 0.18,
      win_rate: 0.19,
      playstyle_text: "리롤 성향 강함",
      carry_champions: [
        { champion_id: 10, name_kr: "요네", square_icon_url: null },
      ],
    },
  ],
};

// WBS FE-03 테스트 요구사항: mock API 응답 데이터 바인딩 테스트. 랭크 필터는
// 2026-08-05 PM 결정으로 제거됨(op.gg가 랭크 구간별 데이터를 제공하지 않음,
// docs/spike/opgg-schema.md).
describe("Home(티어리스트) — mock API 데이터 바인딩", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("로딩 중에는 안내 문구, 성공하면 조합 카드와 패치 배지를 보여준다", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockTierlist,
    } as Response);

    render(<Home />);
    expect(screen.getByText("불러오는 중...")).toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getByText("아이오니아 마법사")).toBeInTheDocument(),
    );
    expect(screen.getByText("패치 17.8")).toBeInTheDocument();
  });

  it("API 호출이 실패하면 에러 문구를 보여준다", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({}),
    } as Response);

    render(<Home />);

    await waitFor(() =>
      expect(
        screen.getByText("티어리스트를 불러오지 못했습니다."),
      ).toBeInTheDocument(),
    );
  });
});
