"""CHAT-06 pytest(TEST-00 시나리오 그대로 옮김, docs/test-scenarios.md CHAT-06):
근거검증, Legend 승률 이중 방어, 상대 닉네임 마스킹 — 각각 결정론적 문자열
매칭/정규식 기반이며 LLM 재호출 없음."""

from __future__ import annotations

from db.models import MetaDocumentEmbedding
from services.chat_postprocessing import (
    UNVERIFIED_NAME_WARNING,
    mask_augment_win_rate_leak,
    mask_opponent_nicknames,
    postprocess_answer,
    strip_internal_doc_marker_leak,
    verify_grounding,
)


def _doc(
    name: str | None = None,
    champion: str | None = None,
    champions: list[str] | None = None,
) -> MetaDocumentEmbedding:
    metadata: dict = {}
    if name is not None:
        metadata["name"] = name
    if champion is not None:
        metadata["champion"] = champion
    if champions is not None:
        metadata["champions"] = champions
    return MetaDocumentEmbedding(doc_metadata=metadata)


# ---- TEST-00 CHAT-06 #1: 검색 문서에 실재하는 이름만 언급 -> 그대로 통과 --------


def test_verify_grounding_passes_when_quoted_name_exists_in_docs() -> None:
    answer = "17.8 패치 기준으로는 '이즈리얼 캐리' 조합이 강세입니다."
    docs = [_doc(name="이즈리얼 캐리")]

    result = verify_grounding(answer, docs)

    assert result == answer
    assert UNVERIFIED_NAME_WARNING not in result


# ---- TEST-00 CHAT-06 #2: 검색 문서에 없는 이름(할루시네이션) -> 경고 문구 추가 ---


def test_verify_grounding_appends_warning_when_quoted_name_not_in_docs() -> None:
    answer = "17.8 패치 기준으로는 '환상의 5티어 조합'이 강세입니다."
    docs = [_doc(name="이즈리얼 캐리")]

    result = verify_grounding(answer, docs)

    assert result.startswith(answer)
    assert UNVERIFIED_NAME_WARNING in result


def test_verify_grounding_checks_champion_name_from_item_build_metadata() -> None:
    answer = "'이즈리얼' 아이템은 무한의 대검을 추천드려요."
    docs = [_doc(champion="이즈리얼")]

    result = verify_grounding(answer, docs)

    assert result == answer


# CHAT-18(PM 제보 2026-08-12): comp/playstyle 문서엔 조합 이름만 있고 구성
# 챔피언 개별 이름이 없어, 8번 규칙대로 정상 인용된 챔피언 이름도 항상
# "확인되지 않음" 오탐을 냈다(CHAT-13이 item_build에 이미 고친 것과 동일한
# 구조적 문제) — "champions" 목록 키로 보강.
def test_verify_grounding_checks_champion_names_from_comp_metadata() -> None:
    answer = "'별돌보미 자야' 조합은 '자야'와 '진'을 캐리로 운영합니다."
    docs = [_doc(name="별돌보미 자야", champions=["자야", "진", "룰루"])]

    result = verify_grounding(answer, docs)

    assert result == answer
    assert UNVERIFIED_NAME_WARNING not in result


def test_verify_grounding_no_quotes_at_all_passes_through() -> None:
    answer = "TFT는 재밌는 게임입니다."
    result = verify_grounding(answer, [])
    assert result == answer


def test_verify_grounding_mixed_quotes_flags_if_any_unverified() -> None:
    answer = "'이즈리얼 캐리'와 '환상의 5티어 조합' 둘 다 강세입니다."
    docs = [_doc(name="이즈리얼 캐리")]

    result = verify_grounding(answer, docs)

    assert UNVERIFIED_NAME_WARNING in result


# ---- TEST-00 CHAT-06 #3: 전처리가 정상 작동해 승률 관련 숫자가 없는 경우 --------


def test_mask_augment_win_rate_leak_no_op_when_no_win_rate_mentioned() -> None:
    answer = "'별의 인도자' 증강체는 인기가 많습니다."
    assert mask_augment_win_rate_leak(answer) == answer


