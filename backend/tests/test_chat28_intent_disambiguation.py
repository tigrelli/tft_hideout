"""CHAT-28 pytest: 단일 키워드 매칭만으로 곧장 확정되던 의도 과잉분류
재발 방지(A13/B5/B11/C11) + 패치버전 조기반환 오탐 수정(H16). G9는 이미
CHAT-26(chatbot_meta)이 해결한 경로라 여기서는 그대로 유지되는지 회귀만
확인한다."""

from __future__ import annotations

import pytest

from services.chat_preprocessing import (
    detect_chatbot_meta_topic,
    is_patch_version_query,
)
from services.intent_classification import (
    INTENT_AUGMENT_RECOMMENDATION,
    INTENT_COMP_RECOMMENDATION,
    INTENT_GENERAL_RULES,
    classify_by_keyword,
    classify_by_llm,
)

# ---- A13/B5/B11/C11: 메커니즘 질문 신호로 1차 확정을 피하는지 -----------------------


@pytest.mark.parametrize(
    "query",
    [
        "증강(오그먼트)은 언제, 몇 개 선택하나요?",  # A13
        "시너지 단계별(2/4/6명 등) 효과 차이를 알려주세요.",  # B5(원래도 키워드 미매칭)
        "이 챔피언들로 조합을 짜면 어떤 시너지가 나오나요?",  # B11
        "이 챔피언에게 어울리지 않는 아이템 조합이 있나요?",  # C11(원래도 이중매칭)
    ],
)
def test_classify_by_keyword_defers_mechanism_questions_to_llm(query: str) -> None:
    assert classify_by_keyword(query) is None


def test_classify_by_llm_routes_mechanism_question_to_general_rules() -> None:
    def mock_llm_call(system_prompt: str, user_message: str) -> str:
        return "general_rules"

    assert (
        classify_by_llm("증강(오그먼트)은 언제, 몇 개 선택하나요?", mock_llm_call)
        == INTENT_GENERAL_RULES
    )
    assert (
        classify_by_llm(
            "이 챔피언들로 조합을 짜면 어떤 시너지가 나오나요?", mock_llm_call
        )
        == INTENT_GENERAL_RULES
    )


# 회귀 방지: 이 신호가 정상적인 "추천해달라" 요청까지 2차로 밀어내지 않는지
# 확인(latency/Groq 호출 낭비 방지 — 기존 test_chat01의 키워드 확정 케이스와
# 동일한 문항들로 재확인).
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("이번에 어떤 증강체가 좋아?", INTENT_AUGMENT_RECOMMENDATION),
        ("8덱 편성 추천해줘", INTENT_COMP_RECOMMENDATION),
    ],
)
def test_classify_by_keyword_still_confirms_normal_recommendation_requests(
    query: str, expected: str
) -> None:
    assert classify_by_keyword(query) == expected


# ---- H16: "어떤"이 "패치"가 아니라 다른 명사를 수식하는 미래 예측 질문 -------------


def test_is_patch_version_query_does_not_flag_future_balance_prediction() -> None:
    """TEST-11 H16(2026-08-19 발견) — "어떤"이 "챔피언"을 수식할 뿐인데 신호
    단어로 오매칭돼 CHAT-19 조기반환이 이 질문을 가로채고 있었다."""
    assert (
        is_patch_version_query("다음 패치에서 어떤 챔피언이 상향될 것 같아?") is False
    )
    assert is_patch_version_query("다음 패치에서 어떤 챔피언이 하향될까요?") is False


# 회귀 방지: 순수 버전 질의는 여전히 True를 반환해야 한다(순서를 바꿨어도
# 결과가 같은지 재확인, test_chat04의 파라미터와 동일한 대표 케이스).
@pytest.mark.parametrize(
    "query",
    ["현재 패치버전은?", "어떤 패치야?", "무슨 패치야?", "패치가 몇이야?"],
)
def test_is_patch_version_query_still_flags_real_version_questions(
    query: str,
) -> None:
    assert is_patch_version_query(query) is True


# ---- G9: CHAT-26(chatbot_meta)이 이미 해결한 경로 — 회귀만 확인 -------------------


def test_g9_region_question_already_routed_by_chatbot_meta() -> None:
    """G9("한국 서버 기준으로 답해주는 거야, 아니면 글로벌 기준이야?")는
    CHAT-26의 detect_chatbot_meta_topic()이 is_off_topic/의도분류보다도 먼저
    가로채 "region" 버킷으로 정답 처리한다 — CHAT-28에서 별도 수정이 필요
    없음을 확인하는 회귀 테스트(chat_stream.py의 조기반환 순서상 이 함수가
    intent_classification보다 먼저 호출됨)."""
    assert (
        detect_chatbot_meta_topic(
            "한국 서버 기준으로 답해주는 거야, 아니면 글로벌 기준이야?"
        )
        == "region"
    )
