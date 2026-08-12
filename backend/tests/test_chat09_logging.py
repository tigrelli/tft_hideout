"""CHAT-09 pytest(WBS 테스트 요구사항: chat_logs row에 질의/의도/근거문서id/
patch_version/답변/지연시간/콜드스타트 전체 필드 적재 확인)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.models import ChatLog, MetaDocumentEmbedding, Patch
from services.chat_logging import COLD_START_THRESHOLD_MS, record_chat_log
from services.chat_stream import generate_answer_stream
from services.intent_classification import INTENT_COMP_RECOMMENDATION


@pytest.fixture
def seeded_patch_session(migrated_engine: Engine) -> Session:
    with Session(migrated_engine) as session:
        session.execute(
            insert(Patch).values(
                version="17.8",
                set_number=17,
                released_at=datetime(2026, 1, 1, tzinfo=UTC),
                is_current=True,
                detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.commit()
        yield session


def _doc_with_id(session: Session, source_id: int) -> MetaDocumentEmbedding:
    doc = MetaDocumentEmbedding(
        patch_version="17.8",
        doc_type="comp",
        source_table="comps",
        source_id=source_id,
        content_text="mock",
        embedding=[0.0] * 1024,
        doc_metadata={"name": "이즈리얼 캐리"},
    )
    session.add(doc)
    session.flush()
    return doc


# ---- record_chat_log: 필드 전체 적재 ---------------------------------------------


def test_record_chat_log_persists_all_fields(seeded_patch_session: Session) -> None:
    doc = _doc_with_id(seeded_patch_session, 1)

    log = record_chat_log(
        seeded_patch_session,
        session_id="11111111-1111-1111-1111-111111111111",
        patch_version="17.8",
        user_query="지금 메타 조합 추천해줘",
        intent=INTENT_COMP_RECOMMENDATION,
        retrieved_docs=[doc],
        answer="'이즈리얼 캐리' 조합을 추천드립니다.",
        latency_ms=1500,
    )

    fetched = seeded_patch_session.get(ChatLog, log.id)
    assert fetched is not None
    assert fetched.session_id == "11111111-1111-1111-1111-111111111111"
    assert fetched.patch_version == "17.8"
    assert fetched.user_query == "지금 메타 조합 추천해줘"
    assert fetched.intent == INTENT_COMP_RECOMMENDATION
    assert fetched.retrieved_doc_ids == [doc.id]
    assert fetched.answer == "'이즈리얼 캐리' 조합을 추천드립니다."
    assert fetched.latency_ms == 1500
    assert fetched.cold_start is False
    assert fetched.created_at is not None


def test_record_chat_log_marks_cold_start_above_threshold(
    seeded_patch_session: Session,
) -> None:
    log = record_chat_log(
        seeded_patch_session,
        session_id="11111111-1111-1111-1111-111111111111",
        patch_version="17.8",
        user_query="질문",
        intent=INTENT_COMP_RECOMMENDATION,
        retrieved_docs=[],
        answer="답변",
        latency_ms=COLD_START_THRESHOLD_MS,
    )
    assert log.cold_start is True


def test_record_chat_log_below_threshold_is_not_cold_start(
    seeded_patch_session: Session,
) -> None:
    log = record_chat_log(
        seeded_patch_session,
        session_id="11111111-1111-1111-1111-111111111111",
        patch_version="17.8",
        user_query="질문",
        intent=INTENT_COMP_RECOMMENDATION,
        retrieved_docs=[],
        answer="답변",
        latency_ms=COLD_START_THRESHOLD_MS - 1,
    )
    assert log.cold_start is False


def test_record_chat_log_empty_retrieved_docs_stores_empty_list(
    seeded_patch_session: Session,
) -> None:
    log = record_chat_log(
        seeded_patch_session,
        session_id="11111111-1111-1111-1111-111111111111",
        patch_version="17.8",
        user_query="질문",
        intent=INTENT_COMP_RECOMMENDATION,
        retrieved_docs=[],
        answer="답변",
        latency_ms=100,
    )
    assert log.retrieved_doc_ids == []


# ---- generate_answer_stream 배선: 정상 흐름에서만 로깅 --------------------------


def test_normal_flow_creates_chat_log_row(seeded_patch_session: Session) -> None:
    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "'이즈리얼 캐리' 조합을 추천드려요."

    session_id = "11111111-1111-1111-1111-111111111111"
    list(
        generate_answer_stream(
            seeded_patch_session,
            session_id,
            "지금 메타 조합 추천해줘",
            embed_fn=lambda text: [0.0],
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_COMP_RECOMMENDATION,
            search_fn=lambda db, intent, patch, emb: [],
            stream_fn=fake_stream_fn,
        )
    )

    logs = seeded_patch_session.scalars(
        select(ChatLog).where(ChatLog.session_id == session_id)
    ).all()
    assert len(logs) == 1
    assert logs[0].intent == INTENT_COMP_RECOMMENDATION
    assert logs[0].patch_version == "17.8"
    assert logs[0].user_query == "지금 메타 조합 추천해줘"
    assert "이즈리얼 캐리" in logs[0].answer
    assert logs[0].latency_ms >= 0


def test_needs_clarification_does_not_create_chat_log(
    seeded_patch_session: Session,
) -> None:
    session_id = "22222222-2222-2222-2222-222222222222"

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("호출되면 안 됨")

    list(
        generate_answer_stream(
            seeded_patch_session,
            session_id,
            "   ",
            embed_fn=_fail_if_called,
            offtopic_confirm_fn=lambda text: False,
            classify_fn=_fail_if_called,
            search_fn=_fail_if_called,
            stream_fn=_fail_if_called,
        )
    )

    logs = seeded_patch_session.scalars(
        select(ChatLog).where(ChatLog.session_id == session_id)
    ).all()
    assert logs == []
