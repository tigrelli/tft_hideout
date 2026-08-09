"""CHAT-11: 답변 생성 직후 맥락 기반 후속 질문을 LLM으로 만든다(FE-09
SuggestedFollowupChips가 쓰던 고정 4개 예시 질문을 대체). 레이트리밋/지연
절감을 위해 재시도 없이 1회만 시도하고, 실패하거나 파싱할 내용이 없으면
빈 목록을 반환한다(policies.md 9번 — 무료 인프라 한도 대응과 동일한 원칙,
빈 목록이면 FE-09가 만든 ChatFollowupChips는 자동으로 hidden 처리된다)."""

from __future__ import annotations

from collections.abc import Callable

MAX_FOLLOWUP_QUESTIONS = 1
FOLLOWUP_MAX_TOKENS = 200

_SYSTEM_PROMPT_BASE = (
    "다음은 TFT(전략적 팀 전투) 챗봇이 방금 사용자에게 준 답변이다. "
    f"사용자가 이어서 물어볼 만한 자연스러운 후속 질문을 최대 {MAX_FOLLOWUP_QUESTIONS}개, "
    "한 줄에 하나씩만 출력해라. 번호·기호·설명 없이 질문 문장만 출력하고, "
    "답변에 등장한 조합/챔피언/아이템/증강체 이름을 최대한 활용해 구체적으로 만들어라. "
    "후속 질문으로 만들 만한 내용이 전혀 없으면 빈 줄만 출력해라. "
    "이 챗봇은 실시간으로 외부를 검색하지 못하고 미리 준비된 문서만 근거로 답하므로, "
    "답변이 '확인되지 않았다/제공되지 않는다/정보가 없다'처럼 요청한 정보를 찾지 "
    "못했다는 내용이면 같은 정보를 더 정확히·자세히 알려달라는 후속 질문은 만들지 "
    "말고 빈 줄만 출력해라(다시 물어도 같은 대답만 반복된다)."
)

# CHAT-14 2차 수정(2026-08-09 PM 피드백): "블리츠크랭크와 바드가 높은 승률을 보인
# 이유는?"처럼 원인을 분석해야 답할 수 있는 후속 질문이 실제로 제안된 적이 있는데,
# 챗봇이 가진 문서는 승률/픽률/구성 같은 수치·목록뿐이라(조합 플레이 스타일
# 설명(comp/playstyle doc_type)에만 "왜 강한지"에 해당하는 서술이 있음) 대부분의
# 경우 이런 질문 자체가 항상 "확인되지 않았다"로 귀결된다. 조합 관련 답변까지
# 전부 막으면 실제로 답할 수 있는 "이 조합이 왜 강해?" 류 질문까지 사라지므로,
# 직전 답변이 comp/playstyle 문서를 근거로 하지 않았을 때만 이 규칙을 덧붙인다
# (chat_stream.generate_answer_stream이 result["retrieved_doc_types"]로 알려줌).
_NARRATIVE_DOC_TYPES = {"comp", "playstyle"}
_NO_REASONING_CONTEXT_RULE = (
    " 이번 답변은 승률/픽률/구성/효과 같은 수치·사실 정보만 근거로 했고 그 원인을 "
    "설명하는 문서는 없었다. '왜 승률이 높은가/무엇이 강력한 이유인가'처럼 원인·이유를"
    " 분석해야 답할 수 있는 후속 질문은 만들지 말고, 사실·수치를 그대로 물어볼 수 있는"
    " 질문만 만들어라."
)

_BULLET_CHARS = " -*•\t"


def _build_user_message(answer_text: str) -> str:
    return f"[챗봇 답변]\n{answer_text}"


def generate_followup_questions(
    answer_text: str,
    llm_call: Callable[..., str],
    *,
    retrieved_doc_types: set[str] | None = None,
) -> list[str]:
    """answer_text가 비어 있거나 llm_call이 실패하면 빈 목록(hidden)을 반환한다.
    llm_call은 (system_prompt, user_message, *, max_tokens) -> 응답 텍스트를
    반환하는 함수(테스트에서는 mock 주입, 운영에서는 groq_client.call_groq_chat).
    retrieved_doc_types(선택, CHAT-14 2차 수정): 직전 답변이 근거로 삼은 문서
    doc_type 집합 — comp/playstyle이 아니면 원인 분석형 후속 질문을 만들지 않게
    시스템 프롬프트에 규칙을 덧붙인다(위 _NO_REASONING_CONTEXT_RULE 참고)."""
    if not answer_text.strip():
        return []
    system_prompt = _SYSTEM_PROMPT_BASE
    if not (retrieved_doc_types and retrieved_doc_types & _NARRATIVE_DOC_TYPES):
        system_prompt += _NO_REASONING_CONTEXT_RULE
    try:
        raw = llm_call(
            system_prompt,
            _build_user_message(answer_text),
            max_tokens=FOLLOWUP_MAX_TOKENS,
        )
    except Exception:  # noqa: BLE001 — Groq 무료 티어 오류/한도 초과 시 폴백(policies.md 9번)
        return []

    questions = [line.strip(_BULLET_CHARS) for line in raw.splitlines()]
    questions = [q for q in questions if q]
    return questions[:MAX_FOLLOWUP_QUESTIONS]
