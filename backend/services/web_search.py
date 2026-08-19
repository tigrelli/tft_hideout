"""CHAT-17: 내부 RAG(CHAT-02)가 커버하지 않는 "일반 게임 정보" 질문(시즌 일정,
공식 이벤트 등)에 SET-17에서 발급한 Tavily API로 웹 검색 근거를 제공한다."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_MAX_RESULTS = 3

# CHAT-22: Tavily는 도메인 신뢰도를 구분하지 않고 결과를 반환하므로, 라이엇
# 공식·TFT 전문 데이터 사이트만 별도로 표시해 프롬프트가 개인 블로그·일반
# 커뮤니티 위키 출처를 단정적으로 인용하지 않도록 유도한다(TEST-11 카테고리 B
# QA에서 저신뢰 블로그 하나만 근거로 "상점에서 특정 챔피언을 안 뜨게 잠글 수
# 있다"는 사실과 다른 단정적 답변이 나온 사례 발견, 2026-08-15).
_AUTHORITATIVE_DOMAINS = frozenset(
    {
        "teamfighttactics.leagueoflegends.com",
        "leagueoflegends.com",
        "lolchess.gg",
        "op.gg",
        "mobalytics.gg",
        "tactics.tools",
        "metatft.com",
    }
)


def is_authoritative_source(url: str) -> bool:
    """url의 호스트가 공식/TFT 전문 정보 사이트 allowlist에 속하는지 판별한다
    (서브도메인 포함, 예: 'na.op.gg' -> 'op.gg' 매칭)."""
    host = urlparse(url).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return any(
        host == domain or host.endswith(f".{domain}")
        for domain in _AUTHORITATIVE_DOMAINS
    )


UNVERIFIED_SOURCE_WARNING = "(주의: 위 답변에 포함된 출처 링크 중 일부는 실제 검색 결과에서 확인되지 않았습니다.)"

# CHAT-30(TEST-11 H15에서 발견, 2026-08-19): verify_web_citation()은 URL이
# 실제 검색 결과에 있는지만 확인할 뿐, 본문 내용 자체(세트 번호·날짜 등
# 구체적 사실)가 검색 결과에 실재하는지는 검증하지 않는다 — H15가 실제
# 검색 결과에 전혀 없는 "세트 15"/"세트 14"를 구체적으로 단정한 사례가
# 실측 확인됨(할루시네이션 URL이라 UNVERIFIED_SOURCE_WARNING은 붙었지만,
# 본문 내용의 근거 없음은 별도로 안 걸러졌음).
UNGROUNDED_CONTENT_WARNING = (
    "(주의: 위 답변에 포함된 세트 번호·날짜 등 구체적 사실 중 일부는 "
    "실제 검색 결과에서 확인되지 않았습니다.)"
)
_SET_NUMBER_PATTERN = re.compile(r"세트\s*(\d+)")
_EXPLICIT_DATE_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}|\d{4}년\s*\d{1,2}월(?:\s*\d{1,2}일)?"
)

# URL 뒤에 붙는 문장부호(마침표·쉼표·괄호 등)는 URL의 일부가 아니므로 매칭 시
# 제거한다. 정규식 문자 클래스 자체에서 ')'/']'/공백을 제외해 대부분의 경우는
# 이미 걸러지지만, 문장 종결 마침표(URL에서 유효 문자라 정규식만으로는 못 거름)
# 등 나머지는 아래 rstrip으로 추가 정리한다(verify_web_citation 참고).
_URL_PATTERN = re.compile(r"https?://[^\s)\]]+")
_URL_TRAILING_PUNCTUATION = ".,;:!?)]'\""

# CHAT-29(TEST-11 E4·E15에서 발견, 2026-08-19): "[출처 1] [출처 2]"/"[출처]"처럼
# 라벨만 있고 뒤에 URL이 아예 없는 답변이 실측 확인됐다. 기존 검증은
# urls_in_answer가 하나도 없으면("URL 자체가 없음") 검증할 게 없다고 보고
# 그냥 통과시켰는데, 라벨만 있고 실제 링크가 없는 인용은 할루시네이션
# URL만큼이나 신뢰할 수 없어(클릭해도 아무 데도 안 감) 같은 경고 대상으로
# 취급한다.
_ORPHANED_CITATION_PATTERN = re.compile(r"\[출처(?:\s*\d+)?\](?!\s*\()")


@dataclass
class WebSearchResult:
    title: str
    url: str
    content: str


def search_web(
    query: str, *, max_results: int = DEFAULT_MAX_RESULTS
) -> list[WebSearchResult]:
    """운영 진입점. 실패(타임아웃/HTTP 오류/쿼터 소진)는 예외를 그대로 던지며,
    폴백 처리는 호출측(chat_stream.py)이 담당한다(policies.md 9번, groq_client
    등 다른 외부 API 호출부와 동일 패턴)."""
    api_key = os.environ["TAVILY_API_KEY"]
    response = httpx.post(
        TAVILY_SEARCH_URL,
        json={"api_key": api_key, "query": query, "max_results": max_results},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    return [
        WebSearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            content=item.get("content", ""),
        )
        for item in data.get("results", [])
    ]


def verify_web_citation(answer_text: str, web_results: list[WebSearchResult]) -> str:
    """CHAT-06 verify_grounding()과 동일한 원칙(결정론적 사후 점검) — 답변에
    포함된 URL이 전부 실제 검색 결과 URL이고 모든 "[출처]" 라벨에 URL이
    붙어있으면 그대로 반환. 검색 결과에 없는(할루시네이션) URL이 있거나,
    URL이 아예 없는 "[출처]" 라벨(CHAT-29)만 있어도 경고 문구를 덧붙인다."""
    urls_in_answer = _URL_PATTERN.findall(answer_text)
    known_urls = {result.url for result in web_results}
    has_hallucinated_url = urls_in_answer and not all(
        url.rstrip(_URL_TRAILING_PUNCTUATION) in known_urls for url in urls_in_answer
    )
    has_orphaned_citation = _ORPHANED_CITATION_PATTERN.search(answer_text) is not None
    if not has_hallucinated_url and not has_orphaned_citation:
        return answer_text
    return f"{answer_text}\n\n{UNVERIFIED_SOURCE_WARNING}"


def verify_web_content_grounding(
    answer_text: str, web_results: list[WebSearchResult]
) -> str:
    """CHAT-30: verify_web_citation()이 놓치는 "본문 내용 자체의 근거 없음"을
    잡는 결정론적 사후 점검(CHAT-06 verify_grounding()과 동일 원칙) — 답변에
    등장하는 세트 번호·명시적 날짜가 실제 검색 결과 본문(title+content)에
    하나도 없으면 경고를 붙인다. URL이 맞더라도 본문 내용은 LLM이 그 URL과
    무관하게 지어낼 수 있어(H15 실측) 별도로 검증한다."""
    combined_content = " ".join(f"{r.title} {r.content}" for r in web_results)
    claimed_sets = set(_SET_NUMBER_PATTERN.findall(answer_text))
    grounded_sets = set(_SET_NUMBER_PATTERN.findall(combined_content))
    claimed_dates = set(_EXPLICIT_DATE_PATTERN.findall(answer_text))
    grounded_dates = set(_EXPLICIT_DATE_PATTERN.findall(combined_content))
    if claimed_sets <= grounded_sets and claimed_dates <= grounded_dates:
        return answer_text
    return f"{answer_text}\n\n{UNGROUNDED_CONTENT_WARNING}"
