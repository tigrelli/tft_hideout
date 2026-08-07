"""CHAT-06: 출력 후처리(설계서 4.4.3). LLM이 생성을 마친 "완성된 답변 문자열"에
대해서만 동작한다(부분 토큰 단위로는 정규식 검사가 신뢰할 수 없어 chat_stream.py가
스트림을 전부 버퍼링한 뒤 이 모듈을 호출한다).

- 근거 검증: 답변에서 작은따옴표로 인용된 고유명사(프롬프트 규칙 8, CHAT-03)가
  검색 문서 메타데이터에 실재하는지 문자열 매칭으로 확인(설계서 4.4.3, LLM 자기
  재검증이 아니라 결정론적 사후 점검 — CHAT-06 작업결과 참고)
- Legend 증강체 승률 이중 방어: 전처리(프롬프트 컨텍스트 구성)가 win_rate를
  이미 제외했더라도, 후처리에서 '승률' 주변 숫자 패턴을 한 번 더 스캔해 제거
- 프라이버시 마스킹: 상대 플레이어 닉네임을 정규식으로 마스킹(재사용 유틸 —
  PGA-09/CHAT-10에서 실제 닉네임 목록과 함께 쓰일 예정, 현재 일반 Q&A 흐름에는
  닉네임 데이터 자체가 없어 호출되지 않음)
"""

from __future__ import annotations

import re

from db.models import MetaDocumentEmbedding

UNVERIFIED_NAME_WARNING = (
    "(주의: 위 답변 중 일부 명칭은 검색된 문서에서 확인되지 않았습니다.)"
)

_QUOTED_NAME_PATTERN = re.compile(r"'([^']+)'")
_WIN_RATE_LEAK_PATTERN = re.compile(r"승률[^%\n]{0,10}\d+(\.\d+)?%")
_WIN_RATE_MASK_REPLACEMENT = "승률 정보 비공개"

# 프롬프트 규칙 5(근거 문서 종류를 한 줄로 밝히라)를 지키려다 LLM이 few-shot의
# "(참고: 조합 정보)" 형식 대신, 프롬프트 자체에 반복 등장하는 내부 구획 표시
# "[검색된 문서]"를 그대로 베껴 답변에 남기는 경우가 실제 운영에서 관측됨
# (2026-08-07, "17.8 패치 기준입니다. (참고: [검색된 문서])"). 실제 문서를
# 가리키지 않는 문자열이라 사용자에게 혼란만 주므로 후처리에서 제거한다
# (prompt_assembly.py 규칙 5 문구 보강과 함께 이중 방어).
_INTERNAL_DOC_MARKER = "[검색된 문서]"
_EMPTY_CITATION_PATTERN = re.compile(r"\(\s*참고\s*:\s*\)")

# retrieved_docs의 doc_metadata 중 "이름"으로 취급할 키 — doc_type별로 다름
# (comp/playstyle/augment는 name, item_build는 champion. DATA-11 collect_chunks 참고)
_NAME_METADATA_KEYS = ("name", "champion")
# item_build는 챔피언 하나에 아이템이 여러 개라 단일 문자열이 아니라 목록으로
# 실려 있다(CHAT-13, DATA-11 collect_chunks의 "items" 키 참고) — 아이템 이름이
# 여기 없으면 8번 규칙대로 정상 인용된 아이템도 항상 근거검증 경고를 유발한다
# (PM 제보 2026-08-08, CHAT-12 작업결과).
_NAME_LIST_METADATA_KEYS = ("items",)


def _known_names(retrieved_docs: list[MetaDocumentEmbedding]) -> set[str]:
    names: set[str] = set()
    for doc in retrieved_docs:
        metadata = doc.doc_metadata or {}
        for key in _NAME_METADATA_KEYS:
            value = metadata.get(key)
            if value:
                names.add(value)
        for key in _NAME_LIST_METADATA_KEYS:
            for value in metadata.get(key) or []:
                names.add(value)
    return names


def verify_grounding(
    answer_text: str, retrieved_docs: list[MetaDocumentEmbedding]
) -> str:
    """답변에서 작은따옴표로 인용된 이름이 전부 검색 문서에 있으면 그대로 반환.
    검색 문서에 없는 인용이 하나라도 있으면 경고 문구를 답변 끝에 덧붙인다
    (TEST-00: 재생성 또는 경고 문구 중 후자 채택 — 재시도 없이 결정론적으로 처리)."""
    quoted = _QUOTED_NAME_PATTERN.findall(answer_text)
    if not quoted:
        return answer_text
    known = _known_names(retrieved_docs)
    if all(name in known for name in quoted):
        return answer_text
    return f"{answer_text}\n\n{UNVERIFIED_NAME_WARNING}"


def mask_augment_win_rate_leak(answer_text: str) -> str:
    """'승률' 뒤 10자 이내에 나오는 퍼센트 숫자를 마스킹한다(Legend 증강체 승률
    비노출 정책의 두 번째 방어선 — 첫 번째 방어선은 프롬프트 컨텍스트 구성 단계에서
    win_rate 필드 자체를 제외하는 것, policies.md 1번)."""
    return _WIN_RATE_LEAK_PATTERN.sub(_WIN_RATE_MASK_REPLACEMENT, answer_text)


def strip_internal_doc_marker_leak(answer_text: str) -> str:
    """LLM이 프롬프트 내부 구획 표시 `[검색된 문서]`를 실제 문서 이름인 것처럼
    답변에 그대로 옮긴 경우 제거한다. 마커만 지우면 `(참고: )`처럼 빈 괄호가
    남을 수 있어 함께 정리한다."""
    if _INTERNAL_DOC_MARKER not in answer_text:
        return answer_text
    text = answer_text.replace(_INTERNAL_DOC_MARKER, "")
    text = _EMPTY_CITATION_PATTERN.sub("", text)
    return text.rstrip()


def mask_opponent_nicknames(answer_text: str, nicknames: list[str]) -> str:
    """주어진 닉네임 목록을 답변에서 '상대 플레이어'로 치환한다(policies.md 2번).
    LLM 생성 이후 한 번 더 마스킹해, 모델이 프롬프트 규칙을 놓쳤을 가능성을
    후처리 단계에서 재차 차단한다."""
    masked = answer_text
    for nickname in nicknames:
        if not nickname:
            continue
        masked = re.sub(re.escape(nickname), "상대 플레이어", masked)
    return masked


def postprocess_answer(
    answer_text: str,
    retrieved_docs: list[MetaDocumentEmbedding],
    *,
    opponent_nicknames: list[str] | None = None,
) -> str:
    """CHAT-06 후처리 파이프라인 전체(순서: 내부 마커 제거 → 승률 마스킹 →
    닉네임 마스킹 → 근거검증). 근거검증을 마지막에 두는 이유: 마스킹으로
    텍스트가 바뀐 뒤에도 인용부호 위치는 그대로 유지되므로 순서를 바꿔도
    결과는 같지만, 경고문구가 붙는다면 마스킹이 전부 끝난 뒤의 최종 답변에
    붙는 게 자연스럽다."""
    text = strip_internal_doc_marker_leak(answer_text)
    text = mask_augment_win_rate_leak(text)
    if opponent_nicknames:
        text = mask_opponent_nicknames(text, opponent_nicknames)
    return verify_grounding(text, retrieved_docs)
