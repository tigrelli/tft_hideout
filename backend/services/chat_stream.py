"""CHAT-05: CHAT-01(의도분류)~CHAT-04(전처리)를 실제로 배선해 Groq 스트리밍
답변을 만든다. API-09가 만든 SSE 배관(build_sse_stream)의 mock을 실제 파이프라인으로
교체한다. CHAT-06(후처리)·CHAT-07(링크 삽입)·CHAT-08(응답 캐싱)·CHAT-09(Q&A 로깅)도
여기서 최종 배선된다."""

import json
import sys
import time
from collections.abc import Callable, Generator

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import ChatLog, MetaDocumentEmbedding
from services.chat_cache import get_cached_answer, store_answer_in_cache
from services.chat_links import extract_champion_ids_from_answer, insert_links
from services.chat_logging import record_chat_log
from services.chat_postprocessing import postprocess_answer
from services.chat_preprocessing import get_conversation_history, preprocess_input
from services.current_patch import get_current_patch_version
from services.hybrid_search import (
    filter_by_name_overlap,
    lookup_item_builds_by_champion_ids,
)
from services.intent_classification import (
    INTENT_GENERAL_GAME_INFO,
    INTENT_ITEM_RECOMMENDATION,
)
from services.prompt_assembly import (
    assemble_system_turn,
    assemble_user_turn,
    assemble_web_search_system_turn,
    assemble_web_search_user_turn,
)
from services.web_search import WebSearchResult, verify_web_citation

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

# CHAT-14: retrieved_docs가 있어도(문서는 검색됐지만) 질문이 원하는 세부 수치·항목이
# 그 안에 없어 시스템 프롬프트 1번 규칙대로 "정보가 확인되지 않았다"류로 답한 턴은
# 후속질문을 만들어봐야 같은 정보를 더 정확히 알려달라는 무의미한 질문만 나온다
# (2026-08-09 PM 피드백 — "보석 건틀릿 치명타 얼마나 증가?" 질문에서 재현). 기존
# retrieved_docs 빈값 체크(아래)만으로는 이 경우를 못 걸러 별도 체크 추가. 모델이
# 규칙 1의 문구를 그대로 재현하지 않고 어미(다/습니다)를 바꿔 표현하는 경우가 실제로
# 관찰돼("확인되지 않았습니다", "제공되지 않았습니다") 어간 단위로 매칭한다 —
# 결정론적 백스톱이라 새로운 표현으로 파라프레이즈되면 놓칠 수 있어, chat_followups.py
# 프롬프트 지시(1차 방어)와 이중으로 둔다.
_NO_GROUNDED_INFO_MARKERS = ("확인되지 않았", "제공되지 않았", "정보가 없", "정보는 없")


def _looks_like_no_info_answer(answer_text: str) -> bool:
    return any(marker in answer_text for marker in _NO_GROUNDED_INFO_MARKERS)


def _build_search_query_text(
    normalized_text: str, conversation_history: list[ChatLog]
) -> str:
    """검색(CHAT-02)에 넘길 텍스트를 만든다. 후속 턴 질문이 "이 챔피언들"처럼
    직전 대화를 가리키는 대명사만 쓰면, 현재 메시지만 임베딩해서는 전혀
    무관한 문서가 뽑히는 문제가 실제로 확인됨(2026-08-07 PM 피드백 — "이
    챔피언들을 조합에 넣을 때 주로 사용하는 아이템은?"만 임베딩하면 직전에
    언급한 5코스트 챔피언 9명과 무관한 챔피언들이 검색됨). 직전 봇 답변
    하나만 현재 질문과 함께 임베딩하면 훨씬 정확해짐을 실측으로 확인 —
    전체 이력까지 섞으면 오히려 희석되므로 바로 직전 턴만 붙인다."""
    if not conversation_history:
        return normalized_text
    return f"{conversation_history[-1].answer}\n{normalized_text}"


def _load_docs_by_ids(db: Session, doc_ids: list[int]) -> list[MetaDocumentEmbedding]:
    """캐시에 저장해둔 근거문서id로 chat_logs.retrieved_doc_ids를 채우기 위해
    실제 문서 행을 다시 조회한다(id 목록만 저장해뒀으므로 캐시 hit 시에도
    embedding/semantic search 없이 인덱스 조회 한 번으로 끝난다)."""
    if not doc_ids:
        return []
    docs = db.scalars(
        select(MetaDocumentEmbedding).where(MetaDocumentEmbedding.id.in_(doc_ids))
    ).all()
    docs_by_id = {doc.id: doc for doc in docs}
    return [docs_by_id[doc_id] for doc_id in doc_ids if doc_id in docs_by_id]


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


