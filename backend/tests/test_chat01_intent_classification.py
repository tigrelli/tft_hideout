import pytest

from services.intent_classification import (
    INTENT_AUGMENT_RECOMMENDATION,
    INTENT_COMP_RECOMMENDATION,
    INTENT_GENERAL_STRATEGY,
    INTENT_ITEM_RECOMMENDATION,
    classify_by_keyword,
    classify_by_llm,
    classify_intent,
)


def _unused_llm_call(system_prompt: str, query: str) -> str:
    raise AssertionError("키워드로 명확히 분류되는 케이스는 LLM을 호출하면 안 된다")


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("이번 패치 최강 조합 뭐야?", INTENT_COMP_RECOMMENDATION),
        ("8덱 편성 추천해줘", INTENT_COMP_RECOMMENDATION),
        ("자르반 아이템 뭐 껴야해?", INTENT_ITEM_RECOMMENDATION),
        ("이 챔피언 빌드 추천", INTENT_ITEM_RECOMMENDATION),
        ("이번에 어떤 증강체가 좋아?", INTENT_AUGMENT_RECOMMENDATION),
        ("오그먼트 티어 알려줘", INTENT_AUGMENT_RECOMMENDATION),
        ("지금 메타는 어떤 느낌이야?", INTENT_GENERAL_STRATEGY),
        ("초반 전략 어떻게 짜야해?", INTENT_GENERAL_STRATEGY),
    ],
)
def test_classify_by_keyword_matches_each_of_4_intents(
    query: str, expected: str
) -> None:
    assert classify_by_keyword(query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("이번 패치 최강 조합 뭐야?", INTENT_COMP_RECOMMENDATION),
        ("자르반 아이템 뭐 껴야해?", INTENT_ITEM_RECOMMENDATION),
    ],
)
def test_classify_intent_uses_keyword_match_without_calling_llm(
    query: str, expected: str
) -> None:
    assert classify_intent(query, _unused_llm_call) == expected


def test_classify_by_keyword_returns_none_when_ambiguous_or_no_match() -> None:
    assert classify_by_keyword("안녕하세요") is None
    assert classify_by_keyword("이 조합에 넣을 아이템 뭐가 좋아?") is None


def test_classify_by_keyword_returns_none_for_champion_cost_query() -> None:
    # "챔피언"을 키워드로 추가하면 "이 챔피언 빌드 추천"(item_recommendation)
    # 같은 기존 케이스와 충돌해(둘 다 매칭 -> 모호) 오히려 분류 품질이
    # 떨어짐(2026-08-07 확인) — "3코스트 챔피언은?" 류는 일부러 키워드
    # 매칭 없이 2차 LLM 분류로 넘긴다(general_strategy "위 세 가지에 속하지
    # 않는 일반 전략 질문" 설명에 맞게 LLM이 판단).
    assert classify_by_keyword("3코스트 챔피언은?") is None


def test_classify_by_llm_returns_mock_intent_for_ambiguous_query() -> None:
    def mock_llm_call(system_prompt: str, query: str) -> str:
        assert query == "이 조합에 넣을 아이템 뭐가 좋아?"
        return INTENT_ITEM_RECOMMENDATION

    result = classify_by_llm("이 조합에 넣을 아이템 뭐가 좋아?", mock_llm_call)
    assert result == INTENT_ITEM_RECOMMENDATION


def test_classify_by_llm_falls_back_to_general_strategy_on_invalid_response() -> None:
    def mock_llm_call(system_prompt: str, query: str) -> str:
        return "not_a_real_intent"

    assert classify_by_llm("애매한 질문", mock_llm_call) == INTENT_GENERAL_STRATEGY


def test_classify_by_llm_falls_back_to_general_strategy_on_llm_failure() -> None:
    def failing_llm_call(system_prompt: str, query: str) -> str:
        raise RuntimeError("Groq API 무료 티어 한도 초과")

    assert classify_by_llm("애매한 질문", failing_llm_call) == INTENT_GENERAL_STRATEGY


def test_classify_intent_routes_ambiguous_query_to_llm() -> None:
    def mock_llm_call(system_prompt: str, query: str) -> str:
        return INTENT_COMP_RECOMMENDATION

    assert classify_intent("안녕하세요", mock_llm_call) == INTENT_COMP_RECOMMENDATION
