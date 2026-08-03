from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.session import get_db
from services.chat_session import validate_session_id
from services.chat_stream import build_sse_stream
from services.kpi_events import record_link_click

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class LinkClickRequest(BaseModel):
    session_id: str
    chat_log_id: int | None = None
    target_page: str


class LinkClickResponse(BaseModel):
    id: int


class ChatMessageRequest(BaseModel):
    session_id: str
    message: str


@router.get("/")
def chat_root() -> dict[str, str]:
    return {"router": "chat"}


@router.post("/message")
def post_chat_message(body: ChatMessageRequest) -> StreamingResponse:
    """스트리밍 응답 인프라(API-09). RAG 검색·의도분류·프롬프트 조립은 CHAT-01~10에서 연동한다."""
    validate_session_id(body.session_id)
    return StreamingResponse(
        build_sse_stream(body.message), media_type="text/event-stream"
    )


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
