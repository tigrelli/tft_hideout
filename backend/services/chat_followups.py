"""CHAT-11: 답변 생성 직후 맥락 기반 후속 질문을 LLM으로 만든다(FE-09
SuggestedFollowupChips가 쓰던 고정 4개 예시 질문을 대체). 레이트리밋/지연
절감을 위해 재시도 없이 1회만 시도하고, 실패하거나 파싱할 내용이 없으면
빈 목록을 반환한다(policies.md 9번 — 무료 인프라 한도 대응과 동일한 원칙,
빈 목록이면 FE-09가 만든 ChatFollowupChips는 자동으로 hidden 처리된다)."""

from __future__ import annotations

from collections.abc import Callable

MAX_FOLLOWUP_QUESTIONS = 3
FOLLOWUP_MAX_TOKENS = 200

_SYSTEM_PROMPT = (
    "다음은 TFT(전략적 팀 전투) 챗봇이 방금 사용자에게 준 답변이다. "
    f"사용자가 이어서 물어볼 만한 자연스러운 후속 질문을 최대 {MAX_FOLLOWUP_QUESTIONS}개, "
    "한 줄에 하나씩만 출력해라. 번호·기호·설명 없이 질문 문장만 출력하고, "
    "답변에 등장한 조합/챔피언/아이템/증강체 이름을 최대한 활용해 구체적으로 만들어라. "
    "후속 질문으로 만들 만한 내용이 전혀 없으면 빈 줄만 출력해라."
)

_BULLET_CHARS = " -*•\t"


def _build_user_message(answer_text: str) -> str:
    return f"[챗봇 답변]\n{answer_text}"


def generate_followup_questions(
    answer_text: str,
    llm_call: Callable[..., str],
) -> list[str]:
    """answer_text가 비어 있거나 llm_call이 실패하면 빈 목록(hidden)을 반환한다.
    llm_call은 (system_prompt, user_message, *, max_tokens) -> 응답 텍스트를
    반환하는 함수(테스트에서는 mock 주입, 운영에서는 groq_client.call_groq_chat)."""
    if not answer_text.strip():
        return []
    try:
        raw = llm_call(
            _SYSTEM_PROMPT,
            _build_user_message(answer_text),
            max_tokens=FOLLOWUP_MAX_TOKENS,
        )
    except Exception:  # noqa: BLE001 — Groq 무료 티어 오류/한도 초과 시 폴백(policies.md 9번)
        return []

    questions = [line.strip(_BULLET_CHARS) for line in raw.splitlines()]
    questions = [q for q in questions if q]
    return questions[:MAX_FOLLOWUP_QUESTIONS]