def _generate_web_search_answer(
    db: Session,
    *,
    session_id: str,
    patch_version: str,
    normalized_text: str,
    search_query_text: str,
    conversation_history: list[ChatLog],
    wrapped_text: str,
    web_search_fn: Callable[[str], list[WebSearchResult]],
    stream_fn: Callable[[str, str], Generator[str, None, None]],
) -> Generator[str, None, None]:
    """CHAT-17: general_game_info 의도 전용 답변 생성. 내부 RAG(CHAT-02) 대신
    Tavily 웹 검색을 근거로 쓴다. 웹 검색 결과는 meta_document_embeddings에
    없어(캐시·후속질문이 참조하는 retrieved_doc_ids 대상이 아님) CHAT-08 캐시·
    CHAT-11 후속질문 result 사이드채널은 이번 범위에서 지원하지 않는다."""
    try:
        web_results = web_search_fn(search_query_text)
    except Exception:  # noqa: BLE001 — Tavily 무료 티어 오류/한도 초과 시 폴백
        print(
            f"TAVILY_SEARCH_ERROR query={search_query_text!r}",
            file=sys.stderr,
            flush=True,
        )
        yield FALLBACK_MESSAGE
        return

    system_prompt = assemble_web_search_system_turn()
    user_prompt = assemble_web_search_user_turn(
        web_results, conversation_history, wrapped_text
    )

    started_at = time.monotonic()
    raw_answer = "".join(stream_llm_answer(system_prompt, user_prompt, stream_fn))
    processed_answer = postprocess_answer(raw_answer, [])
    final_answer = verify_web_citation(processed_answer, web_results)
    latency_ms = int((time.monotonic() - started_at) * 1000)

    # CHAT-09와 동일 원칙: 의도·패치버전이 확정된(=Tavily 호출까지는 성공한)
    # 정상 흐름이므로 Groq 자체가 실패해 FALLBACK_MESSAGE로 대체됐더라도 로깅한다
    # (메인 흐름의 record_chat_log와 동일하게 캐시만 실패 시 별도로 거른다 — 이
    # 경로는 애초에 캐시를 안 쓰므로 그 구분 자체가 없음).
    record_chat_log(
        db,
        session_id=session_id,
        patch_version=patch_version,
        user_query=normalized_text,
        intent=INTENT_GENERAL_GAME_INFO,
        retrieved_docs=[],
        answer=final_answer,
        latency_ms=latency_ms,
    )

    yield from final_answer.split(" ")


