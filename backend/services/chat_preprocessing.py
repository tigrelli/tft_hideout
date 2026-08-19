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
# CHAT-25(TEST-11 카테고리 F 실행 중 발견, PM 제보 2026-08-17): "경제(이코노미)
# 운영은 어떻게 하는 게 좋나요?", "스노우볼링과 그리핑의 차이는 무엇인가요?"처럼
# 명백한 TFT 전략 질문이 위 목록에 없어 2차 LLM 검증으로 넘어갔고, 그마저도
# 니치 은어를 잡담으로 오판해 범위 밖으로 거절되던 문제 — 경제 운영·로우롤 전략
# 관련 커뮤니티 용어를 추가했다.
_TFT_DOMAIN_PATTERN = re.compile(
    r"조합|덱|편성|아이템|빌드|장비|증강체|오그먼트|메타|전략|챔피언|티어|패치|승률|픽률"
    r"|효과|효능|스킬|설명|경제|이코노미|스노우볼링|그리핑"
)

# CHAT-19(PM 제보 2026-08-14): "현재 패치버전은?"류 질문에 이미 알고 있는
# patches.is_current 값이 있는데도 1차 키워드 패턴(조합/아이템/증강체/메타)에
# "패치"가 없어 2차 LLM 의도분류로 넘어가고, general_game_info(CHAT-17, Tavily
# 웹검색 전용)로 오분류돼 무관한 웹검색 결과로 답하는 문제가 있었다. "몇 패치인지"를
# 묻는 질문만 좁게 잡는다 — "이번 패치에 뭐가 바뀌었어?" 같은 패치노트류 질문은
# 내부에 답할 데이터가 없어 이 패턴에 포함하지 않고 기존 general_game_info로
# 그대로 보낸다(패치노트 자체가 chatbot 근거 데이터에 없음).
#
# 회귀 수정(PM 재제보 2026-08-14): 최초 구현은 "패치버전"/"버전+패치"/"몇+패치"만
# 잡는 좁은 정규식이었는데, "현재패치는?"처럼 "버전"/"몇" 같은 명시적 신호 단어가
# 아예 없는 최소 표현은 여전히 걸러지지 않고 그대로 오분류됨(프로덕션에서 실제로
# 재현). 명시적 신호 단어(버전/몇/무슨/어떤)를 우선 확인하고, 신호 단어가 없으면
# 패치노트류 배제 단어(바뀌/변경 등)부터 확인한 뒤, 그래도 남는 "패치"만 있는
# 최소 질문 형태("패치는?", "패치가 뭐야?" 등)를 별도 패턴으로 흡수한다.
_PATCH_VERSION_SIGNAL_WORDS = ("버전", "몇", "무슨", "어떤")
# CHAT-28(TEST-11 H16에서 발견, 2026-08-19): "다음 패치에서 어떤 챔피언이
# 상향될 것 같아?"처럼 "어떤"이 "패치"가 아니라 "챔피언"을 수식하는 미래 예측
# 질문도, 신호 단어("어떤")가 텍스트 어디에 있는지 위치를 안 가리고 매칭돼
# 버전 질의로 오분류돼 CHAT-19 조기반환이 엉뚱하게 가로챈다(패치버전 답만
# 반복하고 실제 질문엔 답 안 함). 상향/하향/미래예측 표현이 있으면 신호
# 단어가 매칭되더라도 배제하도록 배제 단어 목록에 추가하고, 배제 확인을
# 신호 단어 확인보다 먼저 하도록 순서를 바꿨다(기존엔 신호 단어가 매칭되면
# 배제 단어를 아예 확인하지 않고 곧장 True를 반환해 이 조합을 놓쳤다).
_PATCH_NOTE_EXCLUSION_WORDS = (
    "바뀌",
    "바뀐",
    "변경",
    "달라진",
    "패치노트",
    "너프",
    "버프",
    "추가된",
    "상향",
    "하향",
)
_BARE_PATCH_QUERY_PATTERN = re.compile(
    r"^(현재|지금|이번)?\s*패치\s*(는|가|이|을|를)?\s*(뭐(야|예요|지|임)?|무엇(인가요|이야)?)?$"
)


def is_patch_version_query(normalized_text: str) -> bool:
    """의도분류(CHAT-01)보다 먼저 걸러 이미 알고 있는 patch_version으로 결정론적으로
    즉답하기 위한 감지 함수(chat_stream.py 조기 반환에서 사용)."""
    if "패치" not in normalized_text:
        return False
    if any(word in normalized_text for word in _PATCH_NOTE_EXCLUSION_WORDS):
        return False
    if any(word in normalized_text for word in _PATCH_VERSION_SIGNAL_WORDS):
        return True
    stripped = normalized_text.rstrip("?!？! ").strip()
    return _BARE_PATCH_QUERY_PATTERN.fullmatch(stripped) is not None


