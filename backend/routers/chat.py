from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.session import get_db
from services.chat_session import validate_session_id
from services.kpi_events import record_link_click

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class LinkClickRequest(BaseModel):
    session_id: str
    chat_log_id: int | None = None
    target_page: str


class LinkClickResponse(BaseModel):
    id: int


@router.get("/")
def chat_root() -> dict[str, str]:
    return {"router": "chat"}


@router.post("/events/link-click", response_model=LinkClickResponse, status_code=201)
def post_link_click_event(
    body: LinkClickRequest, db: Annotated[Session, Depends(get_db)]
) -> LinkClickResponse:
    session_id = validate_session_id(body.session_id)
    event = record_link_click(
        db,
        session_id=session_id,
        chat_log_id=body.chat_log_id,
        target_page=body.target_page,
    )
    return LinkClickResponse(id=event.id)
