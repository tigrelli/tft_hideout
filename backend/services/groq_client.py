import os
from functools import lru_cache

from groq import Groq

GROQ_MODEL = "llama-3.3-70b-versatile"


@lru_cache
def _get_client() -> Groq:
    return Groq(api_key=os.environ["GROQ_API_KEY"])


def call_groq_chat(system_prompt: str, user_message: str) -> str:
    """Groq sLLM 채팅 완성 호출. 실패 시 예외를 그대로 던지며,
    폴백 처리는 호출측(예: intent_classification.classify_by_llm)에서 담당한다."""
    response = _get_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
        max_tokens=20,
    )
    return response.choices[0].message.content or ""
