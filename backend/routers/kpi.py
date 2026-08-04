from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.session import get_db
from services.kpi_auth import issue_token, verify_password, verify_token
from services.kpi_summary import (
    get_answer_grounding_rate,
    get_conversion_rate,
    get_data_freshness,
    get_post_game_analysis_usage_rate,
    get_response_latency,
)

router = APIRouter(prefix="/api/v1/kpi", tags=["kpi"])


class KpiAuthRequest(BaseModel):
    password: str


class KpiAuthResponse(BaseModel):
    token: str


class DataFreshnessResponse(BaseModel):
    avg_minutes: float | None
    sample_count: int


class AnswerGroundingRateResponse(BaseModel):
    rate_percent: float | None
    sample_count: int


class ConversionRateResponse(BaseModel):
    rate_percent: float | None
    exposed_count: int
    click_count: int


class PostGameAnalysisUsageRateResponse(BaseModel):
    day30_percent: float | None
    day90_percent: float | None
    eligible_day30_count: int
    eligible_day90_count: int


class ResponseLatencyResponse(BaseModel):
    p50_warm_ms: float | None
    p95_overall_ms: float | None
    cold_start_ratio_percent: float | None
    sample_count: int


class KpiSummaryResponse(BaseModel):
    data_freshness: DataFreshnessResponse
    answer_grounding_rate: AnswerGroundingRateResponse
    conversion_rate: ConversionRateResponse
    post_game_analysis_usage_rate: PostGameAnalysisUsageRateResponse
    response_latency: ResponseLatencyResponse


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=401, detail={"error": {"code": code, "message": message}}
    )


def require_kpi_token(authorization: Annotated[str | None, Header()] = None) -> None:
    if authorization is None or not authorization.startswith("Bearer "):
        raise _unauthorized("unauthorized", "KPI 인증이 필요합니다")
    token = authorization.removeprefix("Bearer ")
    if not verify_token(token):
        raise _unauthorized("unauthorized", "유효하지 않거나 만료된 토큰입니다")


@router.get("/")
def kpi_root() -> dict[str, str]:
    return {"router": "kpi"}


@router.post("/auth", response_model=KpiAuthResponse)
def post_kpi_auth(body: KpiAuthRequest) -> KpiAuthResponse:
    if not verify_password(body.password):
        raise _unauthorized("invalid_password", "비밀번호가 올바르지 않습니다")
    return KpiAuthResponse(token=issue_token())


@router.get(
    "/summary",
    response_model=KpiSummaryResponse,
    dependencies=[Depends(require_kpi_token)],
)
def get_kpi_summary(db: Annotated[Session, Depends(get_db)]) -> KpiSummaryResponse:
    freshness = get_data_freshness(db)
    grounding = get_answer_grounding_rate(db)
    conversion = get_conversion_rate(db)
    usage = get_post_game_analysis_usage_rate(db, datetime.now(UTC))
    latency = get_response_latency(db)

    return KpiSummaryResponse(
        data_freshness=DataFreshnessResponse(
            avg_minutes=freshness.avg_minutes, sample_count=freshness.sample_count
        ),
        answer_grounding_rate=AnswerGroundingRateResponse(
            rate_percent=grounding.rate_percent, sample_count=grounding.sample_count
        ),
        conversion_rate=ConversionRateResponse(
            rate_percent=conversion.rate_percent,
            exposed_count=conversion.exposed_count,
            click_count=conversion.click_count,
        ),
        post_game_analysis_usage_rate=PostGameAnalysisUsageRateResponse(
            day30_percent=usage.day30_percent,
            day90_percent=usage.day90_percent,
            eligible_day30_count=usage.eligible_day30_count,
            eligible_day90_count=usage.eligible_day90_count,
        ),
        response_latency=ResponseLatencyResponse(
            p50_warm_ms=latency.p50_warm_ms,
            p95_overall_ms=latency.p95_overall_ms,
            cold_start_ratio_percent=latency.cold_start_ratio_percent,
            sample_count=latency.sample_count,
        ),
    )
