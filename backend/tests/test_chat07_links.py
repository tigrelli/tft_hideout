"""CHAT-07 pytest(WBS 테스트 요구사항: 답변 내 조합/아이템/증강체 언급 시 정확한
링크 삽입, 존재하지 않는 id 오탐 케이스 처리 확인)."""

from __future__ import annotations

from db.models import MetaDocumentEmbedding
from services.chat_links import insert_links


def _doc(
    doc_type: str,
    source_table: str,
    source_id: int,
    name: str | None = None,
    champion: str | None = None,
) -> MetaDocumentEmbedding:
    metadata: dict = {}
    if name is not None:
        metadata["name"] = name
    if champion is not None:
        metadata["champion"] = champion
    return MetaDocumentEmbedding(
        doc_type=doc_type,
        source_table=source_table,
        source_id=source_id,
        doc_metadata=metadata,
    )


# ---- 조합: 개별 상세 페이지(/comps/{comp_id}) --------------------------------


def test_comp_mention_links_to_comp_detail_page() -> None:
    answer = "17.8 패치 기준으로는 '이즈리얼 캐리' 조합이 강세입니다."
    docs = [_doc("comp", "comps", 42, name="이즈리얼 캐리")]

    result = insert_links(answer, docs)

    assert "[이즈리얼 캐리](/comps/42)" in result
    assert "'이즈리얼 캐리'" not in result


def test_playstyle_doc_also_links_to_comp_detail_page() -> None:
    """playstyle doc_type도 source_table은 comps라 동일하게 /comps/{id}로 연결."""
    answer = "'아이오니아 마법사' 조합의 플레이 스타일을 설명드릴게요."
    docs = [_doc("playstyle", "comps", 7, name="아이오니아 마법사")]

    result = insert_links(answer, docs)

    assert "[아이오니아 마법사](/comps/7)" in result


# ---- 아이템 빌드/증강체: 개별 상세 페이지 없음 -> 목록 페이지 -----------------


def test_item_build_mention_links_to_item_builds_list_page() -> None:
    answer = "'이즈리얼' 아이템은 무한의 대검을 추천드려요."
    docs = [_doc("item_build", "champion_item_builds", 5, champion="이즈리얼")]

    result = insert_links(answer, docs)

    assert "[이즈리얼](/items/builds)" in result


def test_augment_mention_links_to_augments_list_page() -> None:
    answer = "'별의 인도자' 증강체가 인기가 많습니다."
    docs = [_doc("augment", "augments", 9, name="별의 인도자")]

    result = insert_links(answer, docs)

    assert "[별의 인도자](/augments)" in result


# ---- 오탐 방지: 검색 문서에 없는 이름은 링크를 만들지 않음 --------------------


def test_unmatched_quoted_name_is_left_unlinked() -> None:
    answer = "'환상의 5티어 조합'은 강력합니다."
    docs = [_doc("comp", "comps", 1, name="이즈리얼 캐리")]

    result = insert_links(answer, docs)

    assert result == answer
    assert "](/comps/" not in result


def test_no_quotes_at_all_passes_through_unchanged() -> None:
    answer = "TFT는 재밌는 게임입니다."
    assert insert_links(answer, []) == answer


# ---- 여러 언급 -----------------------------------------------------------------


def test_multiple_mentions_of_same_name_all_replaced() -> None:
    answer = "'이즈리얼 캐리' 조합은 좋습니다. 다시 말해 '이즈리얼 캐리'가 강합니다."
    docs = [_doc("comp", "comps", 3, name="이즈리얼 캐리")]

    result = insert_links(answer, docs)

    assert result.count("[이즈리얼 캐리](/comps/3)") == 2


def test_mixed_verified_and_unverified_names() -> None:
    answer = "'이즈리얼 캐리'는 검증되지만 '환상의 5티어 조합'은 아닙니다."
    docs = [_doc("comp", "comps", 3, name="이즈리얼 캐리")]

    result = insert_links(answer, docs)

    assert "[이즈리얼 캐리](/comps/3)" in result
    assert "'환상의 5티어 조합'" in result
