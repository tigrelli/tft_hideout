"""CHAT-17 pytest: 5번째 의도(general_game_info) 분류, 웹 검색 프롬프트 조립,
출처 URL 근거검증, generate_answer_stream의 웹검색 분기 배선 확인. 외부 API
(Tavily)는 전부 주입식 fake로 대체(policies.md 10.2/11 — 실제 호출 없음)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.models import ChatLog, Patch
from services.chat_preprocessing import wrap_user_message
from services.chat_stream import FALLBACK_MESSAGE, generate_answer_stream
from services.intent_classification import (
    INTENT_GENERAL_GAME_INFO,
    INTENT_GENERAL_STRATEGY,
    classify_by_keyword,
    classify_by_llm,
)
from services.prompt_assembly import (
    WEB_SEARCH_FEW_SHOT_EXAMPLE,
    WEB_SEARCH_SYSTEM_PROMPT,
    assemble_web_search_system_turn,
    assemble_web_search_user_turn,
)
from services.web_search import (
    WebSearchResult,
    is_authoritative_source,
    verify_web_citation,
)


def _fail_if_called(name: str):
    def _fn(*args: object, **kwargs: object) -> object:
        raise AssertionError(f"{name}이 호출되면 안 됨")

    return _fn


# ---- intent_classification: general_game_info ------------------------------------


def test_classify_by_keyword_does_not_match_general_game_info_queries() -> None:
    # 키워드 사전 나열이 어려운 잔여 카테고리라 1차 키워드 매칭에는 없음(설계 의도).
    assert classify_by_keyword("시즌 종료는 언제야") is None
    assert classify_by_keyword("다음 세트는 언제 나와") is None


def test_classify_by_llm_returns_general_game_info_for_season_query() -> None:
    def mock_llm_call(system_prompt: str, user_message: str) -> str:
        return "general_game_info"

    assert (
        classify_by_llm("시즌 종료는 언제야", mock_llm_call) == INTENT_GENERAL_GAME_INFO
    )


def test_classify_by_llm_still_falls_back_to_general_strategy_on_failure() -> None:
    # CHAT-17 신설 후에도 실패 시 폴백 대상은 general_game_info가 아니라
    # general_strategy로 유지(무료 티어 오류로 엉뚱하게 웹검색이 트리거되는
    # 것보다 내부 RAG 폴백이 더 안전하다는 기존 정책 유지).
    def failing_llm_call(system_prompt: str, user_message: str) -> str:
        raise TimeoutError("mock Groq 오류")

    assert classify_by_llm("애매한 질문", failing_llm_call) == INTENT_GENERAL_STRATEGY


# ---- web_search.verify_web_citation -----------------------------------------------


def test_verify_web_citation_passes_when_url_matches_search_result() -> None:
    results = [WebSearchResult(title="t", url="https://example.com/a", content="c")]
    answer = "정보입니다. (출처: https://example.com/a)"
    assert verify_web_citation(answer, results) == answer


def test_verify_web_citation_strips_trailing_punctuation_before_matching() -> None:
    results = [WebSearchResult(title="t", url="https://example.com/a", content="c")]
    answer = "출처는 https://example.com/a 입니다."
    assert verify_web_citation(answer, results) == answer


def test_verify_web_citation_appends_warning_for_unknown_url() -> None:
    results = [WebSearchResult(title="t", url="https://example.com/a", content="c")]
    answer = "정보입니다. (출처: https://not-a-real-source.com/x)"
    result = verify_web_citation(answer, results)
    assert result != answer
    assert "확인되지 않았습니다" in result


def test_verify_web_citation_passthrough_when_no_url_in_answer() -> None:
    answer = "해당 정보는 확인되지 않았습니다."
    assert verify_web_citation(answer, []) == answer


# ---- web_search.is_authoritative_source (CHAT-22) ---------------------------------


def test_is_authoritative_source_matches_known_tft_sites() -> None:
    assert is_authoritative_source("https://op.gg/tft/some-page") is True
    assert (
        is_authoritative_source(
            "https://teamfighttactics.leagueoflegends.com/en-us/news/x"
        )
        is True
    )
    assert is_authoritative_source("https://www.lolchess.gg/guide") is True


def test_is_authoritative_source_matches_subdomains() -> None:
    assert is_authoritative_source("https://na.op.gg/tft") is True


def test_is_authoritative_source_rejects_unknown_domain() -> None:
    # CHAT-22 실사례: 개인 블로그(goo-gle.tistory.com)를 근거로 상점 잠금 기능에
    # 대한 사실과 다른 단정적 답변이 나온 것을 계기로 신설.
    assert is_authoritative_source("https://goo-gle.tistory.com/44") is False
    assert is_authoritative_source("https://namu.wiki/w/전략적 팀 전투") is False


# ---- prompt_assembly: 웹검색 전용 조립 ----------------------------------------------


def test_web_search_system_prompt_requires_citation_and_polite_tone() -> None:
    assert "존댓말" in WEB_SEARCH_SYSTEM_PROMPT
    assert "출처" in WEB_SEARCH_SYSTEM_PROMPT
    assert "확인되지 않았습니다" in WEB_SEARCH_SYSTEM_PROMPT


# CHAT-20(PM 제보 2026-08-14): 실제로 답변에 쓰지 않은 무관한 검색 결과까지
# "[출처](URL)"로 무조건 나열되던 문제 — 실제 사용한 출처만, 2개 이상이면
# 번호로 구분하도록 프롬프트 규칙을 강화했는지 확인.
def test_web_search_system_prompt_requires_citing_only_used_sources_with_numbering() -> (
    None
):
    assert "실제로 답변에 근거로 사용한 출처만" in WEB_SEARCH_SYSTEM_PROMPT
    assert "출처 1" in WEB_SEARCH_SYSTEM_PROMPT
    assert "출처 2" in WEB_SEARCH_SYSTEM_PROMPT


def test_assemble_web_search_system_turn_includes_few_shot() -> None:
    turn = assemble_web_search_system_turn()
    assert WEB_SEARCH_SYSTEM_PROMPT in turn
    assert WEB_SEARCH_FEW_SHOT_EXAMPLE in turn


def test_assemble_web_search_user_turn_lists_results_with_source() -> None:
    results = [
        WebSearchResult(title="제목1", url="https://a.example/1", content="내용1"),
        WebSearchResult(title="제목2", url="https://a.example/2", content="내용2"),
    ]
    turn = assemble_web_search_user_turn(
        results, [], wrap_user_message("시즌 종료는 언제야")
    )
    assert "[웹 검색 결과]" in turn
    assert "제목1" in turn and "https://a.example/1" in turn
    assert "제목2" in turn and "https://a.example/2" in turn


# CHAT-22(TEST-11 카테고리 B QA에서 발견, 2026-08-15): 저신뢰 출처(개인 블로그)
# 하나만 근거로 게임 시스템 규칙을 단정한 오답 사례 — 출처 신뢰도 라벨이
# 붙어 프롬프트에 전달되는지 확인.
def test_assemble_web_search_user_turn_labels_authoritative_and_community_sources() -> (
    None
):
    results = [
        WebSearchResult(
            title="공식", url="https://op.gg/tft/page", content="공식 내용"
        ),
        WebSearchResult(
            title="블로그", url="https://goo-gle.tistory.com/44", content="블로그 내용"
        ),
    ]
    turn = assemble_web_search_user_turn(results, [], wrap_user_message("질문"))
    assert "[공식/전문] 공식" in turn
    assert "[커뮤니티/미검증] 블로그" in turn


def test_web_search_system_prompt_instructs_hedging_for_community_only_sources() -> (
    None
):
    assert "커뮤니티/미검증" in WEB_SEARCH_SYSTEM_PROMPT
    assert "공식/전문" in WEB_SEARCH_SYSTEM_PROMPT


def test_assemble_web_search_user_turn_shows_placeholder_when_no_results() -> None:
    turn = assemble_web_search_user_turn([], [], wrap_user_message("질문"))
    assert "[웹 검색 결과]\n(검색된 결과 없음)" in turn


def test_assemble_web_search_user_turn_omits_history_section_when_empty() -> None:
    turn = assemble_web_search_user_turn([], [], wrap_user_message("질문"))
    assert "[이전 대화]" not in turn


# ---- generate_answer_stream: general_game_info 분기 --------------------------------


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


def test_general_game_info_uses_web_search_not_internal_rag(
    seeded_patch_session: Session,
) -> None:
    """embed_fn/search_fn(CHAT-02 내부 RAG)은 아예 호출되지 않고, web_search_fn만
    호출되는지 확인 — CHAT-02가 커버 못하는 질문 전용 분기임을 검증."""

    def fake_stream_fn(system_prompt: str, user_message: str):
        assert "[웹 검색 결과]" in user_message
        yield "Set 18은 2026-08-12에 출시되었습니다. (출처: https://a.example/1)"

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "시즌 종료는 언제야",
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_GENERAL_GAME_INFO,
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=lambda q: [
                WebSearchResult(title="Set 18", url="https://a.example/1", content="c")
            ],
            stream_fn=fake_stream_fn,
        )
    )
    assert " ".join(tokens) == (
        "Set 18은 2026-08-12에 출시되었습니다. (출처: https://a.example/1)"
    )


# CHAT-20(PM 제보 2026-08-14): 사용자 메시지에 "TFT" 같은 스코핑 키워드가 없으면
# ("언제 서비스가 종료되나요?") Tavily가 전혀 무관한 결과를 반환하던 문제 —
# web_search_fn에 넘어가는 쿼리에 TFT 컨텍스트가 덧붙여지는지, 원래 질문
# 텍스트도 여전히 포함되는지 확인.
def test_general_game_info_web_search_query_is_scoped_with_tft_context(
    seeded_patch_session: Session,
) -> None:
    captured: dict[str, str] = {}

    def capturing_web_search_fn(query: str) -> list[WebSearchResult]:
        captured["query"] = query
        return []

    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "답변입니다."

    list(
        generate_answer_stream(
            seeded_patch_session,
            "55555555-5555-5555-5555-555555555555",
            "언제 서비스가 종료되나요?",
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_GENERAL_GAME_INFO,
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=capturing_web_search_fn,
            stream_fn=fake_stream_fn,
        )
    )
    assert "TFT" in captured["query"]
    assert "언제 서비스가 종료되나요?" in captured["query"]


def test_general_game_info_records_chat_log_with_empty_retrieved_docs(
    seeded_patch_session: Session,
) -> None:
    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "답변입니다."

    session_id = "22222222-2222-2222-2222-222222222222"
    list(
        generate_answer_stream(
            seeded_patch_session,
            session_id,
            "시즌 종료는 언제야",
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_GENERAL_GAME_INFO,
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=lambda q: [],
            stream_fn=fake_stream_fn,
        )
    )

    logs = seeded_patch_session.scalars(
        select(ChatLog).where(ChatLog.session_id == session_id)
    ).all()
    assert len(logs) == 1
    assert logs[0].intent == INTENT_GENERAL_GAME_INFO
    assert logs[0].retrieved_doc_ids == []


def test_general_game_info_falls_back_to_fallback_message_on_tavily_failure(
    seeded_patch_session: Session,
) -> None:
    session_id = "33333333-3333-3333-3333-333333333333"

    def failing_web_search_fn(query: str) -> list[WebSearchResult]:
        raise TimeoutError("mock Tavily 오류")

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            session_id,
            "시즌 종료는 언제야",
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_GENERAL_GAME_INFO,
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=failing_web_search_fn,
            stream_fn=_fail_if_called("stream_fn"),
        )
    )
    assert tokens == [FALLBACK_MESSAGE]

    logs = seeded_patch_session.scalars(
        select(ChatLog).where(ChatLog.session_id == session_id)
    ).all()
    assert logs == []


def test_general_game_info_answer_with_quoted_name_does_not_trigger_rag_grounding_warning(
    seeded_patch_session: Session,
) -> None:
    """2026-08-12 PM 제보로 발견한 회귀: postprocess_answer()의
    verify_grounding()(CHAT-06, 작은따옴표 인용을 retrieved_docs 메타데이터와
    대조)을 이 경로에 재사용하면, WEB_SEARCH_SYSTEM_PROMPT는 인용 규칙을 지시한
    적 없는데도 모델이 자연스럽게 고유명사를 인용할 때마다 retrieved_docs=[]라
    항상 "확인되지 않았습니다" 오탐 경고가 붙었다. 이 경로는 verify_web_citation
    (URL 기반)만으로 근거검증을 해야 한다."""

    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "Set 18 'Enchanted Wilds'는 2026-08-12에 출시되었습니다. [출처](https://a.example/1)"

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "99999999-9999-9999-9999-999999999999",
            "시즌 종료는 언제야",
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_GENERAL_GAME_INFO,
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=lambda q: [
                WebSearchResult(title="t", url="https://a.example/1", content="c")
            ],
            stream_fn=fake_stream_fn,
        )
    )
    answer = " ".join(tokens)
    assert "명칭은 검색된 문서에서 확인되지 않았습니다" not in answer


def test_general_game_info_answer_gets_citation_warning_for_hallucinated_url(
    seeded_patch_session: Session,
) -> None:
    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "정보입니다. (출처: https://not-in-results.example/x)"

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "44444444-4444-4444-4444-444444444444",
            "시즌 종료는 언제야",
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_GENERAL_GAME_INFO,
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=lambda q: [
                WebSearchResult(title="t", url="https://a.example/1", content="c")
            ],
            stream_fn=fake_stream_fn,
        )
    )
    assert "확인되지 않았습니다" in " ".join(tokens)
