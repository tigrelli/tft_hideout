import re
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from db.models import ChatLog
from services.chat_session import RECENT_TURNS_LIMIT, get_session_history
from services.groq_client import call_groq_chat

# 설계서 4.4.2: 사용자 입력을 시스템 프롬프트와 구조적으로 분리하는 델리미터(NFR-SEC-03).
USER_MESSAGE_DELIMITER_START = "[사용자 메시지]"
USER_MESSAGE_DELIMITER_END = "[/사용자 메시지]"

MAX_QUERY_LENGTH = 500

# 커뮤니티 은어/줄임말 사전(설계서 4.4.2 예시). 사전에 없는 표현은 실패 처리하지 않고
# 임베딩 유사도 검색이 흡수하므로, 여기서는 소수 항목만 유지하고 필요시 계속 추가한다.
# CHAT-14(PM 요청 2026-08-08): 아이템 줄임말 추가 — DATA-19/DATA-07과 같은 성격의
# 초안이라 문구(특히 "라바돈"/"구인수"/"쇼진"처럼 정식 명칭의 앞부분을 그대로 딴
# 줄임말)는 PM 검토 필요. 정식 명칭 자체가 이미 입력에 있을 때 이중 치환되지
# 않도록 normalize_query()에 방어 로직을 추가했다(아래 참고).
SLANG_DICTIONARY: dict[str, str] = {
    "아뎃": "애쉬",
    "보건": "보석 건틀릿",
    "무대": "무한의 대검",
    "구인수": "구인수의 격노검",
    "최속": "최후의 속삭임",
    "거학": "거인 학살자",
    "거결": "거인의 결의",
    "정손": "정의의 손길",
    "쇼진": "쇼진의 창",
    "라바돈": "라바돈의 죽음모자",
    "얼심": "얼어붙은 심장",
    "죽무": "죽음의 저항",
}

# TFT 도메인 신호 키워드(범위 밖 질문 판별용). CHAT-01의 의도별 키워드보다 넓게 잡아
# "일반 전략 질문"까지 포괄하되, 전혀 무관한 잡담만 걸러낸다(설계서 4.4.2 "범위 밖 질문 정책").
# CHAT-14(PM 제보 2026-08-08): "보석건틀릿 효과는?"처럼 아이템/챔피언 이름만 쓰고
# "아이템" 같은 카테고리 단어를 안 쓰는 질문이 전부 범위 밖으로 오분류되던 문제 —
# 구체적 아이템/챔피언 이름을 전부 나열할 수는 없어(패치마다 바뀌고 수백 개), 그런
# 질문에 흔히 같이 쓰이는 "효과/효능/스킬/설명" 등을 신호 키워드에 추가했다(TEST-00
# 시나리오 #6 "오늘 점심 뭐 먹지"는 이 키워드들도 없어 여전히 범위 밖으로 분류됨).
_TFT_DOMAIN_PATTERN = re.compile(
    r"조합|덱|편성|아이템|빌드|장비|증강체|오그먼트|메타|전략|챔피언|티어|패치|승률|픽률"
    r"|효과|효능|스킬|설명"
)

# CHAT-19(PM 제보 2026-08-14): "현재 패치버전은?"류 질문에 이미 알고 있는
# patches.is_current 값이 있는데도 1차 키워드 패턴(조합/아이템/증강체/메타)에
# "패치"가 없어 2차 LLM 의도분류로 넘어가고, general_game_info(CHAT-17, Tavily
# 웹검색 전용)로 오분류돼 무관한 웹검색 결과로 답하는 문제가 있었다. "몇 패치인지"를
# 묻는 질문만 좁게 잡는다 — "이번 패치에 뭐가 바뀌었어?" 같은 패치노트류 질문은
# 내부에 답할 데이터가 없어 이 패턴에 포함하지 않고 기존 general_game_info로
# 그대로 보낸다(패치노트 자체가 chatbot 근거 데이터에 없음).
_PATCH_VERSION_QUERY_PATTERN = re.compile(r"패치\s*버전|버전.*패치|몇\s*패치")


def is_patch_version_query(normalized_text: str) -> bool:
    """의도분류(CHAT-01)보다 먼저 걸러 이미 알고 있는 patch_version으로 결정론적으로
    즉답하기 위한 감지 함수(chat_stream.py 조기 반환에서 사용)."""
    return _PATCH_VERSION_QUERY_PATTERN.search(normalized_text) is not None


@dataclass
class PreprocessResult:
    normalized_text: str
    wrapped_text: str
    is_off_topic: bool
    needs_clarification: bool


