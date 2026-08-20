"""CHAT-29 pytest: 웹검색(general_game_info) 출처 해석 정확도·품질 개선.
TEST-11 B1/B2/B6/B24/D4/D8/D10/D14/E4/E5/E9/E15에서 실측 확인된 세 가지
실패 유형에 대응한다 — (1) 여러 출처를 조합해 어느 쪽도 말하지 않은 결론을
만드는 것, (2) 별개 개념을 질문의 답인 것처럼 연결짓는 것, (3) 오래된
세트/패치 번호를 최신인 것처럼 답하는 것 — 그리고 두 가지 인용 형식 결함
(무정보 답변에 붙는 무의미한 인용, URL 없는 "[출처]" 라벨)을 고친다."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.models import Patch
from services.chat_stream import generate_answer_stream
from services.intent_classification import INTENT_GENERAL_GAME_INFO
from services.prompt_assembly import (
    WEB_SEARCH_SYSTEM_PROMPT,
    assemble_web_search_user_turn,
)
from services.web_search import (
    UNVERIFIED_SOURCE_WARNING,
    WebSearchResult,
    verify_web_citation,
)


def _fail_if_called(name: str):
    def _fn(*args: object, **kwargs: object) -> object:
        raise AssertionError(f"{name}이 호출되면 안 됨")

    return _fn


# ---- 프롬프트 규칙: 여러 출처 조합 금지 / 별개 개념 연결 금지 -----------------------


def test_web_search_system_prompt_forbids_synthesizing_across_sources() -> None:
    """D4(듀오랭크 오독) 대응 — 어느 출처도 말하지 않은 결론을 조합해내지
    말라는 규칙이 있어야 한다."""
    assert "결론을 만들어내지 마라" in WEB_SEARCH_SYSTEM_PROMPT


def test_web_search_system_prompt_forbids_conflating_different_concepts() -> None:
    """D10(순방 vs 강등방지 개념 혼동) 대응."""
    assert "별개의 개념" in WEB_SEARCH_SYSTEM_PROMPT


def test_web_search_system_prompt_requires_trusting_known_fact_over_stale_web_content() -> (
    None
):
    """B1/E5/E9/E15(오래된 세트/패치 번호) 대응."""
    assert "[알려진 사실]" in WEB_SEARCH_SYSTEM_PROMPT
    assert "오래됐을 수 있음" in WEB_SEARCH_SYSTEM_PROMPT


# ---- assemble_web_search_user_turn: [알려진 사실] 섹션 ----------------------------


def test_assemble_web_search_user_turn_includes_known_fact_when_patch_version_given() -> (
    None
):
    turn = assemble_web_search_user_turn([], [], "질문", patch_version="17.9")
    assert "[알려진 사실]" in turn
    assert "17.9" in turn


def test_assemble_web_search_user_turn_omits_known_fact_when_patch_version_none() -> (
    None
):
    """기존 호출부·테스트 하위 호환 — patch_version을 안 넘기면(기본값 None)
    섹션 자체가 없어야 한다."""
    turn = assemble_web_search_user_turn([], [], "질문")
    assert "[알려진 사실]" not in turn


# ---- 스팟픽스: "시즌" 질문에 낡은 커뮤니티 날짜를 최신으로 착각하는 문제 -------------
# (PM 실사용 제보 — "현재 시즌은 언제까지?"에 2024년 날짜의 "시즌 11" 커뮤니티
# 글을 근거로 답변. patch_version 대조만으로는 "세트"가 아닌 "시즌" 개념·날짜
# 자체의 낡음을 못 걸러내 오늘 날짜를 [알려진 사실]에 추가로 명시한다.)


def test_web_search_system_prompt_warns_season_is_not_an_official_tft_term() -> None:
    assert "시즌" in WEB_SEARCH_SYSTEM_PROMPT
    assert "오늘" in WEB_SEARCH_SYSTEM_PROMPT


def test_assemble_web_search_user_turn_includes_current_date_when_given() -> None:
    turn = assemble_web_search_user_turn(
        [], [], "질문", patch_version="17.9", current_date="2026-08-20"
    )
    assert "[알려진 사실]" in turn
    assert "2026-08-20" in turn


def test_assemble_web_search_user_turn_omits_current_date_when_none() -> None:
    """current_date 기본값(None)이면 패치버전만 있던 기존 동작을 유지한다."""
    turn = assemble_web_search_user_turn([], [], "질문", patch_version="17.9")
    assert "[알려진 사실]" in turn
    assert "오늘 날짜는" not in turn


# ---- 스팟픽스: "현재 진행 중"이면서 이미 지난 종료일을 단정하는 모순 방지 ----------
# (PM 실사용 제보 — "현재 시즌 종료는?"에 오늘보다 3주 전인 날짜를 "현재
# 진행 중인 시즌이 그 날짜에 종료된다"고 자기모순적으로 답변. 오늘 날짜를
# [알려진 사실]에 추가한 것만으로는 이 논리적 모순까지는 못 걸러 규칙을
# 명시적으로 추가한다.)


def test_web_search_system_prompt_forbids_contradicting_past_end_date_as_ongoing() -> (
    None
):
    assert "모순" in WEB_SEARCH_SYSTEM_PROMPT
    assert "현재 진행 중" in WEB_SEARCH_SYSTEM_PROMPT


def test_web_search_few_shot_example_includes_current_date_fact() -> None:
    """few-shot 예시의 [알려진 사실]도 실제 assemble_web_search_user_turn()이
    만드는 형식(패치버전+오늘 날짜)과 일치해야 모델이 형식을 혼동하지 않는다."""
    from services.prompt_assembly import WEB_SEARCH_FEW_SHOT_EXAMPLE

    assert "오늘 날짜는" in WEB_SEARCH_FEW_SHOT_EXAMPLE


# ---- verify_web_citation: URL 없는 "[출처]" 라벨(E4/E15) ---------------------------


def test_verify_web_citation_flags_orphaned_citation_label_without_url() -> None:
    answer = "네, 핫픽스가 있었던 것으로 알려져 있습니다. [출처 1] [출처 2]"
    result = verify_web_citation(answer, [])
    assert result != answer
    assert UNVERIFIED_SOURCE_WARNING in result


def test_verify_web_citation_flags_single_orphaned_citation() -> None:
    answer = "다음 세트에서 역할군 밸런스 변화가 있을 예정입니다. [출처]"
    result = verify_web_citation(answer, [])
    assert UNVERIFIED_SOURCE_WARNING in result


def test_verify_web_citation_still_passes_well_formed_citation() -> None:
    """회귀 방지 — "[출처](URL)" 형식은 여전히 정상 통과해야 한다."""
    results = [WebSearchResult(title="t", url="https://example.com/a", content="c")]
    answer = "정보입니다. [출처](https://example.com/a)"
    assert verify_web_citation(answer, results) == answer


def test_verify_web_citation_still_passes_multiple_well_formed_citations() -> None:
    results = [
        WebSearchResult(title="t1", url="https://example.com/a", content="c1"),
        WebSearchResult(title="t2", url="https://example.com/b", content="c2"),
    ]
    answer = (
        "정보입니다. [출처 1](https://example.com/a) [출처 2](https://example.com/b)"
    )
    assert verify_web_citation(answer, results) == answer


# ---- generate_answer_stream: 무정보 답변의 인용 제거(B6) ---------------------------


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


def test_no_info_web_search_answer_drops_unused_citation(
    seeded_patch_session: Session,
) -> None:
    """B6(TEST-11 카테고리 B 발견) — "확인되지 않았습니다"류 무정보 답변에
    실제로는 근거로 쓰지 않은 출처가 그대로 붙어있던 문제. 답변 전체가
    무정보 판정이면 인용을 결정론적으로 제거한다."""

    def fake_stream_fn(system_prompt: str, user_message: str):
        yield (
            "신규 세트의 세부 정보는 확인되지 않았습니다. [출처](https://a.example/1) "
            "에서는 다른 세트 컨셉만 제공하고 있습니다. 신규 시너지 정보는 "
            "제공되지 않았습니다."
        )

    tokens = list(
        generate_answer_stream(
            seeded_patch_session,
            "11111111-1111-1111-1111-111111111111",
            "이번 세트 신규 시너지는 무엇인가요?",
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
    joined = " ".join(tokens)
    assert "[출처]" not in joined
    assert "https://a.example/1" not in joined
    assert "확인되지 않았습니다" in joined


def test_normal_web_search_answer_keeps_citation(
    seeded_patch_session: Session,
) -> None:
    """회귀 방지 — 실제로 정보를 답한 경우(무정보 답변이 아닌 경우)는 인용을
    그대로 유지해야 한다."""

    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "Set 18은 2026-08-12에 출시되었습니다. [출처](https://a.example/1)"

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
                WebSearchResult(title="t", url="https://a.example/1", content="c")
            ],
            stream_fn=fake_stream_fn,
        )
    )
    joined = " ".join(tokens)
    assert "https://a.example/1" in joined


def test_general_game_info_prompt_includes_known_patch_version(
    seeded_patch_session: Session,
) -> None:
    """generate_answer_stream이 실제로 patch_version을 [알려진 사실]로
    프롬프트에 전달하는지 배선 확인."""
    captured: dict[str, str] = {}

    def capturing_stream_fn(system_prompt: str, user_message: str):
        captured["user_message"] = user_message
        yield "답변입니다."

    list(
        generate_answer_stream(
            seeded_patch_session,
            "33333333-3333-3333-3333-333333333333",
            "다음 세트는 언제 나와?",
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_GENERAL_GAME_INFO,
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=lambda q: [],
            stream_fn=capturing_stream_fn,
        )
    )
    assert "[알려진 사실]" in captured["user_message"]
    assert "17.9" in captured["user_message"]


def test_general_game_info_prompt_includes_todays_date(
    seeded_patch_session: Session,
) -> None:
    """스팟픽스 배선 확인 — generate_answer_stream이 실제 오늘 날짜(UTC)를
    [알려진 사실]에 전달하는지."""
    captured: dict[str, str] = {}

    def capturing_stream_fn(system_prompt: str, user_message: str):
        captured["user_message"] = user_message
        yield "답변입니다."

    list(
        generate_answer_stream(
            seeded_patch_session,
            "44444444-4444-4444-4444-444444444444",
            "현재 시즌은 언제까지야?",
            embed_fn=_fail_if_called("embed_fn"),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: INTENT_GENERAL_GAME_INFO,
            search_fn=_fail_if_called("search_fn"),
            web_search_fn=lambda q: [],
            stream_fn=capturing_stream_fn,
        )
    )
    today = datetime.now(UTC).date().isoformat()
    assert today in captured["user_message"]
