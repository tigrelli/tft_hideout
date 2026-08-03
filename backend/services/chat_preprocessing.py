import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from db.models import ChatLog
from services.chat_session import RECENT_TURNS_LIMIT, get_session_history

# 설계서 4.4.2: 사용자 입력을 시스템 프롬프트와 구조적으로 분리하는 델리미터(NFR-SEC-03).
USER_MESSAGE_DELIMITER_START = "[사용자 메시지]"
USER_MESSAGE_DELIMITER_END = "[/사용자 메시지]"

MAX_QUERY_LENGTH = 500

# 커뮤니티 은어/줄임말 사전(설계서 4.4.2 예시). 사전에 없는 표현은 실패 처리하지 않고
# 임베딩 유사도 검색이 흡수하므로, 여기서는 소수 항목만 유지하고 필요시 계속 추가한다.
SLANG_DICTIONARY: dict[str, str] = {
    "아뎃": "애쉬",
}

# TFT 도메인 신호 키워드(범위 밖 질문 판별용). CHAT-01의 의도별 키워드보다 넓게 잡아
# "일반 전략 질문"까지 포괄하되, 전혀 무관한 잡담만 걸러낸다(설계서 4.4.2 "범위 밖 질문 정책").
_TFT_DOMAIN_PATTERN = re.compile(
    r"조합|덱|편성|아이템|빌드|장비|증강체|오그먼트|메타|전략|챔피언|티어|패치|승률|픽률"
)


@dataclass
class PreprocessResult:
    normalized_text: str
    wrapped_text: str
    is_off_topic: bool
    needs_clarification: bool


def normalize_query(raw: str) -> str:
    """공백 정리 + 은어 사전 치환(설계서 4.4.2 "질문 정규화")."""
    text = re.sub(r"\s+", " ", raw.strip())
    for slang, full_name in SLANG_DICTIONARY.items():
        text = text.replace(slang, full_name)
    return text


def wrap_user_message(text: str) -> str:
    """사용자 입력을 델리미터로 감싸 시스템 프롬프트와 구조적으로 분리한다(NFR-SEC-03).
    '지시를 무시하라'는 취지의 문구도 차단하지 않고 데이터로만 취급해 그대로 감싼다."""
    return f"{USER_MESSAGE_DELIMITER_START}\n{text}\n{USER_MESSAGE_DELIMITER_END}"


def is_off_topic(normalized_text: str) -> bool:
    """TFT 도메인 키워드가 전혀 없으면 범위 밖 질문으로 간주한다(제품 정책 기본값, 조정 가능)."""
    return _TFT_DOMAIN_PATTERN.search(normalized_text) is None


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
