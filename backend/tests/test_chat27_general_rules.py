"""CHAT-27 pytest: 6번째 의도(general_rules) 분류, 프롬프트 조립,
generate_answer_stream의 general_rules 분기 배선 확인. 이 경로는 외부 API도
내부 RAG 검색도 쓰지 않는 유일한 의도라(LLM 일반 지식만으로 답함), embed_fn/
search_fn/web_search_fn이 전혀 호출되지 않는지가 핵심 검증 대상이다."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.models import ChatLog, Patch
from services.chat_preprocessing import wrap_user_message
from services.chat_stream import generate_answer_stream
from services.intent_classification import (
    INTENT_GENERAL_RULES,
    INTENT_ITEM_RECOMMENDATION,
    classify_by_keyword,
    classify_by_llm,
)
from services.prompt_assembly import (
    GENERAL_RULES_FEW_SHOT_EXAMPLE,
    GENERAL_RULES_SYSTEM_PROMPT,
    assemble_general_rules_system_turn,
    assemble_general_rules_user_turn,
)


def _fail_if_called(name: str):
    def _fn(*args: object, **kwargs: object) -> object:
        raise AssertionError(f"{name}이 호출되면 안 됨")

    return _fn


# ---- intent_classification: general_rules -----------------------------------------


# TEST-11 카테고리 B/D에서 실제로 커버리지 공백이 확인된 문항 중, 1차 키워드
# (조합/덱/편성/아이템/빌드/장비/증강체/오그먼트/메타/전략)와 우연히 겹치지
# 않는 대표 질문들 — 이 문항들은 1차 키워드 매칭이 바로 None을 반환해 2차
# LLM 분류로 넘어가야 한다(설계 의도, general_game_info와 동일한 패턴).
@pytest.mark.parametrize(
    "query",
    [
        "특정 시너지는 몇 명을 모아야 다음 단계가 발동되나요?",  # B4
        "챔피언 성급(1성/2성/3성)에 따라 스킬 효과도 강해지나요?",  # B10
        "LP(리그 포인트)는 등수에 따라 어떻게 계산되나요?",  # D2
        "매칭은 어떤 기준으로 이루어지나요?",  # D5
        "세트가 교체되면 기존 랭크 점수는 유지되나요?",  # E12
    ],
)
def test_classify_by_keyword_does_not_match_general_rules_queries(
    query: str,
) -> None:
    assert classify_by_keyword(query) is None


def test_classify_by_llm_returns_general_rules_for_rule_question() -> None:
    def mock_llm_call(system_prompt: str, user_message: str) -> str:
        return "general_rules"

    assert (
        classify_by_llm("성급이 오르면 스킬도 강해지나요?", mock_llm_call)
        == INTENT_GENERAL_RULES
    )


# 알려진 한계(CHAT-28로 이관, docs/verification/CHAT-27-작업결과.md 참고):
# "장착한 아이템을 다시 제거할 수 있나요?" 같은 규칙 질문도 "아이템" 키워드
# 하나만으로 1차 매칭이 곧장 item_recommendation을 확정해버려 2차 분류
# (=general_rules 도달 경로) 자체를 못 탄다("아이템은 어떻게 조합하나요?"처럼
# "조합"까지 우연히 같이 들어간 문장은 comp_recommendation과 이중 매칭돼
# 오히려 2차로 넘어가므로 예시에서 제외 — TEST-11 C카테고리 20문항 중 15개가
# 이 "단일 키워드만 매칭" 패턴). 지금은 의도된(수정 전) 동작이므로 회귀가
# 아니라 "고쳐지면 이 값이 바뀌어야 한다"는 표식으로 남겨둔다.
def test_classify_by_keyword_still_swallows_item_worded_rule_questions() -> None:
    assert (
        classify_by_keyword("장착한 아이템을 다시 제거할 수 있나요?")
        == INTENT_ITEM_RECOMMENDATION
    )


# ---- prompt_assembly: general_rules 전용 프롬프트 ----------------------------------


def test_general_rules_system_prompt_allows_llm_general_knowledge() -> None:
    assert "일반적인 TFT 게임 지식으로 직접 답하라" in GENERAL_RULES_SYSTEM_PROMPT


def test_general_rules_system_prompt_forbids_speculating_on_patch_specific_content() -> (
    None
):
    """H15(TEST-11 카테고리 H)에서 확인된 미래 세트 정보 환각과 같은 유형을
    막기 위한 핵심 안전장치 — 시의성 있는 내용은 추측 금지를 명시해야 한다."""
    assert "절대 추측해서 단정하지 마라" in GENERAL_RULES_SYSTEM_PROMPT
    assert "확인되지 않았습니다" in GENERAL_RULES_SYSTEM_PROMPT


def test_general_rules_system_prompt_requires_polite_tone() -> None:
    assert "존댓말" in GENERAL_RULES_SYSTEM_PROMPT


def test_assemble_general_rules_system_turn_includes_few_shot() -> None:
    turn = assemble_general_rules_system_turn()
    assert GENERAL_RULES_SYSTEM_PROMPT in turn
    assert GENERAL_RULES_FEW_SHOT_EXAMPLE in turn


def test_assemble_general_rules_user_turn_omits_history_section_when_empty() -> None:
    wrapped = wrap_user_message("아이템은 어떻게 조합하나요?")
    turn = assemble_general_rules_user_turn([], wrapped)
    assert "[이전 대화]" not in turn
    assert wrapped in turn
    # 검색 문서도 웹 검색 결과도 없는 경로이므로 그런 섹션 헤더가 없어야 한다.
    assert "[검색된 문서]" not in turn
    assert "[웹 검색 결과]" not in turn


def test_assemble_general_rules_user_turn_includes_history_when_present() -> None:
    history = [
        ChatLog(
            user_query="이전 질문",
            answer="이전 답변",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]
    wrapped = wrap_user_message("후속 질문")
    turn = assemble_general_rules_user_turn(history, wrapped)
    assert "[이전 대화]" in turn
    assert "이전 질문" in turn
    assert "이전 답변" in turn


# ---- generate_answer_stream: general_rules 분기 배선 -------------------------------


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


def test_general_rules_skips_internal_rag_and_web_search(
    seeded_patch_session: Session,
) -> None:
    """embed_fn/search_fn(CHAT-02 내부 RAG)도 web_search_fn(CHAT-17)도 전혀
    호출되지 않고, stream_fn만으로 답하는지 확인 — 6개 의도 중 유일하게
    근거 검색 자체가 없는 경로임을 검증한다."""

    def fake_stream_fn(system_prompt: str, user_message: str):
        assert "[검색된 문서]" not in user_message
        assert "[웹 검색 결과]" not in user_message
        yield "기본 아이템 2개를 조합하면 완성 아이템 1개가 됩니다."

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "아이템은 어떻게 조합하나요?",
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_GENERAL_RULES,
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=_fail_if_called("web_search_fn"),
            stream_fn=fake_stream_fn,
        )
    )
    assert " ".join(tokens) == "기본 아이템 2개를 조합하면 완성 아이템 1개가 됩니다."


def test_general_rules_records_chat_log_with_empty_retrieved_docs(
    seeded_patch_session: Session,
) -> None:
    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "답변입니다."

    session_id = "22222222-2222-2222-2222-222222222222"
    list(
        generate_answer_stream(
            seeded_patch_session,
            session_id,
            "성급이 오르면 스킬도 강해지나요?",
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_GENERAL_RULES,
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=_fail_if_called("web_search_fn"),
            stream_fn=fake_stream_fn,
        )
    )

    logs = seeded_patch_session.scalars(
        select(ChatLog).where(ChatLog.session_id == session_id)
    ).all()
    assert len(logs) == 1
    assert logs[0].intent == INTENT_GENERAL_RULES
    assert logs[0].retrieved_doc_ids == []


def test_general_rules_strips_internal_doc_marker_leak(
    seeded_patch_session: Session,
) -> None:
    """LLM이 다른 의도용 프롬프트 문구를 착각해 내부 구획 표시를 그대로
    옮기는 경우(CHAT-06과 동일한 방어)를 general_rules 경로에서도 확인."""

    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "[검색된 문서]를 바탕으로 답변드리면, 그런 규칙은 없습니다."

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "33333333-3333-3333-3333-333333333333",
            "성급이 오르면 스킬도 강해지나요?",
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_GENERAL_RULES,
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=_fail_if_called("web_search_fn"),
            stream_fn=fake_stream_fn,
        )
    )
    joined = " ".join(tokens)
    assert "[검색된 문서]" not in joined
    assert "그런 규칙은 없습니다" in joined
