"""CHAT-11 pytest(WBS 테스트 요구사항: 후속질문 생성 함수 고정 fixture 입력 ->
질문 형식/개수 검증, Groq 실패 시 후속질문 없이도 기존 답변 스트리밍은 정상
동작하는지(폴백) 확인). 외부 API(Groq)는 전부 주입식 fake로 대체(policies.md
10.2/11)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.models import MetaDocumentEmbedding, Patch
from services.chat_cache import get_cached_answer, store_answer_in_cache
from services.chat_followups import (
    MAX_FOLLOWUP_QUESTIONS,
    generate_followup_questions,
)
from services.chat_stream import (
    FALLBACK_MESSAGE,
    build_sse_stream,
    generate_answer_stream,
)
from services.intent_classification import INTENT_COMP_RECOMMENDATION

# ---- generate_followup_questions ------------------------------------------------


def _fail_if_called(*args: object, **kwargs: object) -> str:
    raise AssertionError("llm_call이 호출되면 안 됨(빈 답변은 호출 없이 조기 반환)")


def test_generate_followup_questions_parses_multiline_output() -> None:
    # MAX_FOLLOWUP_QUESTIONS=1(2026-08-07 PM 결정, 화면에 1개만 노출)이라
    # LLM이 여러 줄을 출력해도 첫 줄만 남는지 확인한다(멀티라인 파싱 자체는
    # 여전히 정상 동작해야 함).
    def llm_call(system_prompt: str, user_message: str, *, max_tokens: int) -> str:
        return "그 조합에 어울리는 증강체는?\n다른 S티어 조합도 알려줘\n이 조합의 코어 아이템은?"

    questions = generate_followup_questions("17.8 패치 기준 답변", llm_call)

    assert questions == ["그 조합에 어울리는 증강체는?"]


def test_generate_followup_questions_strips_bullet_characters_and_blank_lines() -> None:
    def llm_call(system_prompt: str, user_message: str, *, max_tokens: int) -> str:
        return "- 질문 하나\n\n* 질문 둘\n   \n"

    questions = generate_followup_questions("답변", llm_call)

    assert questions == ["질문 하나"]


def test_generate_followup_questions_caps_at_max_questions() -> None:
    def llm_call(system_prompt: str, user_message: str, *, max_tokens: int) -> str:
        return "\n".join(f"질문 {i}" for i in range(10))

    questions = generate_followup_questions("답변", llm_call)

    assert len(questions) == MAX_FOLLOWUP_QUESTIONS
    assert questions == ["질문 0"]


def test_generate_followup_questions_returns_empty_list_for_blank_answer() -> None:
    assert generate_followup_questions("", _fail_if_called) == []
    assert generate_followup_questions("   ", _fail_if_called) == []


def test_generate_followup_questions_falls_back_to_empty_list_on_llm_error() -> None:
    def llm_call(system_prompt: str, user_message: str, *, max_tokens: int) -> str:
        raise TimeoutError("mock Groq 오류")

    assert generate_followup_questions("답변", llm_call) == []


def test_generate_followup_questions_returns_empty_list_when_llm_has_nothing_to_suggest() -> (
    None
):
    def llm_call(system_prompt: str, user_message: str, *, max_tokens: int) -> str:
        return "   \n\n"

    assert generate_followup_questions("답변", llm_call) == []


# ---- CHAT-14 2차 수정(2026-08-09): 원인 분석형 후속 질문 억제 -------------------
# PM 실사용 제보: "블리츠크랭크와 바드가 높은 승률을 보인 이유는?"처럼 답할 수
# 없는 원인 분석 질문이 후속질문으로 제안된 적이 있음(직전 답변이 item_build
# 문서 — 승률 수치만 있고 이유를 설명하는 문서가 아니었음). comp/playstyle
# 문서(플레이 스타일 설명 있음)에서 나온 답변에는 이 규칙을 붙이지 않는다.


def test_generate_followup_questions_adds_no_reasoning_rule_when_no_narrative_docs() -> (
    None
):
    captured: dict[str, str] = {}

    def llm_call(system_prompt: str, user_message: str, *, max_tokens: int) -> str:
        captured["system_prompt"] = system_prompt
        return "질문"

    generate_followup_questions(
        "답변", llm_call, retrieved_doc_types={"item_build", "champion"}
    )

    assert "원인·이유를" in captured["system_prompt"]


def test_generate_followup_questions_omits_no_reasoning_rule_when_comp_doc_present() -> (
    None
):
    captured: dict[str, str] = {}

    def llm_call(system_prompt: str, user_message: str, *, max_tokens: int) -> str:
        captured["system_prompt"] = system_prompt
        return "질문"

    generate_followup_questions("답변", llm_call, retrieved_doc_types={"comp"})

    assert "원인·이유를" not in captured["system_prompt"]


def test_generate_followup_questions_defaults_to_no_reasoning_rule_when_doc_types_omitted() -> (
    None
):
    captured: dict[str, str] = {}

    def llm_call(system_prompt: str, user_message: str, *, max_tokens: int) -> str:
        captured["system_prompt"] = system_prompt
        return "질문"

    generate_followup_questions("답변", llm_call)

    assert "원인·이유를" in captured["system_prompt"]


# ---- build_sse_stream followups_fn 배선 -----------------------------------------


def test_build_sse_stream_emits_followups_event_before_done() -> None:
    def tokens():
        yield from ["안녕", "하세요"]

    events = list(
        build_sse_stream(tokens(), followups_fn=lambda: ["후속 질문 1", "후속 질문 2"])
    )

    assert events[:2] == ["data: 안녕\n\n", "data: 하세요\n\n"]
    assert events[2] == 'event: followups\ndata: ["후속 질문 1", "후속 질문 2"]\n\n'
    assert events[3] == "event: done\ndata: [DONE]\n\n"


def test_build_sse_stream_skips_followups_event_when_list_is_empty() -> None:
    def tokens():
        yield "안녕"

    events = list(build_sse_stream(tokens(), followups_fn=lambda: []))

    assert events == ["data: 안녕\n\n", "event: done\ndata: [DONE]\n\n"]


def test_build_sse_stream_without_followups_fn_is_unchanged() -> None:
    """followups_fn을 안 넘기면(기존 API-09/CHAT-05 호출부) 기존 동작 그대로다."""

    def tokens():
        yield "안녕"

    events = list(build_sse_stream(tokens()))

    assert events == ["data: 안녕\n\n", "event: done\ndata: [DONE]\n\n"]


# ---- generate_answer_stream의 result 사이드채널(CHAT-11용) -----------------------


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


def test_result_is_populated_with_final_answer_on_normal_flow(
    seeded_patch_session: Session,
) -> None:
    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "생성된 답변"

    result: dict[str, object] = {}
    list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "지금 메타 조합 추천해줘",
            embed_fn=lambda text: [0.0],
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_COMP_RECOMMENDATION,
            search_fn=lambda db, intent, patch, emb: [MetaDocumentEmbedding()],
            stream_fn=fake_stream_fn,
            result=result,
        )
    )

    assert result["answer_text"] == "생성된 답변"


def test_result_carries_retrieved_doc_types_for_followup_context(
    seeded_patch_session: Session,
) -> None:
    """CHAT-14 2차 수정(2026-08-09): chat_followups가 원인 분석형 후속 질문을
    걸러낼지 판단할 수 있도록 result에 doc_type 집합도 함께 담는다."""

    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "생성된 답변"

    docs = [
        MetaDocumentEmbedding(doc_type="comp"),
        MetaDocumentEmbedding(doc_type="playstyle"),
    ]
    result: dict[str, object] = {}
    list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "지금 메타 조합 추천해줘",
            embed_fn=lambda text: [0.0],
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_COMP_RECOMMENDATION,
            search_fn=lambda db, intent, patch, emb: docs,
            stream_fn=fake_stream_fn,
            result=result,
        )
    )

    assert result["retrieved_doc_types"] == {"comp", "playstyle"}


def test_result_stays_empty_and_answer_not_cached_when_no_docs_retrieved(
    seeded_patch_session: Session,
) -> None:
    """2026-08-07 PM 피드백: 검색된 문서가 없어 "해당 정보는 확인되지 않았습니다"
    류로만 답한 턴은 후속질문 생성 대상에서 빠져야 한다(근거 문서가 없어
    "그 정보 어디서 확인하나요" 같은 무의미한 후속질문만 나오던 문제) —
    캐시도 되지 않아야 이후 캐시 히트로 같은 문제가 재발하지 않는다."""

    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "해당 정보는 확인되지 않았습니다."

    result: dict[str, object] = {}
    list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "지금 메타 조합 추천해줘",
            embed_fn=lambda text: [0.0],
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_COMP_RECOMMENDATION,
            search_fn=lambda db, intent, patch, emb: [],
            stream_fn=fake_stream_fn,
            result=result,
        )
    )

    assert result == {}
    assert (
        get_cached_answer(seeded_patch_session, "지금 메타 조합 추천해줘", "17.8")
        is None
    )


def test_result_stays_empty_but_answer_still_cached_when_docs_found_but_answer_says_no_info(
    seeded_patch_session: Session,
) -> None:
    """2026-08-09 PM 피드백: retrieved_docs는 찾았지만(예: 아이템 문서는 검색됨)
    질문이 원하는 세부 수치가 그 안에 없어 "정보가 제공되지 않았습니다"류로 답한
    턴은, 문서가 아예 없던 기존 케이스와 달리 근거 문서 자체는 있으므로 캐시는
    그대로 되어야 한다(동일 질문 재사용 가능) — 다만 후속질문 생성 대상에서는
    빠져야 한다(같은 정보를 더 정확히 알려달라는 무의미한 후속질문 방지). 모델이
    시스템 프롬프트 1번 규칙 문구를 그대로 재현하지 않고 어미를 바꿔("확인되지
    않았다" 대신 "제공되지 않았습니다") 답하는 경우까지 커버되는지 확인한다."""

    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "치명타 확률이 증가하지만 정확한 수치는 제공되지 않았습니다."

    question = "보석 건틀릿을 장착하면 어떤 챔피언의 치명타 확률이 가장 많이 증가해?"
    result: dict[str, object] = {}
    list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            question,
            embed_fn=lambda text: [0.0],
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_COMP_RECOMMENDATION,
            search_fn=lambda db, intent, patch, emb: [MetaDocumentEmbedding()],
            stream_fn=fake_stream_fn,
            result=result,
        )
    )

    assert result == {}
    assert get_cached_answer(seeded_patch_session, question, "17.8") is not None


