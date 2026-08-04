from datetime import UTC, datetime

from sqlalchemy.orm import Session

from db.models import AccountLinkEvent, LinkClickEvent


def record_link_click(
    db: Session,
    *,
    session_id: str,
    chat_log_id: int | None,
    target_page: str,
) -> LinkClickEvent:
    """챗봇 답변 내 링크 클릭 이벤트 적재 (전환율 계측, schema.md link_click_events)."""
    event = LinkClickEvent(
        session_id=session_id,
        chat_log_id=chat_log_id,
        target_page=target_page,
        clicked_at=datetime.now(UTC),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def record_account_link_event(
    db: Session,
    *,
    riot_id_hash: str,
    region: str,
    event_type: str,
    match_id: str | None,
    latency_ms: int,
) -> AccountLinkEvent:
    """계정연동·분석요청 이벤트 적재 (schema.md account_link_events).
    API-11/12(POST /analysis/link, /analysis/recent)이 이 훅을 호출해 기록한다."""
    event = AccountLinkEvent(
        riot_id_hash=riot_id_hash,
        region=region,
        event_type=event_type,
        match_id=match_id,
        latency_ms=latency_ms,
        created_at=datetime.now(UTC),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
