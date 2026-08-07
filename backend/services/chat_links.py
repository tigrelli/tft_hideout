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
참고 — champion doc_type의 source_id가 곧 champion_id라 그대로 재사용 가능)."""

from __future__ import annotations

import re

from db.models import MetaDocumentEmbedding

_QUOTED_NAME_PATTERN = re.compile(r"'([^']+)'")

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
        for key in ("name", "champion"):
            value = metadata.get(key)
            if value and value not in mapping:
                mapping[value] = _link_target(doc)
    return mapping


def insert_links(answer_text: str, retrieved_docs: list[MetaDocumentEmbedding]) -> str:
    """인용된 이름이 검색 문서에 실재하면 마크다운 링크 `[이름](url)`로 치환한다.
    검색 문서에 없는(=CHAT-06이 이미 경고 처리한) 이름은 링크를 만들 id 자체가
    없으므로 그대로 둔다(오탐 방지 — 존재하지 않는 id로 링크를 만들지 않음)."""
    name_to_url = _name_to_url(retrieved_docs)

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        url = name_to_url.get(name)
        if url is None:
            return match.group(0)
        return f"[{name}]({url})"

    return _QUOTED_NAME_PATTERN.sub(_replace, answer_text)
