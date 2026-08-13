import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import KpiDashboardPage from "@/app/kpi/page";
import type { KpiSummaryResponse } from "@/types/kpi";

const mockSummary: KpiSummaryResponse = {
  data_freshness: { avg_minutes: 42.3, sample_count: 5 },
  answer_grounding_rate: { rate_percent: 87.6, sample_count: 20 },
  conversion_rate: { rate_percent: 18.2, exposed_count: 50, click_count: 9 },
  post_game_analysis_usage_rate: {
    day30_percent: 31.5,
    day90_percent: 40.1,
    eligible_day30_count: 10,
    eligible_day90_count: 4,
  },
  response_latency: {
    p50_warm_ms: 2100,
    p95_overall_ms: 45000,
    cold_start_ratio_percent: 12.5,
    sample_count: 30,
  },
};

// WBS FE-12 완료 기준: 비밀번호 게이트 통과 후 5개 지표 정상 렌더링, 오답 시
// 게이트 재노출.
describe("KpiDashboardPage — 비밀번호 게이트 → 지표 렌더링", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("토큰이 없으면 비밀번호 게이트를 보여준다", async () => {
    render(<KpiDashboardPage />);
    expect(
      await screen.findByRole("button", { name: "확인" }),
    ).toBeInTheDocument();
  });

  it("오답 제출 시 게이트를 유지하고 오류 문구를 보여준다", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({}),
    } as Response);

    render(<KpiDashboardPage />);
    await user.type(await screen.findByLabelText("비밀번호"), "wrong");
    await user.click(screen.getByRole("button", { name: "확인" }));

    await waitFor(() =>
      expect(
        screen.getByText("비밀번호가 올바르지 않습니다."),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "확인" })).toBeInTheDocument();
  });

  it("정답 제출 시 인증 토큰을 받아 지표 요약을 불러와 렌더링한다", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ token: "issued-token" }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSummary,
      } as Response);

    render(<KpiDashboardPage />);
    await user.type(await screen.findByLabelText("비밀번호"), "correct-pw");
    await user.click(screen.getByRole("button", { name: "확인" }));

    await waitFor(() =>
      expect(screen.getByText("데이터 최신성")).toBeInTheDocument(),
    );
    expect(screen.getByText("응답 지연")).toBeInTheDocument();

    const [, summaryCall] = vi.mocked(fetch).mock.calls;
    const summaryInit = summaryCall[1] as RequestInit;
    expect(
      (summaryInit.headers as Record<string, string>).Authorization,
    ).toBe("Bearer issued-token");
  });

  it("인증 직후 지표 조회가 401이면 게이트를 다시 보여준다", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ token: "stale-token" }),
      } as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({}),
      } as Response);

    render(<KpiDashboardPage />);
    await user.type(await screen.findByLabelText("비밀번호"), "correct-pw");
    await user.click(screen.getByRole("button", { name: "확인" }));

    await waitFor(() =>
      expect(screen.getByLabelText("비밀번호")).toBeInTheDocument(),
    );
  });
});
