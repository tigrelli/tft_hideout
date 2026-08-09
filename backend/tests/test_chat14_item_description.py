"""CHAT-14 pytest: item doc_type(DATA-19 description 기반)이 근거검증에는
인식되지만 링크 대상은 아닌지 확인. 하이브리드 검색 라우팅은
test_chat02_hybrid_search.py, SLANG_DICTIONARY 줄임말은
test_chat04_input_preprocessing.py에서 검증한다."""

from __future__ import annotations

from db.models import MetaDocumentEmbedding
from services.chat_links import insert_links
from services.chat_postprocessing import UNVERIFIED_NAME_WARNING, verify_grounding


def _item_doc(name: str, source_id: int = 1) -> MetaDocumentEmbedding:
    return MetaDocumentEmbedding(
        doc_type="item",
        source_table="items",
        source_id=source_id,
        doc_metadata={"name": name},
    )


def test_verify_grounding_recognizes_item_doc_type_name() -> None:
    answer = "'보석 건틀릿'은 치명타 확률을 올려주는 아이템입니다."
    docs = [_item_doc("보석 건틀릿")]

    result = verify_grounding(answer, docs)

    assert result == answer
    assert UNVERIFIED_NAME_WARNING not in result


def test_insert_links_does_not_link_item_doc_type_even_when_quoted() -> None:
    """PM 피드백(CHAT-13): 아이템 이름은 클릭해도 챔피언 선택 없이 목록
    페이지로만 가 혼란스러우니 링크 대상이 아니어야 한다 — item doc_type이
    champion/comp와 같은 "name" 메타데이터 키를 쓰더라도 예외로 유지된다."""
    answer = "'보석 건틀릿'은 치명타 확률을 올려주는 아이템입니다."
    docs = [_item_doc("보석 건틀릿")]

    result = insert_links(answer, docs)

    assert result == answer
    assert "[보석 건틀릿]" not in result