def normalize_query(raw: str) -> str:
    """공백 정리 + 은어 사전 치환(설계서 4.4.2 "질문 정규화").

    "라바돈"->"라바돈의 죽음모자"처럼 줄임말이 정식 명칭의 앞부분과 그대로
    겹치는 경우(CHAT-14 아이템 줄임말 추가로 새로 생긴 케이스), 사용자가 이미
    정식 명칭을 입력했다면 치환을 건너뛰어 "라바돈의 죽음모자의 죽음모자"처럼
    중복 확장되는 것을 막는다."""
    text = re.sub(r"\s+", " ", raw.strip())
    for slang, full_name in SLANG_DICTIONARY.items():
        if full_name not in text:
            text = text.replace(slang, full_name)
    return text


def wrap_user_message(text: str) -> str:
    """사용자 입력을 델리미터로 감싸 시스템 프롬프트와 구조적으로 분리한다(NFR-SEC-03).
    '지시를 무시하라'는 취지의 문구도 차단하지 않고 데이터로만 취급해 그대로 감싼다."""
    return f"{USER_MESSAGE_DELIMITER_START}\n{text}\n{USER_MESSAGE_DELIMITER_END}"


def is_off_topic(normalized_text: str) -> bool:
    """1차 키워드 판별. TFT 도메인 키워드가 전혀 없으면 범위 밖 '후보'로 간주한다
    (최종 확정 아님 — CHAT-01 의도분류와 동일하게, 이 후보 판정만 2차 LLM 검증으로
    넘어간다. 키워드가 매칭되면 이미 on-topic이 확실하므로 LLM 호출 없이 끝난다)."""
    return _TFT_DOMAIN_PATTERN.search(normalized_text) is None


# CHAT-16(PM 요청 2026-08-12): is_off_topic()의 키워드 정규식이 미스하면 곧장
# 범위 밖으로 거부해, "시즌 종료는 언제?"처럼 TFT 관련이지만 조합/아이템/메타 같은
# 키워드가 없는 질문이 오분류되는 문제가 있었다. CHAT-01 의도분류의
# "1차 키워드 → 애매하면 2차 Groq LLM" 패턴을 그대로 재사용해, 키워드가 미스한
# 경우에만(chat_stream.py에서 호출 여부를 결정) 이 2차 검증을 태운다.
_OFF_TOPIC_CONFIRM_SYSTEM_PROMPT = (
    "다음은 TFT(전략적 팀 전투) 챗봇에 들어온 질문이다. 이 질문이 TFT 게임과 "
    "조금이라도 관련 있으면(패치·시즌·업데이트 일정·이벤트·챔피언·아이템·조합·"
    "증강체·전략·게임 시스템 등) 'on_topic'을, 게임과 전혀 무관한 잡담이나 다른 "
    "게임 질문이면 'off_topic'을 다른 말 없이 정확히 하나만 출력해라."
)


def confirm_off_topic(
    normalized_text: str, llm_call: Callable[[str, str], str]
) -> bool:
    """2차 분류: 1차 키워드가 범위 밖 후보로 판정한 질문만 Groq LLM에 재확인시킨다.
    호출 실패나 유효하지 않은 응답은 on-topic으로 통과시킨다(fail-open, PM 결정
    2026-08-12 — CHAT-01의 classify_by_llm과 동일하게 무료 티어 오류로 정상 질문이
    잘못 거부되는 것보다 통과시키는 쪽이 안전하다는 판단)."""
    try:
        raw = llm_call(_OFF_TOPIC_CONFIRM_SYSTEM_PROMPT, normalized_text).strip()
    except Exception:  # noqa: BLE001 — Groq 무료 티어 오류/한도 초과 시 on-topic 통과
        return False
    return raw == "off_topic"


def is_off_topic_for_query(normalized_text: str) -> bool:
    """운영 환경용 진입점. 실제 Groq 호출을 사용한다."""
    return confirm_off_topic(normalized_text, call_groq_chat)


def preprocess_input(raw: str) -> PreprocessResult:
    normalized = normalize_query(raw)
    if not normalized:
        return PreprocessResult(
            normalized_text=normalized,
            wrapped_text="",
            is_off_topic=False,
            needs_clarification=True,
        )

    truncated = normalized[:MAX_QUERY_LENGTH]
    return PreprocessResult(
        normalized_text=truncated,
        wrapped_text=wrap_user_message(truncated),
        is_off_topic=is_off_topic(truncated),
        needs_clarification=False,
    )


def get_conversation_history(db: Session, session_id: str) -> list[ChatLog]:
    """세션별 최근 RECENT_TURNS_LIMIT턴만 프롬프트 컨텍스트에 포함한다(설계서 4.4.1/4.4.2).
    API-10과 동일한 상수·조회 로직을 재사용해 두 곳의 '최근 3턴' 기준이 어긋나지 않게 한다."""
    return get_session_history(db, session_id, limit=RECENT_TURNS_LIMIT)
