"""CHAT-30 pytest: 웹검색 답변의 본문 내용(세트 번호·날짜 등 구체적 사실)이
실제 검색 결과에 근거하는지 검증하는 결정론적 사후 점검. TEST-11 H15가
할루시네이션 URL과는 별개로 본문 자체(세트 15/14, 2025년 말~2026년 초)를
검색 결과에 없는 내용으로 지어낸 사례를 재현·방지한다."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.models import Patch
from services.chat_stream import generate_answer_stream
from services.intent_classification import INTENT_GENERAL_GAME_INFO
from services.prompt_assembly import WEB_SEARCH_SYSTEM_PROMPT
from services.web_search import (
    UNGROUNDED_CONTENT_WARNING,
    WebSearchResult,
    verify_web_content_grounding,
)


def _fail_if_called(name: str):
    def _fn(*args: object, **kwargs: object) -> object:
        raise AssertionError(f"{name}이 호출되면 안 됨")

    return _fn


# ---- verify_web_content_grounding ---------------------------------------------------


def test_flags_set_number_not_present_in_search_results() -> None:
    """H15 재현 — 답변이 "세트 15"를 언급하지만 검색 결과 어디에도 없다."""
    results = [
        WebSearchResult(
            title="TFT 공식 로드맵", url="https://a.example/1", content="세트 17 정보"
        )
    ]
    answer = "다음다음 세트는 세트 15이며 소년만화 배틀물 컨셉입니다."
    result = verify_web_content_grounding(answer, results)
    assert UNGROUNDED_CONTENT_WARNING in result


def test_does_not_flag_set_number_present_in_search_results() -> None:
    """회귀 방지 — 실제로 검색 결과에 있는 세트 번호는 정상 통과해야 한다."""
    results = [
        WebSearchResult(
            title="Set 18 공지", url="https://a.example/1", content="세트 18 출시"
        )
    ]
    answer = "다음 세트는 세트 18로 확인됩니다."
    assert verify_web_content_grounding(answer, results) == answer


def test_flags_explicit_date_not_present_in_search_results() -> None:
    """E5 계열 — 검색 결과에 없는 구체적 날짜를 단정하면 경고가 붙어야 한다."""
    results = [
        WebSearchResult(
            title="패치 안내", url="https://a.example/1", content="정기 패치"
        )
    ]
    answer = "다음 패치는 2025년 12월 25일에 나옵니다."
    result = verify_web_content_grounding(answer, results)
    assert UNGROUNDED_CONTENT_WARNING in result


def test_does_not_flag_explicit_date_present_in_search_results() -> None:
    results = [
        WebSearchResult(
            title="공식 발표", url="https://a.example/1", content="2026-08-26 출시 예정"
        )
    ]
    answer = "정식 출시일은 2026-08-26으로 공지되었습니다."
    assert verify_web_content_grounding(answer, results) == answer


def test_passthrough_when_answer_mentions_no_set_or_date() -> None:
    """과잉 차단 방지 — 세트 번호·날짜를 아예 언급하지 않는 평범한 답변은
    검색 결과 유무와 무관하게 그대로 통과해야 한다."""
    answer = "해당 정보는 확인되지 않았습니다."
    assert verify_web_content_grounding(answer, []) == answer


# ---- 프롬프트 규칙: 목록 나열도 근거 문서에 있는 항목만(H18) -----------------------


def test_web_search_system_prompt_forbids_fabricating_list_items() -> None:
    assert "지어내 목록을 채우지 마라" in WEB_SEARCH_SYSTEM_PROMPT


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


def test_web_search_answer_with_fabricated_set_number_gets_flagged(
    seeded_patch_session: Session,
) -> None:
    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "다음다음 세트는 세트 15이며 소년만화 배틀물 컨셉으로 알려져 있습니다."

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "다음다음 세트는 언제, 어떤 컨셉으로 나와?",
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_GENERAL_GAME_INFO,
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=lambda q: [
                WebSearchResult(
                    title="TFT 로드맵",
                    url="https://a.example/1",
                    content="세트 17 신들의 성역",
                )
            ],
            stream_fn=fake_stream_fn,
        )
    )
    joined = " ".join(tokens)
    assert "세트 번호·날짜 등 구체적 사실" in joined


def test_web_search_answer_with_grounded_content_not_flagged(
    seeded_patch_session: Session,
) -> None:
    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "Set 18은 2026-08-12에 출시되었습니다."

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "22222222-2222-2222-2222-222222222222",
            "다음 세트는 언제 나와?",
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_GENERAL_GAME_INFO,
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=lambda q: [
                WebSearchResult(
                    title="Set 18 공지",
                    url="https://a.example/1",
                    content="Set 18은 2026-08-12에 출시",
                )
            ],
            stream_fn=fake_stream_fn,
        )
    )
    joined = " ".join(tokens)
    assert "세트 번호·날짜 등 구체적 사실" not in joined