# CHAT-26(PM 요청, TEST-11 카테고리 G에서 발견 2026-08-18 — 15문항 중 11건이
# 정형 거절로 회피, 1건(G9)은 무관한 웹검색 결과로 오답): 챗봇 자기 자신에
# 대한 메타 질문("너는 뭘 할 수 있어?", "라이엇 소속이야?" 등)은 TFT 게임
# 콘텐츠 키워드(_TFT_DOMAIN_PATTERN)가 거의 없어 is_off_topic() 1차 판정에서
# 범위 밖 후보로 걸리고, 2차 LLM 검증도 대부분 "무관한 잡담"으로 오판한다.
# is_off_topic() 검사보다 먼저 결정론적으로 감지해(CHAT-19 패치버전 조기반환과
# 동일한 설계) 검색·LLM 호출 없이 고정 FAQ 답변으로 즉답한다. H10(TEST-11
# 카테고리 H, QA 중 자체 발견 2026-08-19 — "도움이 하나도 안되네" 같은 메타
# 피드백/불만도 날씨 질문과 동일한 정형 거절로 응대되던 문제)도 같은 계열로
# feedback_complaint 버킷에 포함한다.
#
# 각 정규식은 "주제 키워드 + 챗봇 자신에게 묻는 문형(~해줄 수 있어/~이야?/
# ~하나요? 등)"을 함께 요구해, 같은 단어가 일반 TFT 질문에 우연히 등장해도
# (예: "이 조합 실시간 승률 어때?"는 순수 통계 요청이라 오분류 위험이 있어
# capability-asking 접미사를 필수로 둠, "이 조합 안전해?"처럼 "안전"만으로는
# 매칭 안 되게 계정/닉네임 문맥을 필수로 둠) 오탐을 줄인다. 그럼에도 완벽한
# 구분은 불가능해 실측(TEST-11 재질의)으로 계속 검증한다.
_CHATBOT_META_TOPICS: list[tuple[str, re.Pattern[str]]] = [
    (
        "identity",
        re.compile(
            r"라이엇\s*(게임즈)?\s*소속|공식\s*(챗봇|서비스)(이야|인가요|야)?|서드파티"
        ),
    ),
    (
        "privacy",
        re.compile(r"(계정\s*정보|닉네임)[^.?!]{0,10}(안전|괜찮)|개인정보"),
    ),
    (
        "memory",
        re.compile(r"기억해|기억하(나요|니)|계속\s*기억|맥락[^.?!]{0,5}유지"),
    ),
    (
        "source",
        re.compile(r"정보\s*출처|출처는\s*어디|어디서\s*(가져|얻)"),
    ),
    (
        "feedback_report",
        re.compile(r"신고|(틀렸을\s*때|오답)[^.?!]{0,10}(고칠|수정)"),
    ),
    (
        "region",
        re.compile(r"한국\s*서버[^.?!]{0,15}(글로벌|전세계)|글로벌\s*기준"),
    ),
    (
        "voice",
        re.compile(r"음성으로|음성\s*질문"),
    ),
    (
        "image",
        re.compile(r"스크린샷|이미지를?\s*(보여|첨부|올리)"),
    ),
    (
        "language",
        re.compile(r"영어로도?\s*(답|받)|다른\s*언어로|다국어"),
    ),
    (
        "realtime_stats",
        re.compile(r"(최신|실시간)\s*(승률|픽률)[^.?!]{0,10}(알려줄\s*수|가능)"),
    ),
    (
        "realtime_patch",
        re.compile(r"실시간[^.?!]{0,10}(패치|정보)|오늘\s*날짜\s*기준"),
    ),
    (
        "match_analysis",
        re.compile(r"(내|제)\s*(최근\s*)?전적[^.?!]{0,10}(분석|봐)"),
    ),
    (
        "other_game",
        re.compile(r"다른\s*게임[^.?!]{0,15}(답|가능)"),
    ),
    (
        "feedback_complaint",
        re.compile(r"도움이\s*(하나도\s*)?안\s*되|쓸모없|별로(다|네)|실망"),
    ),
    (
        "capability",
        re.compile(
            r"(너는|챗봇은|당신은)[^.?!]{0,10}(뭘|어떤|무엇)[^.?!]{0,10}(도와|할\s*수)"
        ),
    ),
]