# ---- TEST-00 CHAT-06 #4: 후처리 정규식이 승률 숫자 패턴을 탐지해 제거/마스킹 ----


def test_mask_augment_win_rate_leak_masks_percentage_near_win_rate_word() -> None:
    answer = "이 증강체는 승률 62%로 우수합니다."

    result = mask_augment_win_rate_leak(answer)

    assert "62%" not in result
    assert "승률 정보 비공개" in result


def test_mask_augment_win_rate_leak_masks_multiple_occurrences() -> None:
    answer = "A는 승률 62%, B는 승률 40.5%입니다."

    result = mask_augment_win_rate_leak(answer)

    assert "62%" not in result
    assert "40.5%" not in result


# ---- 프롬프트 내부 구획 표시("[검색된 문서]") 누출 제거(2026-08-07 운영 관측) ----


def test_strip_internal_doc_marker_leak_removes_marker_and_empty_citation() -> None:
    answer = "17.8 패치 기준입니다. \n(참고: [검색된 문서])"

    result = strip_internal_doc_marker_leak(answer)

    assert "[검색된 문서]" not in result
    assert "(참고:" not in result
    assert result == "17.8 패치 기준입니다."


def test_strip_internal_doc_marker_leak_no_op_when_marker_absent() -> None:
    answer = "17.8 패치 기준입니다. (참고: 조합 정보)"
    assert strip_internal_doc_marker_leak(answer) == answer


def test_postprocess_answer_removes_internal_doc_marker_leak() -> None:
    answer = "17.8 패치 기준입니다. \n(참고: [검색된 문서])"

    result = postprocess_answer(answer, [])

    assert "[검색된 문서]" not in result
    assert result == "17.8 패치 기준입니다."


# ---- TEST-00 CHAT-06 #5: 상대 닉네임 마스킹 --------------------------------------


def test_mask_opponent_nicknames_replaces_with_placeholder() -> None:
    answer = "상대방 '아빠한테넘겨봐'님은 재도전 조합을 썼습니다."

    result = mask_opponent_nicknames(answer, ["아빠한테넘겨봐"])

    assert "아빠한테넘겨봐" not in result
    assert "상대 플레이어" in result


def test_mask_opponent_nicknames_replaces_all_occurrences() -> None:
    answer = (
        "아빠한테넘겨봐님이 이겼고, 아빠한테넘겨봐님의 조합은 이즈리얼 캐리였습니다."
    )

    result = mask_opponent_nicknames(answer, ["아빠한테넘겨봐"])

    assert result.count("상대 플레이어") == 2
    assert "아빠한테넘겨봐" not in result


def test_mask_opponent_nicknames_no_match_leaves_text_unchanged() -> None:
    answer = "정상적인 답변입니다."
    assert mask_opponent_nicknames(answer, ["없는닉네임"]) == answer


def test_mask_opponent_nicknames_empty_list_leaves_text_unchanged() -> None:
    answer = "정상적인 답변입니다."
    assert mask_opponent_nicknames(answer, []) == answer


# ---- postprocess_answer: 전체 파이프라인 통합 ------------------------------------


def test_postprocess_answer_applies_win_rate_mask_and_grounding_together() -> None:
    answer = "'환상의 5티어 조합'은 승률 62%로 우수합니다."
    docs = [_doc(name="이즈리얼 캐리")]

    result = postprocess_answer(answer, docs)

    assert "62%" not in result
    assert UNVERIFIED_NAME_WARNING in result


def test_postprocess_answer_with_opponent_nicknames() -> None:
    # 프롬프트 규칙 8은 조합/챔피언/아이템/증강체만 인용하라고 지시하므로,
    # 정상적인 LLM 출력이라면 상대 닉네임은 인용부호 없이 등장한다.
    answer = "상대 아빠한테넘겨봐님은 '이즈리얼 캐리' 조합을 사용했습니다."
    docs = [_doc(name="이즈리얼 캐리")]

    result = postprocess_answer(answer, docs, opponent_nicknames=["아빠한테넘겨봐"])

    assert "아빠한테넘겨봐" not in result
    assert "상대 플레이어" in result
    assert UNVERIFIED_NAME_WARNING not in result
