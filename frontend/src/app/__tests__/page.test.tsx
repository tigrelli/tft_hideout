import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    expect(
      screen.getByText(
        "불러오는 중입니다. 무료 호스팅 특성상 처음 접속 시 다소 시간이 걸릴 수 있습니다.",
      ),
    ).toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getByText("아이오니아 마법사")).toBeInTheDocument(),
    );
    expect(screen.getByText("패치 17.8")).toBeInTheDocument();
  });

  // FE-16(2026-08-16, PM 요청)에서 처음 추가, 2026-08-18 DATA-23 재정의(opScore
  // 기반 대중성·신뢰도 상대 순위)에 맞춰 문구 갱신 — "자체 계산"이 아니라 "대중적
  // 조합의 상대 등급"이라는 새 정의가 항상 노출돼야 한다.
  it("티어 배지가 op.gg top-10 안에서의 상대 등급이라는 안내 문구를 항상 보여준다", () => {
    render(<Home />);
    expect(
      screen.getByText(
        /티어 배지는 op\.gg 상위 10개 조합 중 대중적으로 꾸준히 강세를 보이는/,
      ),
    ).toBeInTheDocument();
  });

  it("안내 문구 옆 정보 아이콘을 클릭하면 상세 설명 팝업이 뜬다", async () => {
    const user = userEvent.setup();
    render(<Home />);

    expect(
      screen.queryByText(/공식 웹사이트가 보여주는 20개 이상과는/),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "자세히 보기" }));

    expect(
      screen.getByText(/공식 웹사이트가 보여주는 20개 이상과는/),
    ).toBeInTheDocument();
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
