import re
from collections.abc import Callable

from services.groq_client import call_groq_chat

INTENT_COMP_RECOMMENDATION = "comp_recommendation"
INTENT_ITEM_RECOMMENDATION = "item_recommendation"
INTENT_AUGMENT_RECOMMENDATION = "augment_recommendation"
INTENT_GENERAL_STRATEGY = "general_strategy"
# CHAT-17(PM 요청 2026-08-12): 시즌 일정·공식 이벤트 등 TFT 관련이지만 내부 RAG
# (comps/item_builds/augments)로는 답할 수 없는 "일반 게임 정보" 질문 전용
# 의도. 키워드로 사전 나열하기 어려운(패턴이 다양한) 잔여 카테고리라 1차
# 키워드 매칭(_KEYWORD_PATTERNS)에는 넣지 않고 2차 LLM 분류로만 도달한다 —
# CHAT-16의 오프토픽 2차 검증과 동일하게, 명확한 신호가 없을 때만 LLM에 맡기는
# 설계 원칙을 따른다.
INTENT_GENERAL_GAME_INFO = "general_game_info"

VALID_INTENTS = {
    INTENT_COMP_RECOMMENDATION,
    INTENT_ITEM_RECOMMENDATION,
    INTENT_AUGMENT_RECOMMENDATION,
    INTENT_GENERAL_STRATEGY,
    INTENT_GENERAL_GAME_INFO,
}

# glossary.md "챗봇 의도 분류 (4종, 고정)" 기준 1차 키워드 규칙 + CHAT-17
# general_game_info(2차 LLM 전용, 위 설명 참고)
_KEYWORD_PATTERNS: dict[str, re.Pattern[str]] = {
    INTENT_COMP_RECOMMENDATION: re.compile(r"조합|덱|편성"),
    INTENT_ITEM_RECOMMENDATION: re.compile(r"아이템|빌드|장비"),
    INTENT_AUGMENT_RECOMMENDATION: re.compile(r"증강체|오그먼트"),
    INTENT_GENERAL_STRATEGY: re.compile(r"메타|전략"),
}

# CHAT-21(PM 제보 2026-08-14, TEST-11 QA 중 발견): 게임 공식 한글 명칭
# "전략적 팀 전투"를 질문에 그대로 썼을 뿐인데("TFT(전략적 팀 전투)는 어떤
# 게임인가요?") "전략"이 general_strategy 키워드에 걸려, "이 게임이 뭐야" 같은
# 완전히 무관한 질문에까지 조합 추천 경로가 타 무관한 조합 통계가 답변에
# 섞여 나왔다. 1차 키워드 매칭에 넣기 전에 이 고정 구문만 제거해 오탐을
# 막는다(실제 LLM에 전달되는 질문 원문은 그대로, 매칭용 사본만 가공).
_GAME_NAME_PATTERN = re.compile(r"전략적\s*팀\s*전투")

_SYSTEM_PROMPT = (
    "다음은 TFT(전략적 팀 전투) 챗봇에 들어온 질문이다. "
    "아래 5개 카테고리 코드 중 정확히 하나만 다른 말 없이 출력해라.\n"
    "- comp_recommendation: 조합/덱 추천 질문\n"
    "- item_recommendation: 아이템/빌드 추천 질문\n"
    "- augment_recommendation: 증강체 추천 질문\n"
    "- general_game_info: 시즌 일정/출시 일정/공식 이벤트 등 게임 운영 정보 질문"
    "(내부 데이터베이스로는 답할 수 없는 일반 게임 정보)\n"
    "- general_strategy: 위 네 가지에 속하지 않는 일반 전략 질문"
)


def classify_by_keyword(query: str) -> str | None:
    """1차 분류: 정규식 키워드 매칭. 정확히 한 카테고리에만 매칭되면 그 카테고리를 반환하고,
    매칭이 없거나 여러 카테고리에 동시에 매칭되면(애매함) None을 반환해 2차 분류로 넘긴다."""
    keyword_query = _GAME_NAME_PATTERN.sub("", query)
    matched = [
        intent
        for intent, pattern in _KEYWORD_PATTERNS.items()
        if pattern.search(keyword_query)
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
