import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import (
    AccountLinkEvent,
    ChatLog,
    LinkClickEvent,
    PatchDetectionRun,
    RagasEvalResult,
)

# CHAT-07(웹사이트 링크 자동 삽입)이 아직 구현되지 않아 "링크 포함 답변" 플래그가 없다.
# PM 결정(2026-08-03): answer 텍스트에 카탈로그 내부 경로가 포함된 행을 "노출"로 간주한다
# (glossary.md IA 화면 7개 URL 기준). CHAT-07 구현 후 실제 삽입 포맷과 대조해 재검토 필요.
_LINK_EXPOSURE_PATTERN = re.compile(r"/comps/\d+|/items/builds|/augments")


@dataclass
class DataFreshness:
    avg_minutes: float | None
    sample_count: int


@dataclass
class AnswerGroundingRate:
    rate_percent: float | None
    sample_count: int


@dataclass
class ConversionRate:
    rate_percent: float | None
    exposed_count: int
    click_count: int


@dataclass
class PostGameAnalysisUsageRate:
    day30_percent: float | None
    day90_percent: float | None
    eligible_day30_count: int
    eligible_day90_count: int


@dataclass
class ResponseLatency:
    p50_warm_ms: float | None
    p95_overall_ms: float | None
    cold_start_ratio_percent: float | None
    sample_count: int


def _percentile(sorted_values: list[float], pct: float) -> float:
    """선형 보간 방식(nearest-rank 아님) 백분위수. sorted_values는 오름차순 정렬 상태여야 한다."""
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * (pct / 100)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = rank - lower
    return (
        sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction
    )


def get_data_freshness(db: Session) -> DataFreshness:
    """9-1 자동 패치 감지 트리거의 성공 실행 평균 소요시간(분). PRD 3-3 표 목표: 평균 1시간 이내."""
    rows = list(
        db.execute(
            select(PatchDetectionRun.duration_ms).where(
                PatchDetectionRun.status == "success"
            )
        ).scalars()
    )
    if not rows:
        return DataFreshness(avg_minutes=None, sample_count=0)
    avg_ms = sum(rows) / len(rows)
    return DataFreshness(avg_minutes=avg_ms / 60_000, sample_count=len(rows))


def get_answer_grounding_rate(db: Session) -> AnswerGroundingRate:
    """RAGAS faithfulness 스코어 평균(%). PRD 3-3 표 목표: 85% 이상."""
    rows = list(db.execute(select(RagasEvalResult.faithfulness_score)).scalars())
    if not rows:
        return AnswerGroundingRate(rate_percent=None, sample_count=0)
    return AnswerGroundingRate(
        rate_percent=(sum(rows) / len(rows)) * 100, sample_count=len(rows)
    )


def get_conversion_rate(db: Session) -> ConversionRate:
    """챗봇→웹사이트 전환율(%) = (링크 노출 답변에 연결된 클릭 수) / (링크 노출 답변 수).
    PRD 3-3 표 목표: 15~20%."""
    exposed_ids = list(
        db.execute(
            select(ChatLog.id).where(
                ChatLog.answer.op("~")(_LINK_EXPOSURE_PATTERN.pattern)
            )
        ).scalars()
    )
    if not exposed_ids:
        return ConversionRate(rate_percent=None, exposed_count=0, click_count=0)

    click_count = db.execute(
        select(func.count())
        .select_from(LinkClickEvent)
        .where(LinkClickEvent.chat_log_id.in_(exposed_ids))
    ).scalar_one()

    return ConversionRate(
        rate_percent=(click_count / len(exposed_ids)) * 100,
        exposed_count=len(exposed_ids),
        click_count=click_count,
    )


def get_post_game_analysis_usage_rate(
    db: Session, now: datetime
) -> PostGameAnalysisUsageRate:
    """계정 연동 완료(riot_id_hash 최초 link) 코호트 대비 30일/90일 내 analysis_request 비율(%).
    PRD 3-3 표 목표: 30일 30%, 90일 45~50%. 관찰 기간이 아직 안 지난 사용자는 모수에서 제외한다."""
    link_rows = db.execute(
        select(AccountLinkEvent.riot_id_hash, AccountLinkEvent.created_at).where(
            AccountLinkEvent.event_type == "link"
        )
    ).all()
    first_link: dict[str, datetime] = {}
    for riot_id_hash, created_at in link_rows:
        if riot_id_hash not in first_link or created_at < first_link[riot_id_hash]:
            first_link[riot_id_hash] = created_at

    analysis_rows = db.execute(
        select(AccountLinkEvent.riot_id_hash, AccountLinkEvent.created_at).where(
            AccountLinkEvent.event_type == "analysis_request"
        )
    ).all()
    analysis_dates: dict[str, list[datetime]] = defaultdict(list)
    for riot_id_hash, created_at in analysis_rows:
        analysis_dates[riot_id_hash].append(created_at)

    def _rate_for_window(days: int) -> tuple[float | None, int]:
        window = timedelta(days=days)
        eligible = {h: d for h, d in first_link.items() if now - d >= window}
        if not eligible:
            return None, 0
        converted = sum(
            1
            for riot_id_hash, linked_at in eligible.items()
            if any(
                linked_at <= ts <= linked_at + window
                for ts in analysis_dates.get(riot_id_hash, [])
            )
        )
        return (converted / len(eligible)) * 100, len(eligible)

    day30_percent, eligible_day30_count = _rate_for_window(30)
    day90_percent, eligible_day90_count = _rate_for_window(90)
    return PostGameAnalysisUsageRate(
        day30_percent=day30_percent,
        day90_percent=day90_percent,
        eligible_day30_count=eligible_day30_count,
        eligible_day90_count=eligible_day90_count,
    )


def get_response_latency(db: Session) -> ResponseLatency:
    """콜드스타트 제외 p50, 전체(콜드스타트 포함) p95. PRD 3-3 표 목표: 웜 p50 3초 이하, p95 60초 이하."""
    rows = db.execute(select(ChatLog.latency_ms, ChatLog.cold_start)).all()
    if not rows:
        return ResponseLatency(
            p50_warm_ms=None,
            p95_overall_ms=None,
            cold_start_ratio_percent=None,
            sample_count=0,
        )

    all_latencies = sorted(latency_ms for latency_ms, _ in rows)
    warm_latencies = sorted(
        latency_ms for latency_ms, cold_start in rows if not cold_start
    )
    cold_count = sum(1 for _, cold_start in rows if cold_start)

    return ResponseLatency(
        p50_warm_ms=_percentile(warm_latencies, 50) if warm_latencies else None,
        p95_overall_ms=_percentile(all_latencies, 95),
        cold_start_ratio_percent=(cold_count / len(rows)) * 100,
        sample_count=len(rows),
    )
