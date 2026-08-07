"""CHAT-13 pytest(WBS 테스트 요구사항: _known_names()/verify_grounding()이 아이템
이름을 인식해 경고를 안 붙이는지, 여전히 미확인 이름은 경고가 붙는지,
insert_links()가 챔피언 이름을 champion_id 필터 링크로 치환하고 아이템 이름은
링크하지 않는지 확인).

CHAT-06 verify_grounding()의 _known_names()가 item_build 문서의 champion 키만
읽고 아이템 이름은 어디에도 없어(전엔 doc_metadata에 아이템 목록 자체가 없었음),
8번 규칙대로 정상 인용된 아이템 이름조차 항상 "확인되지 않았다" 경고를 유발하던
구조적 오탐을 수정한다(PM 제보 2026-08-08, CHAT-12 작업결과 참고).

2026-08-08 PM 실사용 재검증 중 후속 제보 2건 반영: (1) 아이템 이름은 클릭해도
챔피언 선택 없이 목록 페이지로만 가서 오히려 혼란스러우니 링크하지 말 것,
(2) 챔피언 이름은 클릭 시 그 챔피언으로 필터된 아이템 빌드 화면으로 이동해야
하는데(champion_id 쿼리) item_build 문서에서 온 챔피언은 필터 없는 URL로만
갔던 문제 — 둘 다 아래 테스트에서 확인."""

from __future__ import annotations

from db.models import MetaDocumentEmbedding
from services.chat_links import insert_links
from services.chat_postprocessing import UNVERIFIED_NAME_WARNING, verify_grounding


def _item_build_doc(
    champion: str,
    items: list[str],
    champion_id: int | None = 1,
    source_id: int = 1,
) -> MetaDocumentEmbedding:
    metadata: dict = {"champion": champion, "items": items}
    if champion_id is not None:
        metadata["champion_id"] = champion_id
    return MetaDocumentEmbedding(
        doc_type="item_build",
        source_table="champion_item_builds",
        source_id=source_id,
        doc_metadata=metadata,
    )


# ---- verify_grounding() ----------------------------------------------------


def test_verify_grounding_recognizes_item_names_from_item_build_metadata() -> None:
    answer = "'이즈리얼'에게는 '무한의 대검'과 '쇼진의 창'을 추천드려요."
    docs = [_item_build_doc("이즈리얼", ["무한의 대검", "쇼진의 창"])]

    result = verify_grounding(answer, docs)

    assert result == answer
    assert UNVERIFIED_NAME_WARNING not in result


def test_verify_grounding_still_warns_for_item_name_not_in_any_doc() -> None:
    answer = "'이즈리얼'에게는 '환상의 전설템'을 추천드려요."
    docs = [_item_build_doc("이즈리얼", ["무한의 대검"])]

    result = verify_grounding(answer, docs)

    assert UNVERIFIED_NAME_WARNING in result


def test_verify_grounding_item_names_across_multiple_docs() -> None:
    answer = "'바드'는 '보석 건틀릿', '빅토르'는 '라바돈의 죽음모자'를 씁니다."
    docs = [
        _item_build_doc("바드", ["보석 건틀릿"], source_id=1),
        _item_build_doc("빅토르", ["라바돈의 죽음모자"], source_id=2),
    ]

    result = verify_grounding(answer, docs)

    assert result == answer


# ---- insert_links() ---------------------------------------------------------


def test_insert_links_does_not_link_quoted_item_names() -> None:
    """PM 제보(2026-08-08): 아이템 이름이 링크되면 클릭해도 챔피언 선택 없이
    목록 페이지로만 가서 혼란스럽다 — 아이템 이름은 근거검증 대상일 뿐 링크
    대상이 아니어야 한다."""
    answer = "코어 아이템은 '보석 건틀릿'입니다."
    docs = [_item_build_doc("바드", ["보석 건틀릿"])]

    result = insert_links(answer, docs)

    assert result == answer
    assert "[보석 건틀릿]" not in result


def test_insert_links_leaves_unknown_item_name_unlinked() -> None:
    answer = "'환상의 전설템'을 추천합니다."
    docs = [_item_build_doc("바드", ["보석 건틀릿"])]

    result = insert_links(answer, docs)

    assert result == answer
    assert "[환상의 전설템]" not in result


def test_insert_links_quoted_champion_name_uses_champion_id_filter() -> None:
    """PM 제보(2026-08-08): item_build 문서에서 온 챔피언 링크가 champion_id
    없이 `/items/builds`로만 가서 클릭해도 챔피언이 선택되지 않았다."""
    answer = "'이즈리얼'에게는 무한의 대검을 추천드려요."
    docs = [_item_build_doc("이즈리얼", ["무한의 대검"], champion_id=42)]

    result = insert_links(answer, docs)

    assert "[이즈리얼](/items/builds?champion_id=42)" in result


def test_insert_links_falls_back_to_unfiltered_url_without_champion_id() -> None:
    """champion_id가 없는(예: 구 데이터) item_build 문서는 기존처럼 필터 없는
    목록 페이지로 연결된다(하위호환)."""
    answer = "'이즈리얼'에게는 무한의 대검을 추천드려요."
    docs = [_item_build_doc("이즈리얼", ["무한의 대검"], champion_id=None)]

    result = insert_links(answer, docs)

    assert "[이즈리얼](/items/builds)" in result


def test_insert_links_recovers_unquoted_champion_name_at_list_item_start() -> None:
    """PM 제보(2026-08-08): CHAT-12 목록 서식(`- 챔피언명: 아이템...`)에서
    모델이 챔피언명을 작은따옴표로 인용하지 않아 링크가 아예 안 생기는 경우가
    실제로 있었다 — 목록 항목 맨 앞(콜론 앞)은 항상 챔피언명이 오는 구조이므로
    인용 없이도 인식해야 한다."""
    answer = (
        "빌드를 안내드릴게요.\n- 이즈리얼: 무한의 대검, 쇼진의 창\n- 바드: 보석 건틀릿"
    )
    docs = [
        _item_build_doc(
            "이즈리얼", ["무한의 대검", "쇼진의 창"], champion_id=42, source_id=1
        ),
        _item_build_doc("바드", ["보석 건틀릿"], champion_id=7, source_id=2),
    ]

    result = insert_links(answer, docs)

    assert (
        "- [이즈리얼](/items/builds?champion_id=42): 무한의 대검, 쇼진의 창" in result
    )
    assert "- [바드](/items/builds?champion_id=7): 보석 건틀릿" in result


def test_insert_links_leading_name_pattern_does_not_link_items_after_colon() -> None:
    """목록 항목 맨 앞 보정 로직이 콜론 뒤의 아이템 나열까지 건드리지 않는지
    확인(아이템은 여전히 링크 대상이 아님)."""
    answer = "- 이즈리얼: 보석 건틀릿, 무한의 대검"
    docs = [_item_build_doc("이즈리얼", ["보석 건틀릿", "무한의 대검"], champion_id=42)]

    result = insert_links(answer, docs)

    assert "[보석 건틀릿]" not in result
    assert "[무한의 대검]" not in result
