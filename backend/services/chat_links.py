"""CHAT-07: 답변에서 검증된(CHAT-06 근거검증을 통과한) 고유명사를 상세 페이지
링크로 치환한다. 조합 링크는 `/comps?id={comp_id}` 쿼리스트링 형식(FE-04, PM 결정
2026-08-04 — 정적 export 특성상 패치마다 comp_id가 전부 새로 생겨 경로 방식이면
재배포 전까지 새 조합 링크가 깨짐, glossary.md 참고). 아이템 빌드·증강체는 IA상
개별 상세 페이지가 없어 각각의 목록 페이지(`/items/builds`, `/augments`)로 연결한다.
챔피언(champion doc_type, 2026-08-07 신설)도 개별 상세 페이지가 없지만, 목록
페이지로만 보내면 어떤 챔피언을 언급한 답변인지 화면에서 다시 찾아야 해서
(PM 피드백 — "1코스트 챔피언은?" 답변의 챔피언 링크가 전부 홈으로만 감)
`/items/builds?champion_id={champion_id}`로 보내 해당 챔피언 필터가 걸린
화면으로 바로 연결한다(FE 쪽에 이미 있는 URL 동기화 기능, item-builds-view.tsx
참고 — champion doc_type의 source_id가 곧 champion_id라 그대로 재사용 가능).

CHAT-13(2026-08-08) 후속 수정: item_build 문서에서 온 챔피언 이름도 동일하게
`champion_id` 필터 URL로 연결한다(전엔 item_build 문서의 champion 키가
`_link_target`을 거쳐 항상 필터 없는 `/items/builds`로만 갔음 — PM이 "챔피언을
클릭해도 챔피언이 선택 안 됨"으로 제보). 반대로 아이템 이름은 CHAT-13에서
근거검증(`_known_names`) 목적으로만 인식하게 했을 뿐 링크 대상은 아니었는데,
실제로 링크가 걸려 "선택된 챔피언 없이 아이템 목록 페이지로만 이동"하는 게
오히려 혼란스럽다는 PM 피드백으로 아이템 이름은 링크에서 제외한다."""

from __future__ import annotations

import re

from db.models import MetaDocumentEmbedding

_QUOTED_NAME_PATTERN = re.compile(r"'([^']+)'")
# CHAT-12 서식 규칙(9번)이 만드는 '- 챔피언명: 아이템1, 아이템2' 목록에서, 모델이
# 챔피언명을 작은따옴표로 인용하지 않는 경우가 실제로 관측돼(2026-08-08 PM 제보)
# 위 인용 패턴만으로는 링크가 안 생기는 경우가 있었다. 목록 항목 맨 앞(콜론 앞)은
# 항상 챔피언명이 오는 구조적으로 안전한 위치라 인용 여부와 무관하게 추가로 인식한다.
_LIST_ITEM_LEADING_NAME_PATTERN = re.compile(r"^-\s+([^:\n]+?):", re.MULTILINE)
_CHAMPION_LINK_ID_PATTERN = re.compile(r"/items/builds\?champion_id=(\d+)")

# doc_type -> IA 화면 URL(개별 상세 페이지가 없는 유형은 목록 페이지로 연결)
_LIST_PAGE_URLS: dict[str, str] = {
    "item_build": "/items/builds",
    "augment": "/augments",
}


def _link_target(doc: MetaDocumentEmbedding) -> str:
    if doc.source_table == "comps":
        return f"/comps?id={doc.source_id}"
    if doc.doc_type == "champion":
        return f"/items/builds?champion_id={doc.source_id}"
    return _LIST_PAGE_URLS.get(doc.doc_type, "/")


def _name_to_url(retrieved_docs: list[MetaDocumentEmbedding]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for doc in retrieved_docs:
        metadata = doc.doc_metadata or {}
        name = metadata.get("name")
        if name and name not in mapping:
            mapping[name] = _link_target(doc)
        champion = metadata.get("champion")
        if champion and champion not in mapping:
            champion_id = metadata.get("champion_id")
            if doc.doc_type == "item_build" and champion_id is not None:
                mapping[champion] = f"/items/builds?champion_id={champion_id}"
            else:
                mapping[champion] = _link_target(doc)
        # 아이템 이름은 여기서 의도적으로 매핑하지 않는다(위 모듈 docstring 참고,
        # CHAT-06 근거검증에서만 "알려진 이름"으로 쓰이고 링크 대상은 아님).
    return mapping


def _link_list_item_leading_names(text: str, name_to_url: dict[str, str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name.startswith("["):
            return match.group(0)  # 이미 인용 패턴으로 링크 처리됨
        url = name_to_url.get(name.strip())
        if url is None:
            return match.group(0)
        return f"- [{name.strip()}]({url}):"

    return _LIST_ITEM_LEADING_NAME_PATTERN.sub(_replace, text)


def insert_links(answer_text: str, retrieved_docs: list[MetaDocumentEmbedding]) -> str:
    """인용된 이름이 검색 문서에 실재하면 마크다운 링크 `[이름](url)`로 치환한다.
    검색 문서에 없는(=CHAT-06이 이미 경고 처리한) 이름은 링크를 만들 id 자체가
    없으므로 그대로 둔다(오탐 방지 — 존재하지 않는 id로 링크를 만들지 않음).
    작은따옴표 인용을 1차로 처리한 뒤, 목록 항목 맨 앞의 챔피언명은 인용 누락
    시에도 보정한다(위 `_LIST_ITEM_LEADING_NAME_PATTERN` 참고)."""
    name_to_url = _name_to_url(retrieved_docs)

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        url = name_to_url.get(name)
        if url is None:
            return match.group(0)
        return f"[{name}]({url})"

    linked = _QUOTED_NAME_PATTERN.sub(_replace, answer_text)
    return _link_list_item_leading_names(linked, name_to_url)


def extract_champion_ids_from_answer(answer_text: str) -> list[int]:
    """직전 봇 답변에 심어진 챔피언 링크(`_link_target`이 만든
    `/items/builds?champion_id={id}`의 역방향)에서 champion_id를 그대로
    뽑아낸다. 후속질문이 "이 챔피언들"처럼 대명사로 직전 답변을 가리킬 때,
    의미 검색(임베딩 유사도)으로 근사하면 무관한 챔피언이 섞이거나 언급된
    챔피언이 빠지는 문제가 실제로 확인됨(2026-08-07 PM 피드백) — 링크에
    이미 정확한 champion_id가 있으므로 hybrid_search.
    lookup_item_builds_by_champion_ids()가 의미 검색 대신 이 id로 정확히
    구조화 조회하는 데 쓴다. 중복은 처음 등장한 순서를 유지하며 제거."""
    seen: list[int] = []
    for match in _CHAMPION_LINK_ID_PATTERN.finditer(answer_text):
        champion_id = int(match.group(1))
        if champion_id not in seen:
            seen.append(champion_id)
    return seen