def generate_answer_stream(
    db: Session,
    session_id: str,
    raw_message: str,
    *,
    embed_fn: Callable[[str], list[float]],
    offtopic_confirm_fn: Callable[[str], bool],
    classify_fn: Callable[[str], str],
    search_fn: Callable[[Session, str, str, list[float]], list[MetaDocumentEmbedding]],
    stream_fn: Callable[[str, str], Generator[str, None, None]],
    web_search_fn: Callable[[str], list[WebSearchResult]],
    result: dict[str, object] | None = None,
) -> Generator[str, None, None]:
    """전처리(CHAT-04)가 계산만 해두고 미뤄뒀던 is_off_topic/needs_clarification
    응답 분기를 여기서 실제로 연결하고, 정상 질문은 의도분류(CHAT-01) → 검색(CHAT-02)
    → 프롬프트 조립(CHAT-03) → Groq 스트리밍(CHAT-05) 순으로 배선한다. 각 단계
    로직은 이미 해당 TASK에서 검증됐으므로 이 함수는 배선만 담당한다.

    web_search_fn(CHAT-17): 의도가 general_game_info면 CHAT-02 내부 검색
    대신 이 함수(Tavily)로 근거를 만든다 — 별도 분기(`_generate_web_search_answer`
    참고)라 result 사이드채널(CHAT-11 후속질문)·캐시(CHAT-08)는 이번 범위에서
    지원하지 않는다(웹 검색 결과는 meta_document_embeddings에 없어 기존
    retrieved_doc_ids 기반 캐시/후속질문 구조를 그대로 못 씀 — 필요해지면 별도
    TASK로 확장).

    offtopic_confirm_fn(CHAT-16): preprocessed.is_off_topic은 키워드 매칭 실패만
    의미하는 1차 후보 판정이라, 여기서 2차 LLM 검증으로 재확인한 뒤에만 실제로
    거부한다(키워드가 매칭돼 이미 on-topic이 확실하면 이 함수 자체를 호출하지
    않아 불필요한 Groq 호출을 만들지 않는다).

    result(선택, CHAT-11): 넘겨주면 사용자에게 보여줄 실제 답변이 나온 턴에
    result["answer_text"]를 담아둔다(호출측이 스트림을 전부 소비한 뒤 후속
    질문 생성에 사용) — CHAT-08 캐시 히트도 포함(PM 결정 2026-08-07: 첫 턴이
    캐시에 걸렸다는 이유로 후속질문칩만 없는 게 오히려 사용자 입장에서
    일관성 없어 보인다는 피드백, Groq 호출 1회 추가를 감수). answer_text가
    채워질 때 result["retrieved_doc_types"](set[str])도 함께 채운다 — CHAT-14
    2차 수정(2026-08-09): comp/playstyle 문서에만 조합이 강한 "이유"를 설명하는
    playstyle_text가 있고, champion/item_build 등 다른 doc_type은 수치·목록만
    있어 "왜 승률이 높은가" 같은 원인 분석 질문에 답할 재료가 아예 없다 — 후속
    질문 생성(chat_followups.generate_followup_questions)이 이 여부에 따라
    원인 분석형 후속 질문을 제안할지 판단하는 데 쓴다. 명확화/범위밖/
    패치없음 조기 반환, Groq 완전 실패로 인한 폴백 메시지, retrieved_docs가
    빈 턴("해당 정보는 확인되지 않았다" 류 답변)에는 채우지 않는다(LLM 부재
    없이 호출측 기본값 [] 그대로 유지 = FollowupChips hidden — 이 경우들은
    후속질문을 만들 실질적 내용이 없거나, 근거 문서가 없어 만들어봐야
    "그 정보 어디서 확인하나요" 류 무의미한 질문만 나옴 — 2026-08-07 PM
    피드백). retrieved_docs가 빈 턴은 캐시도 하지 않는다(캐시되면 이후 캐시
    히트 시에도 같은 문제가 재발하므로)."""
    preprocessed = preprocess_input(raw_message)
    if preprocessed.needs_clarification:
        yield CLARIFICATION_MESSAGE
        return
    if preprocessed.is_off_topic and offtopic_confirm_fn(preprocessed.normalized_text):
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
        cached = get_cached_answer(db, preprocessed.normalized_text, patch_version)
        if cached is not None:
            cached_docs = _load_docs_by_ids(db, cached.retrieved_doc_ids or [])
            if result is not None:
                result["answer_text"] = cached.answer
                result["retrieved_doc_types"] = {doc.doc_type for doc in cached_docs}
            # CHAT-09: 캐시 hit 턴도 chat_logs에 남겨야 다음 턴의
            # get_conversation_history가 이 턴을 볼 수 있다(2026-08-07
            # 발견 — 이게 없으면 [이전 대화] 프롬프트 섹션, 문맥 임베딩
            # (_build_search_query_text), 챔피언id 구조화 조회가 모두
            # 이 턴을 못 보고 조용히 깨짐). intent 재계산에 classify_fn을
            # 다시 쓰면 캐싱의 존재 이유(무료 티어 호출 절감)가 없어지므로
            # 캐시 저장 시점에 함께 저장해둔 intent를 그대로 재사용한다.
            # 이 컬럼이 없던 시절 저장된 레거시 캐시 행(intent=None)은
            # 로깅을 건너뛴다 — 패치 갱신으로 곧 자연 무효화된다.
            if cached.intent is not None:
                record_chat_log(
                    db,
                    session_id=session_id,
                    patch_version=patch_version,
                    user_query=preprocessed.normalized_text,
                    intent=cached.intent,
                    retrieved_docs=cached_docs,
                    answer=cached.answer,
                    latency_ms=0,
                )
            yield from cached.answer.split(" ")
            return

    intent = classify_fn(preprocessed.normalized_text)

    if intent == INTENT_GENERAL_GAME_INFO:
        search_query_text = _build_search_query_text(
            preprocessed.normalized_text, conversation_history
        )
        yield from _generate_web_search_answer(
            db,
            session_id=session_id,
            patch_version=patch_version,
            normalized_text=preprocessed.normalized_text,
            search_query_text=search_query_text,
            conversation_history=conversation_history,
            wrapped_text=preprocessed.wrapped_text,
            web_search_fn=web_search_fn,
            stream_fn=stream_fn,
        )
        return

    # 후속질문이 "이 챔피언들"처럼 대명사로 직전 답변을 가리키면, 의미 검색은
    # 근사할 뿐이라 무관한 챔피언이 섞이거나 언급된 챔피언이 빠지는 문제가
    # 실제로 확인됨(2026-08-07 PM 피드백 — 5코스트 9명 질문 후속에 다른
    # 코스트 챔피언들이 섞여 나옴). 직전 답변에 이미 정확한 champion_id가
    # 링크로 박혀있으므로(CHAT-07), item_recommendation 후속 턴에서는 의미
    # 검색 대신 그 id로 구조화 조회한다 — 성공하면(=직전 답변에 챔피언
    # 링크가 있으면) 임베딩 호출 자체를 건너뛰어 HuggingFace 호출도 아낀다.
    retrieved_docs: list[MetaDocumentEmbedding] = []
    if intent == INTENT_ITEM_RECOMMENDATION and conversation_history:
        champion_ids = extract_champion_ids_from_answer(conversation_history[-1].answer)
        if champion_ids:
            retrieved_docs = lookup_item_builds_by_champion_ids(
                db, patch_version, champion_ids
            )

    if not retrieved_docs:
        search_query_text = _build_search_query_text(
            preprocessed.normalized_text, conversation_history
        )
        query_embedding = embed_fn(search_query_text)
        retrieved_docs = search_fn(db, intent, patch_version, query_embedding)
        # CHAT-15 2차 보정: 거리 임계값만으로는 못 거르는 회색지대("광폭검
        # 효과는?"이 '포악한 절단검'과 거리 0.49로 우연히 통과, 2026-08-09
        # PM 검증 중 발견)를 이름 문자 겹침 비율로 추가 방어(hybrid_search.py
        # 참고). search_fn이 이미 patch_version/doc_type/거리 필터를 마쳤으므로
        # 여기서는 item/augment만 한 번 더 거른다.
        retrieved_docs = filter_by_name_overlap(retrieved_docs, search_query_text)

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
    # Groq 호출을 하나 더 추가하는 것도 낭비). retrieved_docs가 비어 검색된
    # 내용이 전혀 없는 턴("해당 정보는 확인되지 않았다" 류 답변)도 제외한다
    # (2026-08-07 PM 피드백: 근거 문서가 없는 답변에 대해 후속질문을 만들면
    # "해당 정보를 어디서 확인할 수 있나요" 같이 답변 자체를 되묻는 무의미한
    # 질문만 나옴 — 애초에 문서가 없으니 의미 있는 후속질문을 만들 재료가 없음).
    # CHAT-14: retrieved_docs가 있어도(문서는 찾았지만) 답변 자체가 "정보가
    # 확인되지 않았다"류면 마찬가지로 제외한다(위 _looks_like_no_info_answer,
    # 2026-08-09 PM 피드백).
    if (
        result is not None
        and raw_answer != FALLBACK_MESSAGE
        and retrieved_docs
        and not _looks_like_no_info_answer(raw_answer)
    ):
        result["answer_text"] = final_answer
        result["retrieved_doc_types"] = {doc.doc_type for doc in retrieved_docs}

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
    # 배포 검증 중 실제로 이 상태에 빠진 것을 발견해 2026-08-06 수정). 검색된
    # 문서가 없는("해당 정보는 확인되지 않았다" 류) 답변도 캐시하지 않는다
    # — 캐시된 채로 남으면 이후 캐시 히트 시에도 result["answer_text"]가
    # 채워져 후속질문 생성 대상이 되는데, 근거 문서가 없어 의미 있는
    # 후속질문을 만들 수 없기 때문(2026-08-07 PM 피드백, 위 result 채우는
    # 조건과 동일한 이유).
    if is_first_turn and raw_answer != FALLBACK_MESSAGE and retrieved_docs:
        store_answer_in_cache(
            db,
            preprocessed.normalized_text,
            patch_version,
            final_answer,
            intent=intent,
            retrieved_doc_ids=[doc.id for doc in retrieved_docs],
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
    (FollowupChips hidden, 기존 done-only 클라이언트와도 호환).

    CHAT-12: 토큰이 개행문자를 포함하면(CHAT-12 서식 규칙으로 답변에 `\n`이
    들어가는 경우가 늘어남) `data: <토큰>\n\n`의 개행이 SSE 이벤트 구분자
    `\n\n`과 섞여 `chat-stream.ts`가 첫 줄만 읽고 나머지를 통째로 잃어버리는
    문제가 있어(2026-08-08 발견, CHAT-12 작업결과 참고) 토큰 내부 개행만
    `\\n`으로 이스케이프해서 보낸다 — 프론트가 수신 직후 원래 문자로 되돌린다."""
    for token in token_stream:
        yield f"data: {token.replace(chr(10), '\\n')}\n\n"
    if followups_fn is not None:
        questions = followups_fn()
        if questions:
            yield f"event: followups\ndata: {json.dumps(questions, ensure_ascii=False)}\n\n"
    yield "event: done\ndata: [DONE]\n\n"
