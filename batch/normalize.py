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
    "ppm": "파워스파이크 속도",
}


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


# ---- 순수 변환 함수(DB 미접근, 유닛 테스트 대상) ------------------------------


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
    """op.gg 응답엔 조합 설명 텍스트가 없어 `badge`(difficulty/tempo/reroll/honey/ppm)와
    캐리 챔피언으로 결정론적으로 생성한다(LLM 미사용, PM 승인 2026-08-04). 정확한 문구는
    추후 PM/FE-03에서 다듬을 수 있는 자리표시자 성격이 있다."""
    parts: list[str] = []

    carry_ids = [u["key"] for u in deck.get("units", []) if u.get("isCore")]
    carry_names = [_champion_display_name(champion_names, cid) for cid in carry_ids]
    if carry_names:
        parts.append("/".join(carry_names) + " 캐리")

    for badge in deck.get("badge", []):
        key, value = badge.get("key"), badge.get("value")
        if value is None or value is False:
            continue
        label = _BADGE_LABELS.get(key, key)
        parts.append(label if value is True else f"{label} {value}")

    return " · ".join(parts) if parts else "정보 없음"


def comp_rows(
    meta_decks: dict[str, Any], champion_names: dict[str, str], lang: str = "ko_KR"
) -> list[dict[str, Any]]:
    """op.gg tft_list_meta_decks 응답에서 조합 목록을 만든다."""
    rows = []
    for deck in meta_decks.get("data", []):
        stat = deck.get("stat", {})
        deck_stat = stat.get("deck", {})
        name_map = deck.get("name", {})
        rows.append(
            {
                "riot_comp_id": deck["id"],
                "name": name_map.get(lang) or next(iter(name_map.values()), deck["id"]),
                "tier_rank": _or_default(stat.get("opTier"), "unknown"),
                "avg_place": _or_default(deck_stat.get("avgPlacement"), 0.0),
                "play_rate": _or_default(deck_stat.get("pickRate"), 0.0),
                "win_rate": deck_stat.get("winRate"),
                "playstyle_text": build_playstyle_text(deck, champion_names),
                "updated_at": _parse_updated_at(meta_decks),
            }
        )
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
