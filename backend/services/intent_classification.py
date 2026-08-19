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
# CHAT-27(PM 결정 2026-08-19, TEST-11 카테고리 B/C/D/E에서 발견한 "패치와 무관한
# 고정 게임 규칙" 커버리지 공백 대응): 아이템 조합 방식·성급별 스킬 강화 여부·
# 랭크 티어 구조 등 세트·패치가 바뀌어도 달라지지 않는 게임 시스템 규칙 질문
# 전용 의도. 내부 RAG(comps/items/augments)에는 이런 설명 문서 자체가 없어
# 검색해도 항상 빈 결과이므로, RAG 문서를 새로 쓰는 대신 검색을 생략하고 LLM의
# 일반 TFT 지식으로 직접 답하게 한다(PM 결정 — "새 의도 신설" 방식 채택,
# RAG 문서 신설 대비 문서 작성 부담 없이 즉시 넓은 영역을 커버). general_game_info
# (시즌 일정 등 시의성 있는 정보, 웹검색 근거 필요)와는 근본적으로 다른 대상이라
# 별도 의도로 분리 — general_rules는 "패치 불변" 전제이므로 검색·웹검색 모두
# 생략하고, 특정 세트/패치에서만 유효한 내용은 프롬프트 규칙으로 답변을
# 거부하도록 강제한다(chat_stream.py의 _generate_general_rules_answer 참고).
INTENT_GENERAL_RULES = "general_rules"

VALID_INTENTS = {
    INTENT_COMP_RECOMMENDATION,
    INTENT_ITEM_RECOMMENDATION,
    INTENT_AUGMENT_RECOMMENDATION,
    INTENT_GENERAL_STRATEGY,
    INTENT_GENERAL_GAME_INFO,
    INTENT_GENERAL_RULES,
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

# CHAT-28(PM 결정 2026-08-19, TEST-11 A13/B11에서 반복 확인된 재발 패턴):
# 단일 카테고리 키워드만 있어도 곧장 그 카테고리를 확정해버리면, 실제로는
# "추천해달라"는 요청이 아니라 게임 메커니즘 자체를 설명해달라는 질문도
# 같은 카테고리로 오분류된다 — A13("증강은 언제, 몇 개 선택하나요?"→
# augment_recommendation 오분류로 무관한 특정 증강체 설명이 나옴), B11
# ("이 챔피언들로 조합을 짜면 어떤 시너지가 나오나요?"→comp_recommendation
# 오분류로 무관한 기존 조합 통계가 섞임)가 실제 사례. 이런 질문에 흔히
# 나타나는 표현(몇 개/몇 명을 "언제" 선택하는지 묻는 절차 질문, "~하면 어떤
# ~가 나오나요" 식의 조건부 결과 질문, "단계별" 효과 차이, "안 어울리는"
# 궁합 질문)이 있으면 카테고리 키워드가 매칭돼도 곧장 확정하지 않고 2차 LLM
# 분류로 넘긴다 — CHAT-27이 만든 general_rules 카테고리가 2차 분류 선택지에
# 있어 이런 메커니즘 질문을 이제 올바르게 처리할 수 있다(이 신호는 "확정
# 하지 말라"는 방어일 뿐, 최종 분류는 여전히 2차 LLM이 판단한다). TEST-11
# 157문항 전체를 대조한 결과 이 신호에 걸리는 건 A13/B5/B11/C11 4문항뿐이라
# (`test_chat28_intent_disambiguation.py` 참고) 정상적인 추천 요청 오탐 위험은
# 낮다고 판단했다.
_MECHANISM_QUESTION_SIGNAL = re.compile(
    r"언제,?\s*몇\s*(개|명)|어떤\s*.{0,10}(나오나요|나올까요)|단계별|단계마다"
    r"|어울리지\s*않는|안\s*어울리는"
)

_SYSTEM_PROMPT = (
    "다음은 TFT(전략적 팀 전투) 챗봇에 들어온 질문이다. "
    "아래 6개 카테고리 코드 중 정확히 하나만 다른 말 없이 출력해라.\n"
    "- comp_recommendation: 조합/덱 추천 질문\n"
    "- item_recommendation: 아이템/빌드 추천 질문\n"
    "- augment_recommendation: 증강체 추천 질문\n"
    "- general_game_info: 시즌 일정/출시 일정/공식 이벤트 등 게임 운영 정보 질문"
    "(내부 데이터베이스로는 답할 수 없는 일반 게임 정보)\n"
    "- general_rules: 패치·세트가 바뀌어도 달라지지 않는 고정 게임 시스템 규칙"
    "/메커니즘 질문(예: 아이템은 어떻게 조합하는지, 성급이 오르면 스킬도 강해지는지,"
    " 랭크 티어는 몇 단계인지, 매칭은 어떤 기준인지). 특정 챔피언/아이템/조합을"
    " 추천해달라는 질문이 아니라 게임 시스템 자체가 어떻게 동작하는지 묻는"
    " 질문이면 이 카테고리를 우선 선택하라. 단, '이번 패치에서 뭐가 바뀌었는지'"
    " '다음 세트가 언제 나오는지'처럼 특정 시점에만 유효한 시의성 있는 내용을"
    " 묻는 질문은 general_game_info로 분류하라(general_rules가 아니다).\n"
    "- general_strategy: 위 다섯 가지에 속하지 않는 일반 전략 질문"
)


def classify_by_keyword(query: str) -> str | None:
    """1차 분류: 정규식 키워드 매칭. 정확히 한 카테고리에만 매칭되면 그 카테고리를 반환하고,
    매칭이 없거나 여러 카테고리에 동시에 매칭되면(애매함) None을 반환해 2차 분류로 넘긴다.
    단일 매칭이어도 메커니즘 질문 신호(CHAT-28, _MECHANISM_QUESTION_SIGNAL)가 있으면
    "추천 요청"이 아닐 가능성이 높아 확정하지 않고 마찬가지로 2차 분류로 넘긴다."""
    keyword_query = _GAME_NAME_PATTERN.sub("", query)
    matched = [
        intent
        for intent, pattern in _KEYWORD_PATTERNS.items()
        if pattern.search(keyword_query)
    ]
    if len(matched) != 1:
        return None
    if _MECHANISM_QUESTION_SIGNAL.search(query):
        return None
    return matched[0]


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
