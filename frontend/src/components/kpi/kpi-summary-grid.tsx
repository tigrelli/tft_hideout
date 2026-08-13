import type { KpiSummaryResponse } from "@/types/kpi";
import { KpiMetricCard } from "@/components/kpi/kpi-metric-card";

function formatPercent(value: number | null): string {
  return value === null ? "데이터 없음" : `${value.toFixed(1)}%`;
}

function formatMinutes(value: number | null): string {
  return value === null ? "데이터 없음" : `평균 ${value.toFixed(1)}분`;
}

function formatMs(value: number | null): string {
  return value === null
    ? "데이터 없음"
    : `${Math.round(value).toLocaleString()}ms`;
}

// PRD 3-3 KPI 목표: 최신성 평균 1시간 이내 / 근거율 85%+ / 전환율 15~20% /
// 사후분석 이용률 30일 30%·90일 45~50% / 응답지연 웜 p50 3초 이하·p95 60초 이하.
export function KpiSummaryGrid({ summary }: { summary: KpiSummaryResponse }) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      <KpiMetricCard label="데이터 최신성">
        <p>{formatMinutes(summary.data_freshness.avg_minutes)}</p>
        <p className="text-caption text-text-secondary">
          표본 {summary.data_freshness.sample_count}건
        </p>
      </KpiMetricCard>

      <KpiMetricCard label="답변 근거율">
        <p>{formatPercent(summary.answer_grounding_rate.rate_percent)}</p>
        <p className="text-caption text-text-secondary">
          표본 {summary.answer_grounding_rate.sample_count}건
        </p>
      </KpiMetricCard>

      <KpiMetricCard label="전환율">
        <p>{formatPercent(summary.conversion_rate.rate_percent)}</p>
        <p className="text-caption text-text-secondary">
          노출 {summary.conversion_rate.exposed_count}건 · 클릭{" "}
          {summary.conversion_rate.click_count}건
        </p>
      </KpiMetricCard>

      <KpiMetricCard label="사후분석 이용률">
        <p>
          30일{" "}
          {formatPercent(summary.post_game_analysis_usage_rate.day30_percent)}
        </p>
        <p>
          90일{" "}
          {formatPercent(summary.post_game_analysis_usage_rate.day90_percent)}
        </p>
      </KpiMetricCard>

      <KpiMetricCard label="응답 지연">
        <p>웜 p50 {formatMs(summary.response_latency.p50_warm_ms)}</p>
        <p>전체 p95 {formatMs(summary.response_latency.p95_overall_ms)}</p>
        <p className="text-caption text-text-secondary">
          콜드스타트 비율{" "}
          {formatPercent(summary.response_latency.cold_start_ratio_percent)}
        </p>
      </KpiMetricCard>
    </div>
  );
}
