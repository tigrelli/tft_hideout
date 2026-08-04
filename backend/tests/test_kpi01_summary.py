from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import (
    AccountLinkEvent,
    ChatLog,
    LinkClickEvent,
    Patch,
    PatchDetectionRun,
    RagasEvalResult,
)
from db.session import get_db
from main import app
from services.kpi_summary import (
    get_answer_grounding_rate,
    get_conversion_rate,
    get_data_freshness,
    get_post_game_analysis_usage_rate,
    get_response_latency,
)

NOW = datetime(2026, 8, 3, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _kpi_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPI_DASHBOARD_PASSWORD", "test-only-password")


@pytest.fixture
def seeded_db(migrated_engine: Engine) -> Engine:
    with Session(migrated_engine) as session:
        session.execute(
            insert(Patch).values(
                version="14.5",
                set_number=14,
                released_at=NOW,
                is_current=True,
                detected_at=NOW,
            )
        )

        # 데이터 최신성: success 2건(30분, 90분 → 평균 60분), failed 1건(제외)
        session.execute(
            insert(PatchDetectionRun).values(
                triggered_at=NOW,
                patch_version_before="14.4",
                patch_version_after="14.5",
                duration_ms=30 * 60_000,
                status="success",
            )
        )
        session.execute(
            insert(PatchDetectionRun).values(
                triggered_at=NOW,
                patch_version_before="14.4",
                patch_version_after="14.5",
                duration_ms=90 * 60_000,
                status="success",
            )
        )
        session.execute(
            insert(PatchDetectionRun).values(
                triggered_at=NOW,
                patch_version_before="14.4",
                patch_version_after="14.5",
                duration_ms=999 * 60_000,
                status="failed",
            )
        )

        # 근거율: faithfulness 0.8, 0.9 → 평균 85%
        session.execute(
            insert(RagasEvalResult).values(
                eval_date=NOW,
                sample_query="8덱 조합 뭐가 좋아?",
                faithfulness_score=0.8,
                answer_relevancy_score=0.9,
                patch_version="14.5",
            )
        )
        session.execute(
            insert(RagasEvalResult).values(
                eval_date=NOW,
                sample_query="아이템 추천해줘",
                faithfulness_score=0.9,
                answer_relevancy_score=0.85,
                patch_version="14.5",
            )
        )

        # 전환율: 링크 노출 답변 2건(exposed), 비노출 답변 1건. 클릭은 노출 답변 중 1건에만 발생.
        session.execute(
            insert(ChatLog).values(
                id=1,
                session_id="11111111-1111-1111-1111-111111111111",
                patch_version="14.5",
                user_query="8덱 조합 추천",
                intent="comp_recommendation",
                retrieved_doc_ids=[1],
                answer="이 조합을 추천합니다. 자세히는 /comps/42 에서 확인하세요.",
                latency_ms=1000,
                cold_start=False,
                created_at=NOW,
            )
        )
        session.execute(
            insert(ChatLog).values(
                id=2,
                session_id="11111111-1111-1111-1111-111111111111",
                patch_version="14.5",
                user_query="증강체 뭐가 좋아?",
                intent="augment_recommendation",
                retrieved_doc_ids=[2],
                answer="증강체 목록은 /augments 에서 확인하세요.",
                latency_ms=2000,
                cold_start=False,
                created_at=NOW,
            )
        )
        session.execute(
            insert(ChatLog).values(
                id=3,
                session_id="11111111-1111-1111-1111-111111111111",
                patch_version="14.5",
                user_query="안녕",
                intent="general_strategy",
                retrieved_doc_ids=[],
                answer="무엇을 도와드릴까요?",
                latency_ms=3000,
                cold_start=True,
                created_at=NOW,
            )
        )
        session.execute(
            insert(LinkClickEvent).values(
                session_id="11111111-1111-1111-1111-111111111111",
                chat_log_id=1,
                target_page="/comps/42",
                clicked_at=NOW,
            )
        )

        # 이용률: user-a는 30일/90일 모두 관찰기간 경과 + 30일 내 분석요청(전환).
        # user-b는 90일 관찰기간만 경과 + 미전환.
        session.execute(
            insert(AccountLinkEvent).values(
                riot_id_hash="hash-a",
                region="kr",
                event_type="link",
                match_id=None,
                latency_ms=200,
                created_at=NOW - timedelta(days=40),
            )
        )
        session.execute(
            insert(AccountLinkEvent).values(
                riot_id_hash="hash-a",
                region="kr",
                event_type="analysis_request",
                match_id="KR_1",
                latency_ms=300,
                created_at=NOW - timedelta(days=35),
            )
        )
        session.execute(
            insert(AccountLinkEvent).values(
                riot_id_hash="hash-b",
                region="kr",
                event_type="link",
                match_id=None,
                latency_ms=200,
                created_at=NOW - timedelta(days=100),
            )
        )
        session.commit()
    return migrated_engine


def test_get_data_freshness_averages_only_successful_runs(seeded_db: Engine) -> None:
    with Session(seeded_db) as db:
        result = get_data_freshness(db)
    assert result.sample_count == 2
    assert result.avg_minutes == pytest.approx(60.0)


def test_get_answer_grounding_rate_averages_faithfulness_as_percent(
    seeded_db: Engine,
) -> None:
    with Session(seeded_db) as db:
        result = get_answer_grounding_rate(db)
    assert result.sample_count == 2
    assert result.rate_percent == pytest.approx(85.0)


def test_get_conversion_rate_counts_only_link_exposed_answers(
    seeded_db: Engine,
) -> None:
    with Session(seeded_db) as db:
        result = get_conversion_rate(db)
    assert result.exposed_count == 2
    assert result.click_count == 1
    assert result.rate_percent == pytest.approx(50.0)


def test_get_post_game_analysis_usage_rate_cohort_windows(seeded_db: Engine) -> None:
    with Session(seeded_db) as db:
        result = get_post_game_analysis_usage_rate(db, NOW)

    assert result.eligible_day30_count == 2
    assert result.day30_percent == pytest.approx(50.0)
    assert result.eligible_day90_count == 1
    assert result.day90_percent == pytest.approx(0.0)


def test_get_response_latency_percentiles_and_cold_start_ratio(
    seeded_db: Engine,
) -> None:
    with Session(seeded_db) as db:
        result = get_response_latency(db)

    assert result.sample_count == 3
    assert result.cold_start_ratio_percent == pytest.approx(100 / 3)
    assert result.p50_warm_ms == pytest.approx(1500.0)
    assert result.p95_overall_ms == pytest.approx(2900.0)


def test_get_data_freshness_returns_none_when_no_success_runs(
    migrated_engine: Engine,
) -> None:
    with Session(migrated_engine) as db:
        result = get_data_freshness(db)
    assert result.avg_minutes is None
    assert result.sample_count == 0


@pytest.fixture
def client(seeded_db: Engine) -> TestClient:
    test_session_local = sessionmaker(bind=seeded_db)

    def override_get_db():
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_kpi_auth_endpoint_issues_token_for_correct_password(
    client: TestClient,
) -> None:
    response = client.post("/api/v1/kpi/auth", json={"password": "test-only-password"})
    assert response.status_code == 200
    assert isinstance(response.json()["token"], str)


def test_kpi_auth_endpoint_rejects_wrong_password(client: TestClient) -> None:
    response = client.post("/api/v1/kpi/auth", json={"password": "wrong"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_password"


def test_kpi_summary_endpoint_requires_token(client: TestClient) -> None:
    response = client.get("/api/v1/kpi/summary")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_kpi_summary_endpoint_rejects_invalid_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/kpi/summary", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_kpi_summary_endpoint_returns_5_metrics_with_valid_token(
    client: TestClient,
) -> None:
    auth_response = client.post(
        "/api/v1/kpi/auth", json={"password": "test-only-password"}
    )
    token = auth_response.json()["token"]

    response = client.get(
        "/api/v1/kpi/summary", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "data_freshness",
        "answer_grounding_rate",
        "conversion_rate",
        "post_game_analysis_usage_rate",
        "response_latency",
    }
    assert body["answer_grounding_rate"]["rate_percent"] == pytest.approx(85.0)