CHATBOT_META_ANSWERS: dict[str, str] = {
    "identity": "저는 라이엇게임즈 공식 서비스가 아니라, 개인이 취미로 만든 비상업적 TFT 정보 챗봇이에요.",
    "privacy": (
        "별도 로그인 없이 이용하실 수 있고, 대화를 구분하는 데 쓰는 session_id는 "
        "회원 식별 정보가 아니에요. 다만 닉네임이나 계정 정보 같은 개인정보는 "
        "굳이 입력하지 않으시는 걸 권해드려요."
    ),
    "memory": (
        "네, 같은 대화(세션) 안에서는 최근 3턴 정도의 맥락을 기억해서 답변에 "
        "반영해요. 다만 대화창을 새로고침하거나 나가면 이전 대화는 기억하지 못해요."
    ),
    "source": (
        "라이엇게임즈 공식 데이터, op.gg 메타 통계, TFT 커뮤니티 자료 등을 참고해 "
        "답변을 준비해요. 일부 답변은 웹 검색 결과를 근거로 제시하고, 그럴 땐 "
        "출처를 함께 안내드려요."
    ),
    "feedback_report": "현재는 답변 오류를 신고하거나 수정 요청할 수 있는 별도 경로가 마련돼 있지 않아요. 추후 지원할 예정이에요.",
    "region": "안내드리는 메타 통계는 특정 서버가 아니라 전 세계 통합 집계 기준이에요(리전별로 나눠서 제공하지는 않아요).",
    "voice": "죄송하지만 음성으로 질문하시는 기능은 지원하지 않아요. 텍스트로 질문해 주시면 답변드릴게요.",
    "image": "죄송하지만 스크린샷이나 이미지를 인식하는 기능은 지원하지 않아요. 궁금하신 내용을 텍스트로 설명해 주시면 답변드릴게요.",
    "language": "죄송하지만 한국어로만 답변을 드리고 있어요. 다른 언어 지원은 아직 준비돼 있지 않아요.",
    "realtime_stats": (
        "실시간으로 특정 챔피언의 승률·픽률을 조회하는 기능은 없어요. 다만 현재 "
        "반영된 패치 기준의 메타 조합 통계는 조합·아이템 관련 질문으로 답변드릴 "
        "수 있고, 더 실시간에 가까운 정보는 op.gg 등 통계 사이트를 참고하시는 "
        "걸 권해드려요."
    ),
    "realtime_patch": (
        "실시간으로 패치를 추적하지는 않고, 새 패치가 감지되면 자동으로 데이터가 "
        "갱신되는 방식이에요. 지금 반영된 패치 버전이 궁금하시면 '지금 패치 "
        "몇이야?'처럼 다시 물어봐 주세요. 가장 정확한 최신 정보는 게임 공식 "
        "패치노트를 확인하시는 걸 권장드려요."
    ),
    "match_analysis": "죄송하지만 아직 개인 전적을 분석해드리는 기능은 지원하지 않아요. 추후 지원할 계획이에요.",
    "other_game": "저는 TFT(전략적 팀 전투) 관련 질문만 답변드릴 수 있어요. 다른 게임 질문은 도와드리기 어려운 점 양해 부탁드려요.",
    "feedback_complaint": (
        "불편을 드려 죄송해요. 혹시 어떤 점이 부족했는지 조금 더 말씀해 주시면 "
        "개선하는 데 참고할게요. TFT 관련해서 다시 질문해 주셔도 좋아요."
    ),
    "capability": (
        "저는 TFT(전략적 팀 전투) 메타 정보를 도와드리는 챗봇이에요. 게임 룰 "
        "설명, 아이템·시너지(증강체) 정보, 현재 메타 조합·전략 팁 등을 답변드릴 "
        "수 있어요. 다만 개인 전적 분석이나 실시간 대신 플레이는 지원하지 않아요."
    ),
}


def detect_chatbot_meta_topic(normalized_text: str) -> str | None:
    """챗봇 자신에 대한 메타 질문을 감지해 매칭된 주제 키를 반환한다(매칭 없으면 None).
    여러 버킷이 동시에 매칭될 수 있는 문장은 드물다고 보고 첫 매칭을 그대로 쓴다
    (_CHATBOT_META_TOPICS 목록 순서 = 우선순위)."""
    for topic, pattern in _CHATBOT_META_TOPICS:
        if pattern.search(normalized_text):
            return topic
    return None


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
    "증강체·전략·게임 시스템·경제(골드/이자) 운영·로우롤/하이롤 같은 커뮤니티 "
    "전략 은어 등) 'on_topic'을, 게임과 전혀 무관한 잡담이나 다른 게임 질문이면 "
    "'off_topic'을 다른 말 없이 정확히 하나만 출력해라."
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
