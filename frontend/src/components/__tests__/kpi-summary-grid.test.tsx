import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { KpiSummaryGrid } from "@/components/kpi/kpi-summary-grid";
import type { KpiSummaryResponse } from "@/types/kpi";

const summary: KpiSummaryResponse = {
  data_freshness: { avg_minutes: 42.3, sample_count: 5 },
  answer_grounding_rate: { rate_percent: 87.6, sample_count: 20 },
  conversion_rate: { rate_percent: 18.2, exposed_count: 50, click_count: 9 },
  post_game_analysis_usage_rate: {
    day30_percent: 31.5,
    day90_percent: null,
    eligible_day30_count: 10,
    eligible_day90_count: 0,
  },
  response_latency: {
    p50_warm_ms: 2100,
    p95_overall_ms: 45000,
    cold_start_ratio_percent: 12.5,
    sample_count: 30,
  },
};

// WBS FE-12 테스트 요구사항: 지표 카드 렌더링 테스트.
describe("KpiSummaryGrid", () => {
  it("5개 지표 카드를 모두 렌더링한다", () => {
    render(<KpiSummaryGrid summary={summary} />);

    expect(screen.getByText("데이터 최신성")).toBeInTheDocument();
    expect(screen.getByText("답변 근거율")).toBeInTheDocument();
    expect(screen.getByText("전환율")).toBeInTheDocument();
    expect(screen.getByText("사후분석 이용률")).toBeInTheDocument();
    expect(screen.getByText("응답 지연")).toBeInTheDocument();
  });

  it("값을 포맷팅해서 보여준다", () => {
    render(<KpiSummaryGrid summary={summary} />);

    expect(screen.getByText("평균 42.3분")).toBeInTheDocument();
    expect(screen.getByText("87.6%")).toBeInTheDocument();
    expect(screen.getByText("노출 50건 · 클릭 9건")).toBeInTheDocument();
    expect(screen.getByText("웜 p50 2,100ms")).toBeInTheDocument();
  });

  it("null 값은 데이터 없음으로 표시한다", () => {
    render(<KpiSummaryGrid summary={summary} />);

    expect(screen.getByText("90일 데이터 없음")).toBeInTheDocument();
  });
});
