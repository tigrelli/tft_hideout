import re
from collections.abc import Callable

from services.groq_client import call_groq_chat

INTENT_COMP_RECOMMENDATION = "comp_recommendation"
INTENT_ITEM_RECOMMENDATION = "item_recommendation"
INTENT_AUGMENT_RECOMMENDATION = "augment_recommendation"
INTENT_GENERAL_STRATEGY = "general_strategy"

VALID_INTENTS = {
    INTENT_COMP_RECOMMENDATION,
    INTENT_ITEM_RECOMMENDATION,
    INTENT_AUGMENT_RECOMMENDATION,
    INTENT_GENERAL_STRATEGY,
}

# glossary.md "챗봇 의도 분류 (4종, 고정)" 기준 1차 키워드 규칙
_KEYWORD_PATTERNS: dict[str, re.Pattern[str]] = {
    INTENT_COMP_RECOMMENDATION: re.compile(r"조합|덱|편성"),
    INTENT_ITEM_RECOMMENDATION: re.compile(r"아이템|빌드|장비"),
    INTENT_AUGMENT_RECOMMENDATION: re.compile(r"증강체|오그먼트"),
    INTENT_GENERAL_STRATEGY: re.compile(r"메타|전략"),
}

_SYSTEM_PROMPT = (
    "다음은 TFT(전략적 팀 전투) 챗봇에 들어온 질문이다. "
    "아래 4개 카테고리 코드 중 정확히 하나만 다른 말 없이 출력해라.\n"
    "- comp_recommendation: 조합/덱 추천 질문\n"
    "- item_recommendation: 아이템/빌드 추천 질문\n"
    "- augment_recommendation: 증강체 추천 질문\n"
    "- general_strategy: 위 세 가지에 속하지 않는 일반 전략 질문"
)


def classify_by_keyword(query: str) -> str | None:
    """1차 분류: 정규식 키워드 매칭. 정확히 한 카테고리에만 매칭되면 그 카테고리를 반환하고,
    매칭이 없거나 여러 카테고리에 동시에 매칭되면(애매함) None을 반환해 2차 분류로 넘긴다."""
    matched = [
        intent for intent, pattern in _KEYWORD_PATTERNS.items() if pattern.search(query)
    ]
    return matched[0] if len(matched) == 1 else None


def classify_by_llm(query: str, llm_call: Callable[[str, str], str]) -> str:
    """2차 분류: 키워드로 애매했던 질문만 Groq LLM에 위임한다.
    llm_call은 (system_prompt, user_message) -> 응답 텍스트를 반환하는 함수(테스트에서는 mock 주입).
    호출 실패나 유효하지 않은 응답은 general_strategy로 폴백한다(무료 티어 한도/오류 대비 정책)."""
    try:
        raw = llm_call(_SYSTEM_PROMPT, query).strip()
    except Exception:  # noqa: BLE001 — Groq 무료 티어 오류/한도 초과 시 폴백(policies.md)
        return INTENT_GENERAL_STRATEGY
    return raw if raw in VALID_INTENTS else INTENT_GENERAL_STRATEGY


def classify_intent(query: str, llm_call: Callable[[str, str], str]) -> str:
    return classify_by_keyword(query) or classify_by_llm(query, llm_call)


def classify_intent_for_query(query: str) -> str:
    """운영 환경용 진입점. 2차 분류가 필요할 때 실제 Groq 호출을 사용한다."""
    return classify_intent(query, call_groq_chat)