def test_result_stays_empty_on_clarification_short_circuit(
    migrated_engine: Engine,
) -> None:
    with Session(migrated_engine) as session:
        result: dict[str, object] = {}
        list(
            generate_answer_stream(
                session,
                "11111111-1111-1111-1111-111111111111",
                "   ",
                embed_fn=_fail_if_called,
                offtopic_confirm_fn=lambda text: False,
                classify_fn=_fail_if_called,
                search_fn=_fail_if_called,
                stream_fn=_fail_if_called,
                result=result,
            )
        )
    assert result == {}


def test_result_is_populated_on_cache_hit(seeded_patch_session: Session) -> None:
    store_answer_in_cache(
        seeded_patch_session, "지금 메타 조합 추천해줘", "17.8", "캐시된 답변"
    )

    result: dict[str, object] = {}
    list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "지금 메타 조합 추천해줘",
            embed_fn=_fail_if_called,
            offtopic_confirm_fn=lambda text: False,
            classify_fn=_fail_if_called,
            search_fn=_fail_if_called,
            stream_fn=_fail_if_called,
            result=result,
        )
    )

    # PM 결정(2026-08-07): 캐시 히트로 첫 턴에만 후속질문칩이 안 보이는 게
    # 사용자 입장에서 일관성 없어 보인다는 피드백 — Groq 호출 1회를 감수하고
    # 캐시 히트에도 후속질문을 생성하도록 변경(레이트리밋 절감보다 UX 우선).
    assert result["answer_text"] == "캐시된 답변"
    # CHAT-14 2차 수정(2026-08-09): 캐시 히트 경로도 retrieved_doc_types를 채워야
    # chat_followups가 원인 분석형 후속 질문 억제 여부를 판단할 수 있다(이 테스트의
    # 캐시 행은 retrieved_doc_ids가 없어 빈 집합이지만, 키 자체는 항상 존재해야 함).
    assert result["retrieved_doc_types"] == set()


def test_result_stays_empty_when_groq_fully_fails(
    seeded_patch_session: Session,
) -> None:
    def always_failing_stream_fn(system_prompt: str, user_message: str):
        raise TimeoutError("mock Groq 완전 실패")
        yield  # pragma: no cover - 제너레이터 형태 유지용

    result: dict[str, object] = {}
    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "지금 메타 조합 추천해줘",
            embed_fn=lambda text: [0.0],
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_COMP_RECOMMENDATION,
            search_fn=lambda db, intent, patch, emb: [],
            stream_fn=always_failing_stream_fn,
            result=result,
        )
    )

    assert " ".join(tokens) == FALLBACK_MESSAGE
    assert result == {}


def test_generate_answer_stream_without_result_kwarg_still_works(
    seeded_patch_session: Session,
) -> None:
    """result를 안 넘기면(기존 CHAT-08/CHAT-09 호출부) 기존 동작 그대로다."""

    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "답변"

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "지금 메타 조합 추천해줘",
            embed_fn=lambda text: [0.0],
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_COMP_RECOMMENDATION,
            search_fn=lambda db, intent, patch, emb: [],
            stream_fn=fake_stream_fn,
        )
    )

    assert tokens == ["답변"]
