"""CHAT-32 pytest: 다중 주제 복합질의 항목별 분해 응답. TEST-11 H12
("아이템 조합표랑 이번 패치노트랑 랭크 시스템 다 한 번에 알려줘")가 첫
주제만 답하고 나머지를 침묵하던 문제를 재현·방지한다."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.models import ChatLog, Patch
from services.chat_preprocessing import detect_multi_topic_signals, multi_topic_labels
from services.chat_stream import (
    MULTI_TOPIC_INTENT_LABEL,
    generate_answer_stream,
)
from services.prompt_assembly import (
    MULTI_TOPIC_SYSTEM_PROMPT,
    assemble_multi_topic_user_turn,
)


def _fail_if_called(name: str):
    def _fn(*args: object, **kwargs: object) -> object:
        raise AssertionError(f"{name}이 호출되면 안 됨")

    return _fn


H12_QUERY = "아이템 조합표랑 이번 패치노트랑 랭크 시스템 다 한 번에 알려줘."


# ---- detect_multi_topic_signals -----------------------------------------------------


def test_detects_all_three_topics_in_h12() -> None:
    topics = detect_multi_topic_signals(H12_QUERY)
    assert set(topics) == {"item_combination", "patch_notes", "rank_system"}


@pytest.mark.parametrize(
    "query",
    [
        "아이템 조합표를 알려주세요.",  # C1류, 단일 주제
        "이번 패치노트 알려줘",
        "랭크 시스템이 궁금해요",
        "지금 메타에서 강한 조합 추천해줘",  # 정상 추천 요청, 무관한 오탐 방지
    ],
)
def test_does_not_flag_single_topic_questions(query: str) -> None:
    assert len(detect_multi_topic_signals(query)) < 2


def test_multi_topic_labels_maps_to_korean_display_names() -> None:
    labels = multi_topic_labels(["item_combination", "patch_notes", "rank_system"])
    assert labels == ["아이템 조합", "패치노트", "랭크 시스템"]


# ---- prompt_assembly -----------------------------------------------------------------


def test_multi_topic_system_prompt_requires_answering_every_topic() -> None:
    assert "하나도 빠짐없이" in MULTI_TOPIC_SYSTEM_PROMPT


def test_assemble_multi_topic_user_turn_lists_requested_topics() -> None:
    from services.chat_preprocessing import wrap_user_message

    turn = assemble_multi_topic_user_turn(
        ["아이템 조합", "패치노트", "랭크 시스템"], wrap_user_message(H12_QUERY)
    )
    assert "[요청된 주제]" in turn
    assert "아이템 조합" in turn
    assert "패치노트" in turn
    assert "랭크 시스템" in turn


# ---- generate_answer_stream 배선 확인 ------------------------------------------------


@pytest.fixture
def seeded_patch_session(migrated_engine: Engine) -> Session:
    with Session(migrated_engine) as session:
        session.execute(
            insert(Patch).values(
                version="17.9",
                set_number=17,
                released_at=datetime(2026, 1, 1, tzinfo=UTC),
                is_current=True,
                detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.commit()
        yield session


def test_multi_topic_query_skips_intent_classification_and_search(
    seeded_patch_session: Session,
) -> None:
    """H12 재현 — embed_fn/search_fn/web_search_fn/classify_fn 전혀 호출되지
    않고 stream_fn만으로 답하는지 확인(general_rules와 동일한 설계)."""

    def fake_stream_fn(system_prompt: str, user_message: str):
        assert "[요청된 주제]" in user_message
        yield (
            "**아이템 조합**\n기본 아이템 2개를 조합하면 완성 아이템이 됩니다.\n\n"
            "**패치노트**\n해당 정보는 확인되지 않았습니다.\n\n"
            "**랭크 시스템**\n아이언부터 챌린저까지 여러 티어로 나뉩니다."
        )

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            H12_QUERY,
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=_fail_if_called("classify_fn"),
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=_fail_if_called("web_search_fn"),
            stream_fn=fake_stream_fn,
        )
    )
    joined = " ".join(tokens)
    assert "아이템 조합" in joined
    assert "패치노트" in joined
    assert "랭크 시스템" in joined


def test_multi_topic_query_records_chat_log_with_multi_topic_intent(
    seeded_patch_session: Session,
) -> None:
    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "답변입니다."

    session_id = "22222222-2222-2222-2222-222222222222"
    list(
        generate_answer_stream(
            seeded_patch_session,
            session_id,
            H12_QUERY,
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=_fail_if_called("classify_fn"),
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=_fail_if_called("web_search_fn"),
            stream_fn=fake_stream_fn,
        )
    )
    logs = seeded_patch_session.scalars(
        select(ChatLog).where(ChatLog.session_id == session_id)
    ).all()
    assert len(logs) == 1
    assert logs[0].intent == MULTI_TOPIC_INTENT_LABEL


# 회귀 방지 — 단일 주제 질문은 기존 의도분류 경로를 그대로 타야 한다.
def test_single_topic_question_still_uses_normal_intent_classification(
    seeded_patch_session: Session,
) -> None:
    classify_calls: list[str] = []

    def tracking_classify_fn(text: str) -> str:
        classify_calls.append(text)
        from services.intent_classification import INTENT_ITEM_RECOMMENDATION

        return INTENT_ITEM_RECOMMENDATION

    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "답변입니다."

    list(
        generate_answer_stream(
            seeded_patch_session,
            "33333333-3333-3333-3333-333333333333",
            "아이템 조합표를 알려주세요.",
            embed_fn=lambda text: [0.0],
            offtopic_confirm_fn=lambda text: False,
            classify_fn=tracking_classify_fn,
            search_fn=lambda db, intent, patch, emb: [],
            web_search_fn=lambda q: [],
            stream_fn=fake_stream_fn,
        )
    )
    assert len(classify_calls) == 1
