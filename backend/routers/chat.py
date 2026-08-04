from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.session import get_db
from services.chat_session import (
    RECENT_TURNS_LIMIT,
    get_session_history,
    validate_session_id,
)
from services.chat_stream import build_sse_stream, generate_answer_stream
from services.embedding_client import embed_query
from services.groq_client import stream_groq_chat
from services.hybrid_search import hybrid_search
from services.intent_classification import classify_intent_for_query
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


class ChatHistoryTurn(BaseModel):
    user_query: str
    answer: str
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    session_id: str
    turns: list[ChatHistoryTurn]


@router.get("/")
def chat_root() -> dict[str, str]:
    return {"router": "chat"}


@router.get("/session/{session_id}/history", response_model=ChatHistoryResponse)
def get_chat_history(
    session_id: str, db: Annotated[Session, Depends(get_db)]
) -> ChatHistoryResponse:
    """드릴다운용 대화 이력 조회(API-10). 가장 최근 RECENT_TURNS_LIMIT턴만 반환한다."""
    validated = validate_session_id(session_id)
    logs = get_session_history(db, validated, limit=RECENT_TURNS_LIMIT)
    return ChatHistoryResponse(
        session_id=validated,
        turns=[
            ChatHistoryTurn(
                user_query=log.user_query, answer=log.answer, created_at=log.created_at
            )
            for log in logs
        ],
    )


@router.post("/message")
def post_chat_message(
    body: ChatMessageRequest, db: Annotated[Session, Depends(get_db)]
) -> StreamingResponse:
    """SSE 스트리밍 응답(API-09 배관 + CHAT-01~05 실제 배선)."""
    validate_session_id(body.session_id)
    token_stream = generate_answer_stream(
        db,
        body.session_id,
        body.message,
        embed_fn=embed_query,
        classify_fn=classify_intent_for_query,
        search_fn=hybrid_search,
        stream_fn=stream_groq_chat,
    )
    return StreamingResponse(
        build_sse_stream(token_stream), media_type="text/event-stream"
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
