import os
from collections.abc import Generator
from functools import lru_cache

from groq import Groq

GROQ_MODEL = "openai/gpt-oss-120b"

# CHAT-23(2026-08-16): gpt-oss-120b는 리즈닝 모델이라 최종 답변 전에 별도
# reasoning 토큰을 먼저 소비한다(예: 단순 분류 질문에도 12~52 reasoning
# 토큰 관측). 이전 모델(llama-3.3-70b-versatile) 기준으로 정해졌던
# max_tokens=20은 reasoning 토큰만으로 전부 소진되어 content가 빈 문자열로
# 잘리는 회귀가 실측 확인됨(finish_reason="length"). reasoning_effort="low"로
# reasoning 토큰을 줄이고, max_tokens=100으로 올려 관측된 최대치(52)에
# 여유를 둔다(TEST-11 재개 중 발견, 실제 API 호출로 검증).
_SHORT_CALL_MAX_TOKENS = 100
_SHORT_CALL_REASONING_EFFORT = "low"


@lru_cache
def _get_client() -> Groq:
    return Groq(api_key=os.environ["GROQ_API_KEY"])


def call_groq_chat(
    system_prompt: str, user_message: str, *, max_tokens: int = _SHORT_CALL_MAX_TOKENS
) -> str:
    """Groq sLLM 채팅 완성 호출. 실패 시 예외를 그대로 던지며,
    폴백 처리는 호출측(예: intent_classification.classify_by_llm,
    chat_followups.generate_followup_questions)에서 담당한다. 짧고 구조화된
    응답(분류 토큰 등)이 기대되는 호출 전용이라 reasoning_effort="low"를
    고정 적용한다."""
    response = _get_client().chat.completions.create(
        model=GROQ_MODEL,
        reasoning_effort=_SHORT_CALL_REASONING_EFFORT,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def stream_groq_chat(
    system_prompt: str, user_message: str
) -> Generator[str, None, None]:
    """Groq sLLM 채팅 완성을 스트리밍으로 호출해 델타 토큰을 순서대로 yield한다.
    실패 시 예외를 그대로 던지며, 재시도·폴백은 호출측(chat_stream.stream_llm_answer)이
    담당한다."""
    stream = _get_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
