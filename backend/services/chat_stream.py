"""CHAT-05: CHAT-01(의도분류)~CHAT-04(전처리)를 실제로 배선해 Groq 스트리밍
답변을 만든다. API-09가 만든 SSE 배관(build_sse_stream)의 mock을 실제 파이프라인으로
교체한다. CHAT-06(후처리)·CHAT-07(링크 삽입)·CHAT-08(응답 캐싱)·CHAT-09(Q&A 로깅)도
여기서 최종 배선된다."""

import json
import sys
import time
from collections.abc import Callable, Generator

from sqlalchemy.orm import Session

from db.models import ChatLog, MetaDocumentEmbedding
from services.chat_cache import get_cached_answer, store_answer_in_cache
from services.chat_links import insert_links
from services.chat_logging import record_chat_log
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
    대체한다(WBS CHAT-05 테스트요구사항: 타임아웃 예외 처리 확인).

    사용자에게는 FALLBACK_MESSAGE만 보이고 실제 예외는 삼켜지므로, 원인 파악이
    가능하도록 진단 메시지를 남긴다(운영 중 GROQ_API_KEY 오설정 등을 진단하다가
    실제 예외가 어디에도 기록되지 않는 것을 확인해 2026-08-06 추가, CHAT-11
    후속 조치). `logging` 모듈 대신 stderr에 직접 print하는 이유: 이 앱에
    logging 설정이 전혀 없는 상태에서 warning 레벨 로그가 Render 로그에
    나타나지 않는 것을 실제로 확인했다(uvicorn/일부 의존성이 root logger에
    핸들러를 붙이면서 propagate를 막는 것으로 추정) — print는 그런 설정과
    무관하게 항상 보인다."""
    for attempt in range(MAX_LLM_ATTEMPTS):
        yielded_any = False
        try:
            for token in stream_fn(system_prompt, user_message):
                yielded_any = True
                yield token
            return
        except Exception as exc:  # noqa: BLE001 — Groq 무료 티어 타임아웃/오류 대비 폴백
            print(
                f"GROQ_STREAM_ERROR attempt={attempt + 1}/{MAX_LLM_ATTEMPTS} "
                f"yielded_any={yielded_any} type={type(exc).__name__} error={exc!r}",
                file=sys.stderr,
                flush=True,
            )
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
    result: dict[str, object] | None = None,
) -> Generator[str, None, None]:
    """전처리(CHAT-04)가 계산만 해두고 미뤄뒀던 is_off_topic/needs_clarification
    응답 분기를 여기서 실제로 연결하고, 정상 질문은 의도분류(CHAT-01) → 검색(CHAT-02)
    → 프롬프트 조립(CHAT-03) → Groq 스트리밍(CHAT-05) 순으로 배선한다. 각 단계
    로직은 이미 해당 TASK에서 검증됐으므로 이 함수는 배선만 담당한다.

    result(선택, CHAT-11): 넘겨주면 사용자에게 보여줄 실제 답변이 나온 턴에
    result["answer_text"]를 담아둔다(호출측이 스트림을 전부 소비한 뒤 후속
    질문 생성에 사용) — CHAT-08 캐시 히트도 포함(PM 결정 2026-08-07: 첫 턴이
    캐시에 걸렸다는 이유로 후속질문칩만 없는 게 오히려 사용자 입장에서
    일관성 없어 보인다는 피드백, Groq 호출 1회 추가를 감수). 명확화/범위밖/
    패치없음 조기 반환과 Groq 완전 실패로 인한 폴백 메시지에는 채우지
    않는다(LLM 부재 없이 호출측 기본값 [] 그대로 유지 = FollowupChips
    hidden — 이 두 경우는 여전히 후속질문을 만들 실질적 내용이 없음)."""
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

    # CHAT-08: 대화 이력이 없는 첫 턴 질문만 캐시 대상(같은 문장도 후속 턴에서는
    # 직전 맥락에 따라 정답이 달라지므로 후속 턴은 캐시를 아예 조회하지 않음).
    conversation_history: list[ChatLog] = get_conversation_history(db, session_id)
    is_first_turn = len(conversation_history) == 0
    if is_first_turn:
        cached_answer = get_cached_answer(
            db, preprocessed.normalized_text, patch_version
        )
        if cached_answer is not None:
            if result is not None:
                result["answer_text"] = cached_answer
            yield from cached_answer.split(" ")
            return

    intent = classify_fn(preprocessed.normalized_text)
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
    started_at = time.monotonic()
    raw_answer = "".join(stream_llm_answer(system_prompt, user_prompt, stream_fn))
    processed_answer = postprocess_answer(raw_answer, retrieved_docs)
    # CHAT-07: 검증된(=검색 문서에 실재하는) 인용 이름만 상세 페이지 링크로 치환.
    # verify_grounding이 이미 미검증 이름을 걸러내므로, 여기서는 존재하지 않는
    # id로 링크를 만들 위험이 없다.
    final_answer = insert_links(processed_answer, retrieved_docs)
    latency_ms = int((time.monotonic() - started_at) * 1000)

    # CHAT-11: Groq가 완전히 실패해 FALLBACK_MESSAGE로 대체된 답변은 후속질문
    # 생성 대상에서 제외(에러 문구를 이어서 되물을 이유가 없고, 실패한 턴에
    # Groq 호출을 하나 더 추가하는 것도 낭비).
    if result is not None and raw_answer != FALLBACK_MESSAGE:
        result["answer_text"] = final_answer

    # CHAT-09: chat_logs 적재는 의도분류·검색·답변생성이 전부 이뤄진 정상 흐름에서만
    # 수행(명확화/범위밖/패치없음 조기 반환은 intent·patch_version이 없어 대상 아님).
    record_chat_log(
        db,
        session_id=session_id,
        patch_version=patch_version,
        user_query=preprocessed.normalized_text,
        intent=intent,
        retrieved_docs=retrieved_docs,
        answer=final_answer,
        latency_ms=latency_ms,
    )

    # Groq가 완전히 실패해 FALLBACK_MESSAGE로 대체된 턴은 캐시하지 않는다
    # (캐시 키가 session_id가 아니라 질문 문장+패치 버전이라, 캐시하면 그
    # 문장을 묻는 모든 세션이 다음 패치까지 계속 폴백만 받게 됨 — CHAT-11
    # 배포 검증 중 실제로 이 상태에 빠진 것을 발견해 2026-08-06 수정).
    if is_first_turn and raw_answer != FALLBACK_MESSAGE:
        store_answer_in_cache(
            db, preprocessed.normalized_text, patch_version, final_answer
        )

    yield from final_answer.split(" ")


def build_sse_stream(
    token_stream: Generator[str, None, None],
    *,
    followups_fn: Callable[[], list[str]] | None = None,
) -> Generator[str, None, None]:
    """토큰 제너레이터를 SSE(text/event-stream) 포맷으로 감싼다.
    각 토큰은 `data:` 이벤트로, 스트림 종료는 별도 `done` 이벤트로 보내
    클라이언트가 연결 종료 시점을 명확히 알 수 있게 한다.

    followups_fn(선택, CHAT-11): 토큰 스트림을 전부 소비한 뒤(=제너레이터
    본문이 끝까지 실행돼 result 딕셔너리가 채워진 뒤) 호출해 후속 질문
    목록을 얻는다. 목록이 비어 있으면 이벤트 자체를 보내지 않는다
    (FollowupChips hidden, 기존 done-only 클라이언트와도 호환)."""
    for token in token_stream:
        yield f"data: {token}\n\n"
    if followups_fn is not None:
        questions = followups_fn()
        if questions:
            yield f"event: followups\ndata: {json.dumps(questions, ensure_ascii=False)}\n\n"
    yield "event: done\ndata: [DONE]\n\n"
