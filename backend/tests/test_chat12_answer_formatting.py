"""CHAT-12 pytest(WBS 테스트 요구사항: SYSTEM_PROMPT_BASE에 목록 서식 규칙 문자열
포함 확인, few-shot 예시에 형식 반영 확인).

2026-08-08 PM 제보로 발견한 회귀(작업결과 문서 참고) 이후 강조(**) 지시는
제거했다 — 목록 항목에서 모델이 8번 규칙(작은따옴표 인용)을 별표로 대체하면
CHAT-07 링크 삽입(`'([^']+)'`만 인식)이 그 이름을 링크로 바꾸지 못해 챔피언/조합
링크가 통째로 사라졌기 때문. 아래 테스트는 이 회귀가 재발하지 않도록 강조 지시가
없고 목록 항목도 작은따옴표를 유지함을 명시적으로 검증한다."""

from __future__ import annotations

from services.intent_classification import (
    INTENT_AUGMENT_RECOMMENDATION,
    INTENT_COMP_RECOMMENDATION,
    INTENT_GENERAL_STRATEGY,
    INTENT_ITEM_RECOMMENDATION,
)
from services.prompt_assembly import (
    FEW_SHOT_EXAMPLES,
    SYSTEM_PROMPT_BASE,
    build_system_prompt,
)


def test_system_prompt_instructs_bullet_list_for_multiple_items() -> None:
    assert "- '로 시작하는 목록" in SYSTEM_PROMPT_BASE


def test_system_prompt_does_not_instruct_bold_emphasis() -> None:
    # 회귀 재발 방지: 별표 강조는 더 이상 지시하지 않는다(위 모듈 docstring 참고)
    assert "**" not in SYSTEM_PROMPT_BASE


def test_system_prompt_forbids_replacing_quotes_with_bold_in_lists() -> None:
    assert "별표(강조)로 대체하지 마라" in SYSTEM_PROMPT_BASE


def test_few_shot_examples_demonstrate_quoted_bullet_format_without_bold() -> None:
    assert "- '이즈리얼': " in FEW_SHOT_EXAMPLES
    assert "- '자야': " in FEW_SHOT_EXAMPLES
    assert "**" not in FEW_SHOT_EXAMPLES


def test_formatting_rule_applies_to_every_intent() -> None:
    # 9번 규칙은 SYSTEM_PROMPT_BASE에 있어 의도별 추가지시와 무관하게 항상 포함됨
    for intent in (
        INTENT_COMP_RECOMMENDATION,
        INTENT_ITEM_RECOMMENDATION,
        INTENT_AUGMENT_RECOMMENDATION,
        INTENT_GENERAL_STRATEGY,
    ):
        prompt = build_system_prompt(intent)
        assert "- '로 시작하는 목록" in prompt
