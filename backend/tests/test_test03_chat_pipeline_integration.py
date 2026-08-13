"""TEST-03: chat API 및 RAG 파이프라인 테스트 — 의도분류/검색/생성/후처리/캐싱,
DoD "전체 통과, 근거율 샘플 검증".

CHAT-01~09 각 TASK는 이미 자기 단계를 촘촘히 단위 테스트한다. 그런데
`generate_answer_stream`(CHAT-05)을 호출하는 기존 테스트(test_chat05_streaming.py,
test_chat08_cache.py 등 29건 이상)는 전부 `classify_fn`/`search_fn`을 하드코딩된
람다로 갈아끼워서 실행하고, `test_api09_chat_message_stream.py`도 스스로
"실제 LLM 파이프라인 배선은 CHAT-05가 대체했다"며 검증을 명시적으로 미뤄뒀다.
즉 **실제 `classify_intent`(CHAT-01) → 실제 `hybrid_search`(CHAT-02, 진짜
pgvector 검색) → `generate_answer_stream`의 오케스트레이션 → 실제
`postprocess_answer`의 근거검증(CHAT-06)**이 한 번도 함께 실행된 적이 없다
(외부 I/O인 Groq/HF만 계속 fake로 유지하는 게 맞고, 그 경계 안쪽은 전부 실제
구현을 그대로 쓴다). 이 파일은 그 배선 자체와, 서로 다른 doc_type(조합/증강체)
샘플에 대한 근거율(grounding)을 검증한다.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.models import EMBEDDING_DIM, MetaDocumentEmbedding, Patch
from services.chat_postprocessing import UNVERIFIED_NAME_WARNING
from services.chat_stream import generate_answer_stream
from services.hybrid_search import hybrid_search
from services.intent_classification import (
    classify_intent,
)

SESSION_ID = "11111111-1111-1111-1111-111111111111"


def _fail_if_called(*args, **kwargs):
    raise AssertionError("Groq LLM이 호출되면 안 됨(키워드 1차 분류로 확정돼야 함)")


def _one_hot(index: int) -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    vec[index] = 1.0
    return vec


@pytest.fixture
def seeded_session(migrated_engine: Engine) -> Session:
    with Session(migrated_engine) as session:
        session.execute(
            insert(Patch).values(
                version="17.8",
                set_number=17,
                released_at=datetime(2026, 1, 1, tzinfo=UTC),
                is_current=True,
                detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="comp",
                source_table="comps",
                source_id=1,
                content_text="리롤 요네: 8레벨 리롤 성향의 조합",
                embedding=_one_hot(0),
                doc_metadata={"name": "리롤 요네"},
            )
        )
        session.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="augment",
                source_table="augments",
                source_id=1,
                content_text="힘의 마법공학: 공격력이 증가한다",
                embedding=_one_hot(1),
                doc_metadata={"name": "힘의 마법공학"},
            )
        )
        session.commit()
        yield session


# doc_type별 (질의, 임베딩 인덱스, 실제 문서 이름) — comp_recommendation은 doc_type
# "comp"를, augment_recommendation은 "augment"를 검색하도록 keyword로 확정된다.
# augment/item doc_type은 hybrid_search의 filter_by_name_overlap(CHAT-15)이
# "질의 문자열에 문서 이름 글자가 50% 이상 겹쳐야" 통과시키므로(줄임말이
# SLANG_DICTIONARY로 치환된 뒤 검색되는 정상 흐름을 흉내낸 것), 질의에 실제
# 문서 이름을 그대로 포함시켜야 한다 — comp/playstyle은 이 필터 대상이 아니라
# 조합명을 안 담아도 된다(hybrid_search.py NAME_OVERLAP_DOC_TYPES 참고).
SAMPLE_CASES = [
    pytest.param("지금 메타 조합 추천해줘", 0, "리롤 요네", id="comp"),
    pytest.param("힘의 마법공학 증강체 효과 알려줘", 1, "힘의 마법공학", id="augment"),
]


def test_real_pipeline_wiring_classify_search_postprocess(
    seeded_session: Session,
) -> None:
    """의도분류(CHAT-01 real)→검색(CHAT-02 real)→생성→후처리(CHAT-06 real)가
    전부 실제 구현으로 연결됐을 때, 실제로 검색된 문서 이름을 인용한 답변은
    근거검증 경고 없이 그대로 나오는지 확인한다(배선 자체의 정상 동작 증명)."""

    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "'리롤 요네'는 이번 패치 S티어 조합입니다."

    tokens = list(
        generate_answer_stream(
            seeded_session,
            SESSION_ID,
            "지금 메타 조합 추천해줘",
            embed_fn=lambda text: _one_hot(0),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: classify_intent(text, _fail_if_called),
            search_fn=hybrid_search,
            web_search_fn=lambda text: [],
            stream_fn=fake_stream_fn,
        )
    )

    answer = " ".join(tokens)
    assert UNVERIFIED_NAME_WARNING not in answer


@pytest.mark.parametrize("query, embed_index, real_name", SAMPLE_CASES)
def test_grounded_citation_of_real_search_result_passes_across_doc_types(
    seeded_session: Session, query: str, embed_index: int, real_name: str
) -> None:
    def fake_stream_fn(system_prompt: str, user_message: str):
        yield f"'{real_name}'을(를) 추천합니다."

    tokens = list(
        generate_answer_stream(
            seeded_session,
            SESSION_ID,
            query,
            embed_fn=lambda text: _one_hot(embed_index),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: classify_intent(text, _fail_if_called),
            search_fn=hybrid_search,
            web_search_fn=lambda text: [],
            stream_fn=fake_stream_fn,
        )
    )

    assert UNVERIFIED_NAME_WARNING not in " ".join(tokens)


@pytest.mark.parametrize("query, embed_index, real_name", SAMPLE_CASES)
def test_ungrounded_citation_triggers_warning_despite_real_search_results(
    seeded_session: Session, query: str, embed_index: int, real_name: str
) -> None:
    """검색 자체는 실제 문서를 정상적으로 찾아오더라도, LLM이 그 문서에
    없는 이름을 인용하면(예: 지어낸 이름) 근거검증 경고가 붙어야 한다."""

    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "'존재하지않는가짜이름'을(를) 추천합니다."

    tokens = list(
        generate_answer_stream(
            seeded_session,
            SESSION_ID,
            query,
            embed_fn=lambda text: _one_hot(embed_index),
            offtopic_confirm_fn=lambda text: False,
            classify_fn=lambda text: classify_intent(text, _fail_if_called),
            search_fn=hybrid_search,
            web_search_fn=lambda text: [],
            stream_fn=fake_stream_fn,
        )
    )

    assert UNVERIFIED_NAME_WARNING in " ".join(tokens)


def test_second_session_same_query_hits_cache_and_skips_real_pipeline(
    seeded_session: Session,
) -> None:
    """캐시(CHAT-08)는 세션이 아니라 질문 문장+패치 버전으로 키가 정해지지만,
    "첫 턴"(해당 session_id에 이전 chat_logs가 없음)일 때만 조회한다(같은
    세션 내 후속 턴은 문맥 유지를 위해 의도적으로 캐시를 건너뜀 —
    test_chat08_cache.py의 test_subsequent_turn_ignores_cache_even_if_entry_exists
    참고). 그래서 "동일 질문을 새 세션(다른 사용자)이 다시 물어보면 캐시가
    히트한다"를 검증하려면 두 번째 호출은 다른 session_id를 써야 한다."""
    search_calls = {"n": 0}

    def counting_search_fn(db, intent, patch_version, embedding):
        search_calls["n"] += 1
        return hybrid_search(db, intent, patch_version, embedding)

    def fake_stream_fn(system_prompt: str, user_message: str):
        yield "'리롤 요네'는 이번 패치 S티어 조합입니다."

    def run(session_id: str) -> list[str]:
        return list(
            generate_answer_stream(
                seeded_session,
                session_id,
                "지금 메타 조합 추천해줘",
                embed_fn=lambda text: _one_hot(0),
                offtopic_confirm_fn=lambda text: False,
                classify_fn=lambda text: classify_intent(text, _fail_if_called),
                search_fn=counting_search_fn,
                web_search_fn=lambda text: [],
                stream_fn=fake_stream_fn,
            )
        )

    first = run("11111111-1111-1111-1111-111111111111")
    assert search_calls["n"] == 1
    second = run("22222222-2222-2222-2222-222222222222")
    assert search_calls["n"] == 1  # 캐시 히트라 검색이 다시 호출되지 않음
    assert first == second
