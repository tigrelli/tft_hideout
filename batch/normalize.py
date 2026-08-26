"""DATA-10: op.gg(DATA-08)·Community Dragon(DATA-09) raw 응답 -> 구조화 테이블 upsert.

정합성 원칙(policies.md 3번): 모든 레코드에 patch_version 태깅, 동일 패치 내
재수집은 upsert(같은 (patch_version, 원본 ID) 행을 갱신), 다른 패치 행은 절대
덮어쓰지 않는다(새 patch_version은 항상 새 행). patches.is_current 전환은
DATA-13 몫이라 여기서는 건드리지 않는다.

comps/comp_champions는 이번 TASK 범위에 포함하지만 comp_augments는 op.gg
5개 도구 어디에도 조합-증강체 연결 데이터가 없어 채우지 않는다(PM 확인,
2026-08-04) — 데이터 소스가 생기면 그때 추가한다.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

import db_session as batch_db

models = batch_db.models

_BADGE_LABELS = {
    "difficulty": "난이도",
    "tempo": "템포",
    "reroll": "리롤 성향",
    "honey": "이코노미(하이퍼롤)",
}

# 2026-08-18 발견·제거: "ppm"을 "파워스파이크 속도"로 표시했었으나 검증 없는
# 추측 라벨이었음(build_playstyle_text 최초 주석에도 "추후 다듬을 자리표시자"
# 라고 명시돼 있었음). 실측 결과 ppm 값은 "high"/None 두 가지뿐이고,
# "high"가 붙는 조합이 매 배치에서 opScore 상위권(오늘자: 상위 4/10, DATA-23
# 알고리즘의 OP·S 등급과 정확히 일치)과 정확히 겹침 — 플레이 특성이 아니라
# op.gg 자체의 "주목 조합" 하이라이트 플래그로 추정되며, 정확한 의미는 op.gg가
# 공개하지 않아 확정할 수 없다(docs/spike/opgg-schema.md 10번 항목에 이미
# "의미 불명확"으로 기록됨). PM 결정으로 화면 표시에서 제거.
_EXCLUDED_BADGE_KEYS = {"ppm"}


def _find_set_entry(
    cdragon_data: dict[str, Any], set_number: int
) -> dict[str, Any] | None:
    for entry in cdragon_data.get("setData", []):
        if entry.get("number") == set_number:
            return entry
    return None


def _augment_table_rows(table: dict[str, Any]) -> list[dict[str, Any]]:
    headers = table.get("headers", [])
    return [dict(zip(headers, row, strict=True)) for row in table.get("rows", [])]


def _or_default(value: Any, default: Any) -> Any:
    """dict.get(key, default)는 키가 아예 없을 때만 default를 쓰고 값이 명시적으로
    None이면 None을 그대로 반환한다 — op.gg 실응답엔 category/desc 등이 null로
    오는 경우가 실제로 있어(2026-08-04 실호출로 확인) NOT NULL 컬럼에 넣기 전에
    이 헬퍼로 한 번 더 방어한다."""
    return default if value is None else value


# FE-13: Community Dragon 응답의 아이콘 필드(squareIcon 등)는 게임 엔진 원본
# 텍스처 경로(.tex, 대문자 포함)라 브라우저에서 바로 못 씀. 실제 이미지를 주는
# raw.communitydragon.org 규칙(경로 전체 소문자 + 확장자 .png)으로 변환한다
# (2026-08-05 실호출로 변환 규칙 확인, 예: "ASSETS/.../Foo.tex" ->
# "https://raw.communitydragon.org/latest/game/assets/.../foo.png").
_COMMUNITY_DRAGON_ASSET_BASE = "https://raw.communitydragon.org/latest/game/"


def cdragon_asset_url(tex_path: str) -> str:
    return _COMMUNITY_DRAGON_ASSET_BASE + tex_path.lower().replace(".tex", ".png")


# DATA-16: op.gg 증강체 설명 원문에 <br> 리터럴 태그·<rules> 같은 HTML 유사 태그·
# @TFTUnitProperty...@ 형태의 미해석 수치 템플릿이 그대로 남아있음(FE-06 실데이터
# 검증 중 발견, docs/verification/FE-06-작업결과.md). op.gg가 실제 수치를 별도로
# 안 줘서(DATA-05 스파이크 범위 밖) @...@ 템플릿을 진짜 값으로 치환할 수는 없어,
# 대신 "(수치 정보 없음)"으로 바꿔 깨진 템플릿 문법 자체는 노출되지 않게 한다.
_BR_TAG_PATTERN = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HTML_TAG_PATTERN = re.compile(r"</?[a-zA-Z][^<>]*>")
_TEMPLATE_PLACEHOLDER_PATTERN = re.compile(r"@[^@]*@")
_EXCESS_NEWLINES_PATTERN = re.compile(r"\n{3,}")


def clean_augment_description(raw: str) -> str:
    text = _BR_TAG_PATTERN.sub("\n", raw)
    text = _TEMPLATE_PLACEHOLDER_PATTERN.sub("(수치 정보 없음)", text)
    text = _HTML_TAG_PATTERN.sub("", text)
    text = _EXCESS_NEWLINES_PATTERN.sub("\n\n", text)
    return text.strip()


# DATA-19: 아이템 desc도 증강체와 같은 op.gg/Community Dragon 원본(cdragon-item)이라
# <br>·HTML 유사 태그·@...@ 미해석 수치 템플릿이 동일하게 섞여 있다(실호출 838개 전수
# 확인, docs/spike/opgg-schema.md 9번). 추가로 아이템 특유의 문제: 일부 desc가
# "{{TFT_Keyword_Precision}}"처럼 재사용 키워드를 완전히 미해석 참조로만 남겨두는데
# (예: '보석 건틀릿' desc가 "정밀을 얻습니다.<br><br>{{TFT_Keyword_Precision}}"로 끝나
# "정밀"이 정확히 뭘 주는지는 알 수 없음), op.gg·Community Dragon 어디에도 이 키워드를
# 해석해주는 별도 엔드포인트가 없다(cdragon/tft 전체 덤프 top-level 키가
# items/setData/sets뿐, 재확인 완료). 실측 결과 이런 재사용 키워드는 정밀/화상/냉각/
# 상처 4종뿐이라(DATA-07 Legend 목록과 같은 성격) 수동 유지 사전으로 보강한다 —
# PM 승인 필요, 문구는 TFT 공식 키워드 설명을 참고해 작성한 초안(부정확하면 PM이
# 직접 수정).
_ITEM_KEYWORD_GLOSSARY: dict[str, str] = {
    "TFT_Keyword_Precision": (
        "스킬 공격도 치명타로 적중할 수 있게 되고, 치명타 확률과 치명타 피해량이 증가합니다."
    ),
    "TFT_Keyword_Burn": "매초 잃은 체력의 일정 비율만큼 지속 피해를 입고, 받는 회복량이 감소합니다.",
    "TFT_Keyword_Chill": "공격 속도가 감소합니다.",
    "TFT_Keyword_Wound": "받는 회복량이 감소합니다.",
}
_KEYWORD_REFERENCE_PATTERN = re.compile(r"\{\{([^{}]+)\}\}")


def clean_item_description(raw: str) -> str:
    """아이템 desc 원문을 정리한다. 순서 중요: 재사용 키워드 참조를 먼저 실제
    설명으로 풀어낸 뒤(사전에 없는 키워드는 안전하게 제거 — 미해석 `{{...}}`
    구문을 그대로 노출하지 않기 위함), 증강체와 동일한 태그·수치 템플릿 정리를
    적용한다."""

    def _resolve_keyword(match: re.Match[str]) -> str:
        return _ITEM_KEYWORD_GLOSSARY.get(match.group(1), "")

    text = _KEYWORD_REFERENCE_PATTERN.sub(_resolve_keyword, raw)
    return clean_augment_description(text)


# DATA-20: items.stats는 op.gg/Community Dragon 원본 툴팁 변수를 그대로 담고 있어
# distinct 키가 500개 이상이고(실측), 값 단위가 키마다도 다르고(정수 퍼센트/0~1
# 소수 퍼센트/평면 수치) **같은 키 안에서도 아이템마다 단위가 섞여 있는 경우가
# 실제로 있다**(2026-08-09 실측: `AttackSpeed`가 어떤 아이템은 0.3(=30%), 어떤
# 아이템은 60(그 자체로 60%)로 저장되어 있어 하나의 규칙으로 변환 불가 — 이런
# 키(`AttackSpeed`, `Omnivamp`)는 화이트리스트에서 제외한다). 전체를 그대로
# 노출하면 단위를 알 수 없는 수치가 RAG 문서에 그대로 섞여 오답 위험이 커서,
# 값이 아이템 전수에 걸쳐 일관된 단위임을 실측으로 확인한 핵심 스탯만
# DATA-07(Legend 목록)·DATA-19(키워드 글로서리)와 같은 성격의 수동 유지
# 화이트리스트로 관리한다(CHAT-14 PM 검증 중 발견, 2026-08-09 PM 결정. 문구·수치는
# op.gg 원본 그대로라 PM 검토 필요한 초안, DATA-19와 동일 성격). unit:
# "flat"(공격력/체력처럼 그냥 더해지는 수치, +35 형태) / "percent"(치명타 확률처럼
# 이미 정수 퍼센트 포인트로 저장된 값, +35% 형태) /
# "percent_fraction"(0~1 소수로 저장된 퍼센트, 0.35 -> +35% 형태로 환산).
_ITEM_STAT_WHITELIST: dict[str, tuple[str, str]] = {
    "AP": ("주문력", "flat"),
    "Armor": ("방어력", "flat"),
    "MagicResist": ("마법 저항력", "flat"),
    "Health": ("체력", "flat"),
    "ManaRegen": ("마나 재생", "flat"),
    "AD": ("공격력", "percent_fraction"),
    "CritChance": ("치명타 확률", "percent"),
    "CritDamageToGive": ("치명타 피해", "percent"),
    "LifeSteal": ("생명력 흡수", "percent"),
    "DamageAmp": ("피해량 증폭", "percent_fraction"),
}


def _format_stat_value(value: float, unit: str) -> str:
    if unit == "percent_fraction":
        value = round(value * 100, 1)
        percent = True
    else:
        percent = unit == "percent"
    display = int(value) if value == int(value) else value
    return f"+{display}%" if percent else f"+{display}"


def format_item_stats(stats: dict[str, Any] | None) -> str:
    """items.stats(원본 그대로)에서 화이트리스트 핵심 스탯만 "이름 +값" 형태로
    골라 ", "로 이어붙인다. 화이트리스트에 없거나 값이 없는(None) 키는 조용히
    건너뛴다 — 의미·단위를 확신할 수 없는 수치를 RAG 문서에 노출하지 않기
    위함(위 주석 참고). 노출할 스탯이 하나도 없으면 빈 문자열을 반환한다."""
    if not stats:
        return ""
    parts = []
    for key, (label, unit) in _ITEM_STAT_WHITELIST.items():
        value = stats.get(key)
        if not isinstance(value, int | float):
            continue
        parts.append(f"{label} {_format_stat_value(value, unit)}")
    return ", ".join(parts)


# ---- 순수 변환 함수(DB 미접근, 유닛 테스트 대상) ------------------------------


# 2026-08-26 발견(패치 18.1 자동 감지 사고): Community Dragon setData[].champions
# 배열에는 실제 플레이 가능한 챔피언 외에 정글 몬스터·아이템 모루·훈련 봇 같은
# 비챔피언 엔티티도 섞여 있다(예: TFT_Krug, TFT_BlueGolem, TFT_ArmoryKeyCompleted).
# 이전까지는 실챔피언이 항상 함께 들어있어 화면에 안 보였을 뿐 걸러낸 적이 없었다.
# Set 17·Set 18 양쪽 실데이터로 확인한 결과 비챔피언 엔티티는 예외 없이
# `traits: []`(빈 리스트)이고 실챔피언은 항상 1개 이상의 특성을 갖는다 — apiName
# 접두어(`TFT17_`/`TFT18_`)는 Set 18에서 `DA_18_`로 바뀌어 신뢰할 수 없음이
# 확인됐으므로(docs/spike/tft-ddragon.md) traits 유무로 판별한다.
def champion_rows(
    cdragon_ko: dict[str, Any], cdragon_en: dict[str, Any], set_number: int
) -> list[dict[str, Any]]:
    """Community Dragon 세트 데이터에서 챔피언 목록을 만든다(op.gg는 챔피언
    표시 이름을 주지 않아 이 소스가 유일함, DATA-09 결정)."""
    entry_ko = _find_set_entry(cdragon_ko, set_number)
    entry_en = _find_set_entry(cdragon_en, set_number)
    if not entry_ko or not entry_en:
        return []
    en_by_id = {c["apiName"]: c for c in entry_en.get("champions", [])}
    rows = []
    for c_ko in entry_ko.get("champions", []):
        if not c_ko.get("traits"):
            continue
        api_name = c_ko["apiName"]
        c_en = en_by_id.get(api_name)
        if c_en is None:
            continue
        square_icon = c_ko.get("squareIcon")
        rows.append(
            {
                "riot_champion_id": api_name,
                "name_kr": c_ko["name"],
                "name_en": c_en["name"],
                "cost": c_ko["cost"],
                "square_icon_url": (
                    cdragon_asset_url(square_icon) if square_icon else None
                ),
            }
        )
    return rows


# 2026-08-26 발견(패치 18.1 자동 감지 사고): Set 18 런칭 감지 당시 Community
# Dragon의 setData[18] 항목이 아직 실챔피언 2명(traits 있는 항목 기준)만 채워진
# 미리보기 상태였는데도, run_batch_with_atomic_promotion(DATA-13)은 "예외 없이
# 끝났는가"만으로 성공 여부를 판단해 이 상태를 그대로 patches.is_current로
# 승격시켰다 — comp_champions가 전부 0건이 돼 조합 상세 화면이 통째로 비었다.
# 기존 패치 대비 챔피언 수가 비정상적으로 적으면 여기서 예외를 던져 배치를
# 실패 처리(is_current 승격 차단)한다. 역대 TFT 세트는 최소 40명 이상이었으므로
# 여유를 둔 30명을 하한선으로 삼는다(신규 세트 축소 개편 가능성 감안).
MIN_REAL_CHAMPIONS_PER_SET = 30


def validate_champion_collection(
    champions: list[dict[str, Any]], set_number: int
) -> None:
    """챔피언 수집 결과가 비정상적으로 적으면 예외를 던져 배치를 중단시킨다
    (patch_transition.run_batch_with_atomic_promotion이 잡아 is_current 승격을
    막는다)."""
    if len(champions) < MIN_REAL_CHAMPIONS_PER_SET:
        raise ValueError(
            f"Set {set_number} 챔피언 수집 결과가 비정상적으로 적습니다"
            f"({len(champions)}명, 최소 {MIN_REAL_CHAMPIONS_PER_SET}명 기대) — "
            "Community Dragon의 해당 세트 데이터가 아직 미완성(프리뷰)일 수 있으니 "
            "patch_version 승격을 중단합니다."
        )


def trait_rows(
    cdragon_ko: dict[str, Any], cdragon_en: dict[str, Any], set_number: int
) -> list[dict[str, Any]]:
    """op.gg 5개 도구엔 특성(trait) 데이터가 전혀 없어 Community Dragon만 사용."""
    entry_ko = _find_set_entry(cdragon_ko, set_number)
    entry_en = _find_set_entry(cdragon_en, set_number)
    if not entry_ko or not entry_en:
        return []
    en_by_id = {t["apiName"]: t for t in entry_en.get("traits", [])}
    rows = []
    for t_ko in entry_ko.get("traits", []):
        api_name = t_ko["apiName"]
        t_en = en_by_id.get(api_name)
        if t_en is None:
            continue
        rows.append(
            {
                "riot_trait_id": api_name,
                "name_kr": t_ko["name"],
                "name_en": t_en["name"],
                "tier_thresholds": t_ko.get("effects", []),
            }
        )
    return rows


def item_rows(
    items_ko: dict[str, Any],
    items_en: dict[str, Any],
    cdragon_ko: dict[str, Any],
) -> list[dict[str, Any]]:
    """op.gg tft_list_item_combinations(ko/en 각 1회 호출 결과)에서 아이템 목록을
    만든다. 아이콘은 op.gg 응답에 없어(2026-08-06 확인) Community Dragon
    cdragon/tft 응답의 최상위 items[](챔피언과 달리 세트별 setData가 아닌 전역
    목록, apiName으로 매칭됨, 2026-08-06 실호출로 확인)의 icon 필드를
    cdragon_asset_url로 변환해 채운다."""
    en_by_id = {i["apiName"]: i for i in items_en.get("data", [])}
    icon_by_id = {i["apiName"]: i.get("icon") for i in cdragon_ko.get("items", [])}
    rows = []
    for i_ko in items_ko.get("data", []):
        api_name = i_ko["apiName"]
        i_en = en_by_id.get(api_name)
        if i_en is None:
            continue
        icon = icon_by_id.get(api_name)
        rows.append(
            {
                "riot_item_id": api_name,
                "name_kr": _or_default(i_ko.get("name"), api_name),
                "name_en": _or_default(i_en.get("name"), api_name),
                "item_type": _or_default(i_ko.get("category"), "unknown"),
                "components": _or_default(i_ko.get("composition"), []),
                "stats": _or_default(i_ko.get("effects"), {}),
                "square_icon_url": cdragon_asset_url(icon) if icon else None,
                "description": clean_item_description(
                    _or_default(i_ko.get("desc"), "")
                ),
            }
        )
    return rows


def augment_rows(
    augments_ko: dict[str, Any], augments_en: dict[str, Any]
) -> list[dict[str, Any]]:
    """op.gg tft_list_augments(ko/en 각 1회 호출 결과)에서 증강체 목록을 만든다.

    is_legend_related은 항상 False로 고정한다 — DATA-07 결정: op.gg 응답에 라벨이
    없고 현재 Set 17엔 Legends 메커니즘 자체가 없다(목록 관리 인프라는 필요해질
    때 만들기로 함, YAGNI).

    image_url은 챔피언/아이템과 달리 op.gg 응답(headers의 imageUrl 컬럼,
    c-tft-api.op.gg CDN)에 바로 들어있어 Community Dragon 변환이 필요 없다.
    """
    en_by_id = {r["apiName"]: r for r in _augment_table_rows(augments_en)}
    rows = []
    for r_ko in _augment_table_rows(augments_ko):
        api_name = r_ko["apiName"]
        r_en = en_by_id.get(api_name)
        if r_en is None:
            continue
        rows.append(
            {
                "riot_augment_id": api_name,
                "name_kr": _or_default(r_ko.get("name"), api_name),
                "name_en": _or_default(r_en.get("name"), api_name),
                "tier": _or_default(r_ko.get("tier"), "unknown"),
                "description": clean_augment_description(
                    _or_default(r_ko.get("desc"), "")
                ),
                "is_legend_related": False,
                "image_url": r_ko.get("imageUrl"),
            }
        )
    return rows


def _champion_display_name(champion_names: dict[str, str], champion_id: str) -> str:
    return champion_names.get(champion_id, champion_id)


def build_playstyle_text(deck: dict[str, Any], champion_names: dict[str, str]) -> str:
    """op.gg 응답엔 조합 설명 텍스트가 없어 `badge`(difficulty/tempo/reroll/honey,
    ppm은 2026-08-18 제외 — 아래 _EXCLUDED_BADGE_KEYS 주석 참고)와 캐리 챔피언으로
    결정론적으로 생성한다(LLM 미사용, PM 승인 2026-08-04). 정확한 문구는 추후
    PM/FE-03에서 다듬을 수 있는 자리표시자 성격이 있다."""
    parts: list[str] = []

    carry_ids = [u["key"] for u in deck.get("units", []) if u.get("isCore")]
    carry_names = [_champion_display_name(champion_names, cid) for cid in carry_ids]
    if carry_names:
        parts.append("/".join(carry_names) + " 캐리")

    for badge in deck.get("badge", []):
        key, value = badge.get("key"), badge.get("value")
        if value is None or value is False or key in _EXCLUDED_BADGE_KEYS:
            continue
        label = _BADGE_LABELS.get(key, key)
        parts.append(label if value is True else f"{label} {value}")

    return " · ".join(parts) if parts else "정보 없음"


# DATA-21(2026-08-16, PM 요청): op.gg 웹사이트와 티어 배지가 다르게 보인다는
# PM 제보를 조사한 결과, op.gg tft_list_meta_decks(MCP 공개 도구)는 랭크 필터
# 없이 정확히 10개 조합만 반환해(DATA-05 스파이크) op.gg 웹사이트(20개 이상,
# 랭크 구간 필터 가능)와 애초에 모집단 자체가 다름을 확인 — op.gg 웹사이트와
# 완전히 일치시킬 방법은 없다. 대신 이 배치가 실제로 확보한 표본 안에서라도
# avg_place·win_rate가 뱃지와 어긋나지 않도록(예: 승률이 더 낮은 조합이 더
# 높은 뱃지를 받는 경우 방지) op.gg가 준 opTier를 그대로 쓰지 않고 자체
# 상대순위로 재계산한다(PM 승인 2026-08-16).
_TIER_LABELS: list[str] = ["OP", "S", "A", "B", "C"]

# DATA-23: 2026-08-18 단일 스냅샷(같은 배치 10개)에서 탐색적으로 찾은 값이라
# 과적합 위험이 있음 — 여러 날짜/패치 스냅샷으로 재검증 필요(docs/spike/
# comp-tier-scoring.md "반드시 확인 후 구현할 것" 참고).
_GAP_THRESHOLD_FACTOR = 1.3


def assign_self_tiers(rows: list[dict[str, Any]]) -> None:
    """같은 배치(패치 1회 수집 단위, 통상 10개)의 comp 행들에 op_score 기반
    자체 상대순위 tier_rank를 매겨 rows를 제자리에서(in-place) 갱신한다
    (DATA-23, avg_place·win_rate 두 축 순위합 방식(DATA-21)을 폐기).

    op_score는 avg_place·win_rate·top4_rate와 거의 무관(r≈-0.2)하고
    pickRate와 거의 완벽히 상관(r=0.984)함이 실측으로 확인됨 — op.gg의
    top-10(이미 성능으로 1차 필터링된 집합) 안에서는 사실상 대중성·신뢰도
    대리 지표다. 따라서 이 알고리즘의 목표는 "객관적 최강 조합 판별"이
    아니라 "op.gg top-10 안에서 op_score 기준으로 믿을 만하게 강한 대중적
    조합의 상대 순위"로 재정의됐다(docs/spike/comp-tier-scoring.md).

    op_score를 0~100으로 Min-Max 정규화 → 내림차순 정렬 → 인접 순위 간
    점수 격차가 평균 격차 x _GAP_THRESHOLD_FACTOR를 넘는 지점만 "진짜
    경계"로 인정한다(고정 5단계 강제 배분 폐지 — 그날 데이터 분포에 따라
    3~5단계로 가변적). op_score가 없는 행(op.gg 응답 결측)은 이 정규화·
    격차 계산에서 제외하고 항상 "C"로 고정한다."""
    n = len(rows)
    if n == 0:
        return

    scored_indices = [
        i for i, row in enumerate(rows) if row.get("op_score") is not None
    ]
    for i, row in enumerate(rows):
        if row.get("op_score") is None:
            row["tier_rank"] = "C"

    if len(scored_indices) == 0:
        return
    if len(scored_indices) == 1:
        rows[scored_indices[0]]["tier_rank"] = "A"
        return

    values = [rows[i]["op_score"] for i in scored_indices]
    min_v, max_v = min(values), max(values)
    spread = max_v - min_v
    normalized = [100 * (v - min_v) / spread if spread else 0.0 for v in values]

    order = sorted(range(len(scored_indices)), key=lambda k: -normalized[k])
    sorted_scores = [normalized[k] for k in order]
    gaps = [sorted_scores[k] - sorted_scores[k + 1] for k in range(len(order) - 1)]
    mean_gap = sum(gaps) / len(gaps) if gaps else 0.0
    threshold = mean_gap * _GAP_THRESHOLD_FACTOR

    label_idx = 0
    rows[scored_indices[order[0]]]["tier_rank"] = _TIER_LABELS[0]
    for pos in range(1, len(order)):
        if gaps[pos - 1] > threshold and label_idx < len(_TIER_LABELS) - 1:
            label_idx += 1
        rows[scored_indices[order[pos]]]["tier_rank"] = _TIER_LABELS[label_idx]


def comp_rows(
    meta_decks: dict[str, Any], champion_names: dict[str, str], lang: str = "ko_KR"
) -> list[dict[str, Any]]:
    """op.gg tft_list_meta_decks 응답에서 조합 목록을 만든다. tier_rank는
    op.gg opTier가 아니라 assign_self_tiers()의 자체 계산 값이다(DATA-21)."""
    rows = []
    for deck in meta_decks.get("data", []):
        stat = deck.get("stat", {})
        deck_stat = stat.get("deck", {})
        name_map = deck.get("name", {})
        rows.append(
            {
                "riot_comp_id": deck["id"],
                "name": name_map.get(lang) or next(iter(name_map.values()), deck["id"]),
                "tier_rank": "unknown",
                "avg_place": _or_default(deck_stat.get("avgPlacement"), 0.0),
                "play_rate": _or_default(deck_stat.get("pickRate"), 0.0),
                "win_rate": deck_stat.get("winRate"),
                # DATA-22: top4Rate(4등 이내 확률), compsCount(조합별 실제 표본
                # 게임수 — totalCount는 집계구간 전체 공통분모라 개별 조합
                # 표본과 다름, docs/spike/opgg-schema.md 10번 항목).
                "top4_rate": deck_stat.get("top4Rate"),
                "game_count": deck_stat.get("compsCount"),
                # DATA-23: assign_self_tiers()가 tier_rank 계산에 쓰는 원값.
                "op_score": stat.get("opScore"),
                "playstyle_text": build_playstyle_text(deck, champion_names),
                "updated_at": _parse_updated_at(meta_decks),
            }
        )
    assign_self_tiers(rows)
    return rows


def _parse_updated_at(meta_decks: dict[str, Any]) -> datetime:
    raw = meta_decks.get("metadata", {}).get("gameStatDateTime")
    if not raw:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


def comp_champion_rows(deck: dict[str, Any]) -> list[dict[str, Any]]:
    """deck 하나(comp_rows에 넘긴 것과 동일 deck)에서 조합-챔피언 매핑을 만든다.
    champion_id(riot ID) -> DB id 해석은 호출부(upsert_comp_champions)에서 한다.

    cell_x/cell_y는 unit.cell.{x,y}(x:1~7, y:1~4, 4행x7열 실제 배치 좌표,
    FE-14, 2026-08-06 실호출로 확인) — cell 필드가 없으면(과거 응답 형태 대비
    방어적으로) None으로 둬 프론트가 휴리스틱 배치로 폴백하게 한다.

    star_level은 unit.tier(정수 2 또는 3, FE-15, 2026-08-06 실호출로 확인 —
    cell과 같은 unit 객체 필드) — 없으면 None으로 둬 프론트가 별 표시를
    생략하게 한다."""
    rows = []
    for unit in deck.get("units", []):
        cell = unit.get("cell") or {}
        rows.append(
            {
                "riot_champion_id": unit["key"],
                "is_carry": bool(unit.get("isCore", False)),
                "recommended_items": unit.get("items", []),
                "cell_x": cell.get("x"),
                "cell_y": cell.get("y"),
                "star_level": unit.get("tier"),
            }
        )
    return rows


def comp_trait_rows(deck: dict[str, Any]) -> list[dict[str, Any]]:
    """deck 하나(comp_rows에 넘긴 것과 동일 deck)에서 조합-시너지 매핑을 만든다.
    trait_id(riot ID) -> DB id 해석은 호출부(upsert_comp_traits)에서 한다.
    (DATA-22, op.gg tft_list_meta_decks 응답 deck.traits[])."""
    rows = []
    for trait in deck.get("traits", []):
        rows.append(
            {
                "riot_trait_id": trait["key"],
                "style": trait["style"],
                "num_units": trait["numUnits"],
            }
        )
    return rows


def champion_item_build_rows(build_response: dict[str, Any]) -> list[dict[str, Any]]:
    """op.gg tft_get_champion_item_build(champion_id) 응답에서 빌드 목록을 만든다."""
    rows = []
    for entry in build_response.get("data", []):
        total = entry.get("totalChampionCount") or 0
        item_count = entry.get("itemCount") or 0
        rows.append(
            {
                "item_combination": _or_default(entry.get("itemNames"), []),
                "play_rate": (item_count / total) if total else 0.0,
                "avg_place": _or_default(entry.get("avgPlacement"), 0.0),
                "win_rate": _or_default(entry.get("winRate"), 0.0),
            }
        )
    return rows


# ---- DB upsert 함수 -----------------------------------------------------------


def ensure_patch(
    session: Session,
    version: str,
    set_number: int,
    released_at: datetime | None = None,
) -> None:
    """patches 행이 없으면 생성한다(is_current는 건드리지 않음 — DATA-13 몫)."""
    now = datetime.now(UTC)
    stmt = pg_insert(models.Patch).values(
        version=version,
        set_number=set_number,
        released_at=released_at or now,
        is_current=False,
        detected_at=now,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["version"])
    session.execute(stmt)


def upsert_champions(
    session: Session, patch_version: str, rows: list[dict[str, Any]]
) -> dict[str, int]:
    """반환: {riot_champion_id: db_id}. 빈 rows면 빈 dict."""
    if not rows:
        return {}
    stmt = pg_insert(models.Champion).values(
        [{**row, "patch_version": patch_version} for row in rows]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["patch_version", "riot_champion_id"],
        set_={
            "name_kr": stmt.excluded.name_kr,
            "name_en": stmt.excluded.name_en,
            "cost": stmt.excluded.cost,
            "square_icon_url": stmt.excluded.square_icon_url,
        },
    ).returning(models.Champion.id, models.Champion.riot_champion_id)
    return {riot_id: db_id for db_id, riot_id in session.execute(stmt)}


def upsert_traits(
    session: Session, patch_version: str, rows: list[dict[str, Any]]
) -> dict[str, int]:
    if not rows:
        return {}
    stmt = pg_insert(models.Trait).values(
        [{**row, "patch_version": patch_version} for row in rows]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["patch_version", "riot_trait_id"],
        set_={
            "name_kr": stmt.excluded.name_kr,
            "name_en": stmt.excluded.name_en,
            "tier_thresholds": stmt.excluded.tier_thresholds,
        },
    ).returning(models.Trait.id, models.Trait.riot_trait_id)
    return {riot_id: db_id for db_id, riot_id in session.execute(stmt)}


def upsert_items(
    session: Session, patch_version: str, rows: list[dict[str, Any]]
) -> dict[str, int]:
    if not rows:
        return {}
    stmt = pg_insert(models.Item).values(
        [{**row, "patch_version": patch_version} for row in rows]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["patch_version", "riot_item_id"],
        set_={
            "name_kr": stmt.excluded.name_kr,
            "name_en": stmt.excluded.name_en,
            "item_type": stmt.excluded.item_type,
            "components": stmt.excluded.components,
            "stats": stmt.excluded.stats,
            "square_icon_url": stmt.excluded.square_icon_url,
            "description": stmt.excluded.description,
        },
    ).returning(models.Item.id, models.Item.riot_item_id)
    return {riot_id: db_id for db_id, riot_id in session.execute(stmt)}


def upsert_augments(
    session: Session, patch_version: str, rows: list[dict[str, Any]]
) -> dict[str, int]:
    if not rows:
        return {}
    stmt = pg_insert(models.Augment).values(
        [{**row, "patch_version": patch_version} for row in rows]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["patch_version", "riot_augment_id"],
        set_={
            "name_kr": stmt.excluded.name_kr,
            "name_en": stmt.excluded.name_en,
            "tier": stmt.excluded.tier,
            "description": stmt.excluded.description,
            "is_legend_related": stmt.excluded.is_legend_related,
            "image_url": stmt.excluded.image_url,
        },
    ).returning(models.Augment.id, models.Augment.riot_augment_id)
    return {riot_id: db_id for db_id, riot_id in session.execute(stmt)}


def upsert_comps(
    session: Session, patch_version: str, rows: list[dict[str, Any]]
) -> dict[str, int]:
    """반환: {riot_comp_id: db_id}."""
    if not rows:
        return {}
    stmt = pg_insert(models.Comp).values(
        [{**row, "patch_version": patch_version} for row in rows]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["patch_version", "riot_comp_id"],
        set_={
            "name": stmt.excluded.name,
            "tier_rank": stmt.excluded.tier_rank,
            "avg_place": stmt.excluded.avg_place,
            "play_rate": stmt.excluded.play_rate,
            "win_rate": stmt.excluded.win_rate,
            "top4_rate": stmt.excluded.top4_rate,
            "game_count": stmt.excluded.game_count,
            "op_score": stmt.excluded.op_score,
            "playstyle_text": stmt.excluded.playstyle_text,
            "updated_at": stmt.excluded.updated_at,
            # DATA-17: 이전 배치에서 소프트 삭제(is_active=False)됐던 조합이
            # 다시 op.gg 상위 10위에 나타나면 재활성화한다.
            "is_active": True,
        },
    ).returning(models.Comp.id, models.Comp.riot_comp_id)
    return {riot_id: db_id for db_id, riot_id in session.execute(stmt)}


def mark_stale_comps_inactive(
    session: Session, patch_version: str, active_riot_comp_ids: set[str]
) -> int:
    """이번 배치 op.gg 응답에 없는 기존 조합을 소프트 삭제(is_active=False)한다.

    op.gg tft_list_meta_decks는 페이지네이션 없이 항상 현재 상위 10개
    조합만 반환해(DATA-17, docs/spike/opgg-schema.md 7·8번), 같은
    patch_version 내에서도 메타가 회전하면 예전에 상위 10위였던 조합이
    이번 응답엔 없을 수 있다. comp_champions/comp_augments·
    match_analyses.matched_comp_id FK와 meta_document_embeddings 참조를
    보존해야 해서 하드 삭제 대신 플래그만 끈다 — 호출부는 반드시
    upsert_comps() 직후, active_riot_comp_ids에 이번 배치로 upsert한
    riot_comp_id 전체를 넘겨 호출해야 한다."""
    stmt = (
        update(models.Comp)
        .where(
            models.Comp.patch_version == patch_version,
            models.Comp.is_active.is_(True),
            models.Comp.riot_comp_id.not_in(active_riot_comp_ids),
        )
        .values(is_active=False)
    )
    result = session.execute(stmt)
    return result.rowcount


def upsert_comp_champions(
    session: Session,
    comp_id: int,
    rows: list[dict[str, Any]],
    champion_ids_by_riot_id: dict[str, int],
) -> None:
    """rows는 comp_champion_rows() 결과(riot_champion_id 포함). 매핑에 없는
    챔피언(예: PVE 전용이라 champions 테이블에 없는 유닛)은 건너뛴다."""
    values = []
    for row in rows:
        champion_id = champion_ids_by_riot_id.get(row["riot_champion_id"])
        if champion_id is None:
            continue
        values.append(
            {
                "comp_id": comp_id,
                "champion_id": champion_id,
                "is_carry": row["is_carry"],
                "recommended_items": row["recommended_items"],
                "cell_x": row.get("cell_x"),
                "cell_y": row.get("cell_y"),
                "star_level": row.get("star_level"),
            }
        )
    if not values:
        return
    stmt = pg_insert(models.CompChampion).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["comp_id", "champion_id"],
        set_={
            "is_carry": stmt.excluded.is_carry,
            "recommended_items": stmt.excluded.recommended_items,
            "cell_x": stmt.excluded.cell_x,
            "cell_y": stmt.excluded.cell_y,
            "star_level": stmt.excluded.star_level,
        },
    )
    session.execute(stmt)


def upsert_comp_traits(
    session: Session,
    comp_id: int,
    rows: list[dict[str, Any]],
    trait_ids_by_riot_id: dict[str, int],
) -> None:
    """rows는 comp_trait_rows() 결과(riot_trait_id 포함). 매핑에 없는 특성은
    건너뛴다(DATA-22, comp_champions/upsert_comp_champions과 동일 패턴)."""
    values = []
    for row in rows:
        trait_id = trait_ids_by_riot_id.get(row["riot_trait_id"])
        if trait_id is None:
            continue
        values.append(
            {
                "comp_id": comp_id,
                "trait_id": trait_id,
                "style": row["style"],
                "num_units": row["num_units"],
            }
        )
    if not values:
        return
    stmt = pg_insert(models.CompTrait).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["comp_id", "trait_id"],
        set_={
            "style": stmt.excluded.style,
            "num_units": stmt.excluded.num_units,
        },
    )
    session.execute(stmt)


def replace_champion_item_builds(
    session: Session,
    champion_id: int,
    patch_version: str,
    rows: list[dict[str, Any]],
) -> None:
    """champion_item_builds는 안정적인 자연키가 없어(빌드 조합이 매번 순위가
    바뀔 수 있음) 챔피언·패치 단위로 기존 행을 지우고 새로 넣는다(replace-set)."""
    from sqlalchemy import delete

    session.execute(
        delete(models.ChampionItemBuild).where(
            models.ChampionItemBuild.champion_id == champion_id,
            models.ChampionItemBuild.patch_version == patch_version,
        )
    )
    if rows:
        session.execute(
            pg_insert(models.ChampionItemBuild).values(
                [
                    {**row, "champion_id": champion_id, "patch_version": patch_version}
                    for row in rows
                ]
            )
        )
