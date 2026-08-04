"""CHAT-05: CHAT-01(의도분류)~CHAT-04(전처리)를 실제로 배선해 Groq 스트리밍
답변을 만든다. API-09가 만든 SSE 배관(build_sse_stream)의 mock을 실제 파이프라인으로
교체한다."""

from collections.abc import Callable, Generator

from sqlalchemy.orm import Session

from db.models import ChatLog, MetaDocumentEmbedding
from services.chat_postprocessing import postprocess_answer
from services.chat_preprocessing import get_conversation_history, preprocess_input
from services.current_patch import get_current_patch_version
from services.prompt_assembly import assemble_system_turn, assemble_user_turn

CLARIFICATION_MESSAGE = (
    "질문을 조금 더 구체적으로 입력해주시겠어요? 예: '지금 메타에서 강한 조합 추천해줘'"
)
OFF_TOPIC_MESSAGE = (
    "죄송하지만 TFT(전략적 팀 전투) 관련 질문에만 답변드릴 수 있어요. "
    "TFT 관련해서 궁금하신 점을 다시 질문해 주세요."
)
NO_CURRENT_PATCH_MESSAGE = (
    "현재 패치 정보가 없어 답변을 생성할 수 없습니다. 잠시 후 다시 시도해주세요."
)
FALLBACK_MESSAGE = (
    "죄송합니다, 일시적인 오류로 답변을 생성하지 못했습니다. 잠시 후 다시 시도해주세요."
)

MAX_LLM_ATTEMPTS = 2


def stream_llm_answer(
    system_prompt: str,
    user_message: str,
    stream_fn: Callable[[str, str], Generator[str, None, None]],
) -> Generator[str, None, None]:
    """Groq 스트리밍 호출(stream_fn). 토큰을 하나도 받기 전에 실패하면 1회 재시도하고,
    그래도 실패하거나 스트림 도중 실패하면 예외를 전파하지 않고 고정 폴백 메시지로
    대체한다(WBS CHAT-05 테스트요구사항: 타임아웃 예외 처리 확인)."""
    for attempt in range(MAX_LLM_ATTEMPTS):
        yielded_any = False
        try:
            for token in stream_fn(system_prompt, user_message):
                yielded_any = True
                yield token
            return
        except Exception:  # noqa: BLE001 — Groq 무료 티어 타임아웃/오류 대비 폴백
            if not yielded_any and attempt < MAX_LLM_ATTEMPTS - 1:
                continue
            yield FALLBACK_MESSAGE
            return


def generate_answer_stream(
    db: Session,
    session_id: str,
    raw_message: str,
    *,
    embed_fn: Callable[[str], list[float]],
    classify_fn: Callable[[str], str],
    search_fn: Callable[[Session, str, str, list[float]], list[MetaDocumentEmbedding]],
    stream_fn: Callable[[str, str], Generator[str, None, None]],
) -> Generator[str, None, None]:
    """전처리(CHAT-04)가 계산만 해두고 미뤄뒀던 is_off_topic/needs_clarification
    응답 분기를 여기서 실제로 연결하고, 정상 질문은 의도분류(CHAT-01) → 검색(CHAT-02)
    → 프롬프트 조립(CHAT-03) → Groq 스트리밍(CHAT-05) 순으로 배선한다. 각 단계
    로직은 이미 해당 TASK에서 검증됐으므로 이 함수는 배선만 담당한다."""
    preprocessed = preprocess_input(raw_message)
    if preprocessed.needs_clarification:
        yield CLARIFICATION_MESSAGE
        return
    if preprocessed.is_off_topic:
        yield OFF_TOPIC_MESSAGE
        return

    patch_version = get_current_patch_version(db)
    if patch_version is None:
        yield NO_CURRENT_PATCH_MESSAGE
        return

    intent = classify_fn(preprocessed.normalized_text)
    conversation_history: list[ChatLog] = get_conversation_history(db, session_id)
    query_embedding = embed_fn(preprocessed.normalized_text)
    retrieved_docs = search_fn(db, intent, patch_version, query_embedding)

    system_prompt = assemble_system_turn(intent)
    user_prompt = assemble_user_turn(
        patch_version, retrieved_docs, conversation_history, preprocessed.wrapped_text
    )

    # CHAT-06 후처리(근거검증·승률마스킹)는 완성된 문장 단위로만 신뢰할 수 있어
    # (부분 토큰 중간에 숫자·인용부호가 잘리면 정규식이 오작동) 여기서 스트림을
    # 전부 버퍼링한 뒤 후처리하고, 검증된 최종 텍스트를 다시 단어 단위로 쪼개
    # 내보낸다(체감 스트리밍 유지 — 실시간 생성 속도는 아니지만 순차 전송은 유지,
    # PM 승인 2026-08-04, CHAT-06 작업결과 참고).
    raw_answer = "".join(stream_llm_answer(system_prompt, user_prompt, stream_fn))
    final_answer = postprocess_answer(raw_answer, retrieved_docs)
    yield from final_answer.split(" ")


def build_sse_stream(
    token_stream: Generator[str, None, None],
) -> Generator[str, None, None]:
    """토큰 제너레이터를 SSE(text/event-stream) 포맷으로 감싼다.
    각 토큰은 `data:` 이벤트로, 스트림 종료는 별도 `done` 이벤트로 보내
    클라이언트가 연결 종료 시점을 명확히 알 수 있게 한다."""
    for token in token_stream:
        yield f"data: {token}\n\n"
    yield "event: done\ndata: [DONE]\n\n"
