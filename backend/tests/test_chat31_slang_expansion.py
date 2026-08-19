"""CHAT-31 pytest: 증강체·전략 은어(슬랭)·줄임말 인식 확장이 실제 의도분류
경로까지 이어지는지 확인. TEST-11 H13("티에프티 오구먼트가 뭐임?")·H14
("롤체 하이롤 각 어캐 잡음?")가 검색 실패("확인되지 않았습니다")로 끝나던
문제 — CHAT-04(정규화)만 고쳐서는 부족하고, 정규화된 텍스트가 실제로
올바른 의도로 분류되는지까지 확인해야 한다."""

from __future__ import annotations

from services.chat_preprocessing import normalize_query
from services.intent_classification import (
    INTENT_AUGMENT_RECOMMENDATION,
    INTENT_GENERAL_RULES,
    INTENT_ITEM_RECOMMENDATION,
    classify_by_keyword,
    classify_by_llm,
)


def test_h13_normalized_query_matches_augment_keyword() -> None:
    """H13: "오구먼트"→"증강체" 정규화 후 1차 키워드 매칭까지 정상 동작하는지."""
    normalized = normalize_query("티에프티 오구먼트가 뭐임?")
    assert classify_by_keyword(normalized) == INTENT_AUGMENT_RECOMMENDATION


def test_h14_normalized_query_routes_to_general_rules_via_llm() -> None:
    """H14: "롤체"/"어캐" 정규화 후에도 1차 키워드는 안 걸려(하이롤은
    특정 카테고리 키워드가 아님) 2차 LLM으로 넘어가야 하고, 넓어진
    general_rules 카테고리 설명(일반 플레이 테크닉 포함)으로 올바르게
    분류되는지 확인."""
    normalized = normalize_query("롤체 하이롤 각 어캐 잡음?")
    assert classify_by_keyword(normalized) is None

    def mock_llm_call(system_prompt: str, user_message: str) -> str:
        assert "하이롤" in system_prompt  # general_rules 설명에 예시로 포함돼야 함
        return "general_rules"

    assert classify_by_llm(normalized, mock_llm_call) == INTENT_GENERAL_RULES


# 회귀 방지 — 기존 아이템 줄임말 인식 경로에 영향 없는지
def test_existing_item_slang_still_routes_to_item_recommendation() -> None:
    normalized = normalize_query("무대 아이템 좋아?")
    assert classify_by_keyword(normalized) == INTENT_ITEM_RECOMMENDATION
