// backend/routers/kpi.py의 Pydantic 응답 모델과 1:1 대응(KPI-01, FE-12).

export interface KpiAuthResponse {
  token: string;
}

export interface DataFreshness {
  avg_minutes: number | null;
  sample_count: number;
}

export interface AnswerGroundingRate {
  rate_percent: number | null;
  sample_count: number;
}

export interface ConversionRate {
  rate_percent: number | null;
  exposed_count: number;
  click_count: number;
}

export interface PostGameAnalysisUsageRate {
  day30_percent: number | null;
  day90_percent: number | null;
  eligible_day30_count: number;
  eligible_day90_count: number;
}

export interface ResponseLatency {
  p50_warm_ms: number | null;
  p95_overall_ms: number | null;
  cold_start_ratio_percent: number | null;
  sample_count: number;
}

export interface KpiSummaryResponse {
  data_freshness: DataFreshness;
  answer_grounding_rate: AnswerGroundingRate;
  conversion_rate: ConversionRate;
  post_game_analysis_usage_rate: PostGameAnalysisUsageRate;
  response_latency: ResponseLatency;
}
