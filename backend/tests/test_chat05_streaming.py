"""CHAT-05 pytest(WBS 테스트 요구사항: mock Groq 클라이언트로 SSE 스트리밍 조립
확인, 타임아웃 예외 처리 확인). 외부 API(Groq/HF)는 전부 주입식 fake로 대체
(policies.md 10.2/11)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.models import EMBEDDING_DIM, ChatLog, Champion, MetaDocumentEmbedding, Patch
from services.chat_stream import (
    CLARIFICATION_MESSAGE,
    FALLBACK_MESSAGE,
    NO_CURRENT_PATCH_MESSAGE,
    OFF_TOPIC_MESSAGE,
    build_sse_stream,
    generate_answer_stream,
    stream_llm_answer,
)
from services.intent_classification import (
    INTENT_COMP_RECOMMENDATION,
    INTENT_GENERAL_STRATEGY,
    INTENT_ITEM_RECOMMENDATION,
)

# ---- build_sse_stream(토큰 제너레이터 -> SSE 포맷) -------------------------------


def test_build_sse_stream_emits_data_events_then_done_event() -> None:
    def tokens():
        yield from ["가장", "좋은", "덱은"]

    events = list(build_sse_stream(tokens()))

    assert events[:-1] == ["data: 가장\n\n", "data: 좋은\n\n", "data: 덱은\n\n"]
    assert events[-1] == "event: done\ndata: [DONE]\n\n"


# CHAT-12 발견: 토큰에 개행이 섞여 있으면(CHAT-12 서식 규칙 도입으로 흔해짐)
# `data: <토큰>\n\n`의 원문 개행이 SSE 이벤트 구분자(`\n\n`)와 뒤섞여
# chat-stream.ts가 그 줄 이후 내용을 통째로 잃어버리는 문제가 있었음 —
# 토큰 내부 개행을 `\\n`으로 이스케이프해 이벤트 경계와 절대 섞이지 않게 한다.
def test_build_sse_stream_escapes_newlines_inside_a_token() -> None:
    def tokens():
        yield from ["손길\n- 이즈리얼:", "아이템"]

    events = list(build_sse_stream(tokens()))

    assert events[0] == "data: 손길\\n- 이즈리얼:\n\n"
    assert "\n" not in events[0].removesuffix("\n\n")


# ---- stream_llm_answer: 재시도 + 폴백(WBS 핵심 요구사항) -------------------------


def test_stream_llm_answer_succeeds_on_first_try() -> None:
    def stream_fn(system_prompt: str, user_message: str):
        yield from ["안녕", "하세요"]

    tokens = list(stream_llm_answer("sys", "user", stream_fn))
    assert tokens == ["안녕", "하세요"]


def test_stream_llm_answer_retries_once_on_failure_before_any_token() -> None:
    attempts = {"n": 0}

    def stream_fn(system_prompt: str, user_message: str):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise TimeoutError("mock 타임아웃")
        yield from ["재시도", "성공"]

    tokens = list(stream_llm_answer("sys", "user", stream_fn))

    assert attempts["n"] == 2
    assert tokens == ["재시도", "성공"]


def test_stream_llm_answer_falls_back_after_exhausting_retries() -> None:
    def stream_fn(system_prompt: str, user_message: str):
        raise TimeoutError("mock 타임아웃")
        yield  # pragma: no cover - 제너레이터 형태 유지용

    tokens = list(stream_llm_answer("sys", "user", stream_fn))

    assert tokens == [FALLBACK_MESSAGE]


def test_stream_llm_answer_falls_back_without_retry_if_partial_tokens_already_sent() -> (
    None
):
    """스트림 도중 실패하면(이미 일부 토큰을 보낸 뒤) 재시도하지 않고
    폴백 메시지를 이어 붙인다(중복 전송 방지)."""
    attempts = {"n": 0}

    def stream_fn(system_prompt: str, user_message: str):
        attempts["n"] += 1
        yield "일부"
        raise TimeoutError("mock 도중 실패")

    tokens = list(stream_llm_answer("sys", "user", stream_fn))

    assert attempts["n"] == 1  # 재시도 안 함
    assert tokens == ["일부", FALLBACK_MESSAGE]


# ---- generate_answer_stream: 전처리 분기 + 전체 배선 -----------------------------


def _fail_if_called(name: str):
    def _fn(*args, **kwargs):
        raise AssertionError(f"{name}가 호출되면 안 됨(범위 밖/명확화 분기여야 함)")

    return _fn


def test_needs_clarification_short_circuits_without_calling_pipeline(
    migrated_engine: Engine,
) -> None:
    with Session(migrated_engine) as session:
        tokens = list(
            generate_answer_stream(
                session,
                "11111111-1111-1111-1111-111111111111",
                "   ",  # 공백만 -> needs_clarification
                embed_fn=_fail_if_called("embed_fn"),
                offtopic_confirm_fn=lambda text: False,
                classify_fn=_fail_if_called("classify_fn"),
                search_fn=_fail_if_called("search_fn"),
                web_search_fn=lambda text: [],
                stream_fn=_fail_if_called("stream_fn"),
            )
        )
    assert tokens == [CLARIFICATION_MESSAGE]


def test_off_topic_short_circuits_without_calling_pipeline(
    migrated_engine: Engine,
) -> None:
    with Session(migrated_engine) as session:
        tokens = list(
            generate_answer_stream(
                session,
                "11111111-1111-1111-1111-111111111111",
                "오늘 점심 뭐 먹지",  # TFT 무관 — 키워드 미스 + 2차 LLM도 off_topic 확인
                embed_fn=_fail_if_called("embed_fn"),
                offtopic_confirm_fn=lambda text: True,
                classify_fn=_fail_if_called("classify_fn"),
                search_fn=_fail_if_called("search_fn"),
                web_search_fn=lambda text: [],
                stream_fn=_fail_if_called("stream_fn"),
            )
        )
    assert tokens == [OFF_TOPIC_MESSAGE]


def test_off_topic_keyword_miss_but_llm_confirms_on_topic_continues_pipeline(
    seeded_patch_session: Session,
) -> None:
    """CHAT-16: 키워드 매칭은 실패(off_topic 후보)했지만 2차 LLM 검증이
    on_topic이라고 판단하면 거부하지 않고 정상 파이프라인을 계속 태운다."""

    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "생성된 답변"

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "시즌 종료는 언제야",  # 키워드 미스, 하지만 TFT 관련
            embed_fn=lambda text: [0.0],
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_GENERAL_STRATEGY,
            search_fn=lambda db, intent, patch, emb: [],
            web_search_fn=lambda text: [],
            stream_fn=fake_stream_fn,
        )
    )
    assert tokens == ["생성된", "답변"]


def test_no_current_patch_returns_fixed_message(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        tokens = list(
            generate_answer_stream(
                session,
                "11111111-1111-1111-1111-111111111111",
                "지금 메타 조합 추천해줘",
                embed_fn=_fail_if_called("embed_fn"),
                offtopic_confirm_fn=lambda text: False,
                classify_fn=_fail_if_called("classify_fn"),
                search_fn=_fail_if_called("search_fn"),
                web_search_fn=lambda text: [],
                stream_fn=_fail_if_called("stream_fn"),
            )
        )
    assert tokens == [NO_CURRENT_PATCH_MESSAGE]


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


def test_normal_flow_wires_intent_search_and_prompt_into_stream_fn(
    seeded_patch_session: Session,
) -> None:
    calls: dict = {}

    def fake_embed_fn(text: str) -> list[float]:
        calls["embed_text"] = text
        return [0.1, 0.2]

    def fake_classify_fn(text: str) -> str:
        calls["classify_text"] = text
        return INTENT_COMP_RECOMMENDATION

    def fake_search_fn(db, intent, patch_version, embedding):
        calls["search_args"] = (intent, patch_version, embedding)
        return []

    def fake_stream_fn(system_prompt: str, user_message: str):
        calls["system_prompt"] = system_prompt
        calls["user_message"] = user_message
        # CHAT-06부터 generate_answer_stream이 전체 응답을 버퍼링("".join)한 뒤
        # 공백 기준으로 다시 쪼개 내보내므로, 실제 Groq 델타처럼 두 번째 토큰에
        # 선행 공백을 포함시켜야 "안녕 하세요"로 정확히 복원된다.
        yield from ["안녕", " 하세요"]

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "지금 메타 조합 추천해줘",
            embed_fn=fake_embed_fn,
            offtopic_confirm_fn=lambda text: False,
            classify_fn=fake_classify_fn,
            search_fn=fake_search_fn,
            web_search_fn=lambda text: [],
            stream_fn=fake_stream_fn,
        )
    )

    assert tokens == ["안녕", "하세요"]
    assert calls["classify_text"] == "지금 메타 조합 추천해줘"
    assert calls["embed_text"] == "지금 메타 조합 추천해줘"
    assert calls["search_args"] == (INTENT_COMP_RECOMMENDATION, "17.8", [0.1, 0.2])
    assert "[사용자 메시지]" in calls["user_message"]
    assert "지금 메타 조합 추천해줘" in calls["user_message"]
    assert "티어" in calls["system_prompt"]  # 조합 추천 의도별 추가지시 포함


# CHAT-15 2차 보정(2026-08-09 PM 검증 중 발견): search_fn이 거리 임계값을 통과한
# item/augment 문서를 반환하더라도, 이름이 질의 문자열과 거의 안 겹치면
# generate_answer_stream 단계에서 한 번 더 걸러져야 한다("광폭검 효과는?"이
# '포악한 절단검'과 거리만으로는 통과하던 실제 사례).
class _FakeItemDoc:
    def __init__(self, name: str, content_text: str) -> None:
        self.doc_type = "item"
        self.doc_metadata = {"name": name}
        self.content_text = content_text
        self.id = 1


def test_item_doc_with_no_name_overlap_is_dropped_from_prompt(
    seeded_patch_session: Session,
) -> None:
    doc = _FakeItemDoc("포악한 절단검", "포악한 절단검: 기본 공격 시 광역 피해")
    captured: dict[str, str] = {}

    def fake_stream_fn(system_prompt: str, user_message: str):
        captured["user_message"] = user_message
        yield "안녕"

    list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "광폭검 효과는?",
            embed_fn=lambda text: [0.1, 0.2],
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_ITEM_RECOMMENDATION,
            search_fn=lambda db, intent, patch, emb: [doc],
            web_search_fn=lambda text: [],
            stream_fn=fake_stream_fn,
        )
    )
    assert "포악한 절단검" not in captured["user_message"]


def test_item_doc_with_name_overlap_is_kept_in_prompt(
    seeded_patch_session: Session,
) -> None:
    doc = _FakeItemDoc("보석 건틀릿", "보석 건틀릿: 치명타 확률이 증가합니다.")
    captured: dict[str, str] = {}

    def fake_stream_fn(system_prompt: str, user_message: str):
        captured["user_message"] = user_message
        yield "안녕"

    list(
        generate_answer_stream(
            seeded_patch_session,
            "33333333-3333-3333-3333-333333333333",
            "보석 건틀릿 효과는?",
            embed_fn=lambda text: [0.1, 0.2],
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_ITEM_RECOMMENDATION,
            search_fn=lambda db, intent, patch, emb: [doc],
            web_search_fn=lambda text: [],
            stream_fn=fake_stream_fn,
        )
    )
    assert "보석 건틀릿" in captured["user_message"]


def test_normal_flow_includes_conversation_history_in_prompt(
    seeded_patch_session: Session,
) -> None:
    seeded_patch_session.execute(
        insert(ChatLog).values(
            session_id="11111111-1111-1111-1111-111111111111",
            patch_version="17.8",
            user_query="이전 질문",
            intent=INTENT_COMP_RECOMMENDATION,
            retrieved_doc_ids={},
            answer="이전 답변",
            latency_ms=100,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    seeded_patch_session.commit()

    captured_prompt = {}

    def fake_stream_fn(system_prompt: str, user_message: str):
        captured_prompt["user_message"] = user_message
        yield "답변"

    list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "지금 메타 조합 추천해줘",
            embed_fn=lambda text: [0.0],
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_COMP_RECOMMENDATION,
            search_fn=lambda db, intent, patch, emb: [],
            web_search_fn=lambda text: [],
            stream_fn=fake_stream_fn,
        )
    )

    assert "[이전 대화]" in captured_prompt["user_message"]
    assert "이전 질문" in captured_prompt["user_message"]


# ---- 검색용 임베딩 입력에 직전 대화 포함(2026-08-07 PM 피드백) -------------------


def test_search_embedding_includes_last_bot_answer_on_followup_turn(
    seeded_patch_session: Session,
) -> None:
    """후속 턴 질문이 "이 챔피언들"처럼 직전 대화를 가리키는 대명사만 쓰면,
    현재 메시지만 임베딩해서는 무관한 문서가 뽑히는 문제가 실제로 확인됨
    (5코스트 챔피언 9명을 물었는데 답변에 1명만 등장) — 검색용 임베딩
    입력에 직전 봇 답변이 함께 들어가는지 확인한다."""
    seeded_patch_session.execute(
        insert(ChatLog).values(
            session_id="11111111-1111-1111-1111-111111111111",
            patch_version="17.8",
            user_query="5코스트 챔피언은?",
            intent=INTENT_COMP_RECOMMENDATION,
            retrieved_doc_ids={},
            answer="블리츠크랭크, 벡스, 바드입니다.",
            latency_ms=100,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    seeded_patch_session.commit()

    captured: dict[str, str] = {}

    def fake_embed_fn(text: str) -> list[float]:
        captured["text"] = text
        return [0.0]

    list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "이 챔피언들 아이템 뭐 써야해",
            embed_fn=fake_embed_fn,
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_COMP_RECOMMENDATION,
            search_fn=lambda db, intent, patch, emb: [],
            web_search_fn=lambda text: [],
            stream_fn=lambda sp, um: iter(["답변"]),
        )
    )

    assert "블리츠크랭크, 벡스, 바드입니다." in captured["text"]
    assert "이 챔피언들 아이템 뭐 써야해" in captured["text"]


def test_search_embedding_is_just_current_message_on_first_turn(
    seeded_patch_session: Session,
) -> None:
    captured: dict[str, str] = {}

    def fake_embed_fn(text: str) -> list[float]:
        captured["text"] = text
        return [0.0]

    list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "지금 메타 조합 추천해줘",
            embed_fn=fake_embed_fn,
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_COMP_RECOMMENDATION,
            search_fn=lambda db, intent, patch, emb: [],
            web_search_fn=lambda text: [],
            stream_fn=lambda sp, um: iter(["답변"]),
        )
    )

    assert captured["text"] == "지금 메타 조합 추천해줘"


# ---- item_recommendation 후속질문 구조화 조회(2026-08-07 PM 요청) --------------


def test_item_recommendation_followup_bypasses_embed_and_search_via_structured_lookup(
    seeded_patch_session: Session,
) -> None:
    """직전 답변에 챔피언 링크가 있으면 의미 검색(embed_fn/search_fn)을 아예
    호출하지 않고 정확한 champion_id로 구조화 조회해야 한다(2026-08-07 PM
    요청 — "이 챔피언들" 후속질문에 무관한 챔피언이 섞이던 문제의 근본
    해결책). embed_fn/search_fn이 호출되면 즉시 실패시켜 우회를 검증한다."""
    seeded_patch_session.execute(
        insert(Champion).values(
            patch_version="17.8",
            riot_champion_id="TFT17_Bard",
            name_kr="바드",
            name_en="Bard",
            cost=5,
        )
    )
    seeded_patch_session.flush()
    champion_id = seeded_patch_session.scalar(
        select(Champion.id).where(Champion.riot_champion_id == "TFT17_Bard")
    )
    seeded_patch_session.execute(
        insert(MetaDocumentEmbedding).values(
            patch_version="17.8",
            doc_type="item_build",
            source_table="champion_item_builds",
            source_id=1,
            content_text="바드 아이템 빌드: 보석 건틀릿, 내셔의 이빨, 라바돈의 죽음모자.",
            embedding=[0.0] * EMBEDDING_DIM,
            doc_metadata={"champion": "바드"},
        )
    )
    seeded_patch_session.execute(
        insert(ChatLog).values(
            session_id="11111111-1111-1111-1111-111111111111",
            patch_version="17.8",
            user_query="5코스트 챔피언은?",
            intent=INTENT_COMP_RECOMMENDATION,
            retrieved_doc_ids={},
            answer=f"[바드](/items/builds?champion_id={champion_id}) 등입니다.",
            latency_ms=100,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    seeded_patch_session.commit()

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "이 챔피언 아이템 뭐 써야해",
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_ITEM_RECOMMENDATION,
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=lambda text: [],
            stream_fn=lambda sp, um: iter(["답변"]),
        )
    )

    assert tokens == ["답변"]


def test_item_recommendation_followup_without_champion_links_falls_back_to_search(
    seeded_patch_session: Session,
) -> None:
    """직전 답변에 챔피언 링크가 없으면(예: 조합 링크만 있음) 기존처럼
    의미 검색으로 폴백해야 한다."""
    seeded_patch_session.execute(
        insert(ChatLog).values(
            session_id="11111111-1111-1111-1111-111111111111",
            patch_version="17.8",
            user_query="지금 메타 조합 추천해줘",
            intent=INTENT_COMP_RECOMMENDATION,
            retrieved_doc_ids={},
            answer="[아이오니아 마법사](/comps?id=1) 조합이 강세입니다.",
            latency_ms=100,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    seeded_patch_session.commit()

    search_called = {"value": False}

    def fake_search_fn(db, intent, patch, emb):
        search_called["value"] = True
        return []

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "아이템은 뭐가 좋아",
            embed_fn=lambda text: [0.0],
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_ITEM_RECOMMENDATION,
            search_fn=fake_search_fn,
            web_search_fn=lambda text: [],
            stream_fn=lambda sp, um: iter(["답변"]),
        )
    )

    assert search_called["value"] is True
    assert tokens == ["답변"]
