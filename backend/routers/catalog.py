import re
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    Augment,
    Champion,
    ChampionItemBuild,
    Comp,
    CompAugment,
    CompChampion,
    Item,
    Patch,
)
from db.session import get_db

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])

PATCH_PATTERN = re.compile(r"^\d+\.\d+$")
# op.gg 실제 랭크 구간 값은 DATA-05 스파이크 완료 후 확정 — 지금은 "all"만 실사용, 나머지는 자리표시
ALLOWED_RANKS = {"all", "challenger", "grandmaster", "master"}
# op.gg tft_list_augments의 실제 tier 값 3종(DATA-05 스파이크, docs/spike/legend-augment.md)
ALLOWED_AUGMENT_TIERS = {"gold", "silver", "prism"}


class CompSummary(BaseModel):
    id: int
    name: str
    tier_rank: str
    avg_place: float
    play_rate: float
    win_rate: float | None
    playstyle_text: str
    carry_champion_ids: list[int]


class TierlistResponse(BaseModel):
    patch_version: str
    rank: str
    comps: list[CompSummary]


def _invalid_param_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=400, detail={"error": {"code": code, "message": message}}
    )


def _not_found_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=404, detail={"error": {"code": code, "message": message}}
    )


def _resolve_patch(db: Session, patch: str | None) -> str:
    """patch 미지정 시 patches.is_current=True인 버전으로 대체한다."""
    if patch is not None:
        return patch
    current = db.execute(
        select(Patch).where(Patch.is_current.is_(True))
    ).scalar_one_or_none()
    if current is None:
        raise _not_found_error("no_current_patch", "현재 패치가 설정되어 있지 않습니다")
    return current.version


class ChampionInComp(BaseModel):
    champion_id: int
    name_kr: str
    name_en: str
    is_carry: bool
    recommended_items: list[str]  # 원본 riot_item_id(추후 아이콘 매칭용)
    recommended_item_names: list[str]  # 사람이 읽는 이름(items.name_kr)


class AugmentInComp(BaseModel):
    augment_id: int
    name_kr: str
    name_en: str
    priority: int


class CompDetailResponse(BaseModel):
    id: int
    patch_version: str
    name: str
    tier_rank: str
    avg_place: float
    play_rate: float
    win_rate: float | None
    playstyle_text: str
    champions: list[ChampionInComp]
    augments: list[AugmentInComp]


class ItemBuild(BaseModel):
    id: int
    champion_id: int
    item_combination: dict
    play_rate: float
    avg_place: float
    win_rate: float


class ItemBuildsResponse(BaseModel):
    patch_version: str
    champion_id: int | None
    builds: list[ItemBuild]


class AugmentSummary(BaseModel):
    id: int
    name_kr: str
    name_en: str
    tier: str
    description: str
    is_legend_related: bool
    win_rate: float | None


class AugmentsResponse(BaseModel):
    patch_version: str
    augments: list[AugmentSummary]


class CurrentPatchResponse(BaseModel):
    version: str
    set_number: int
    released_at: datetime
    detected_at: datetime


@router.get("/")
def catalog_root() -> dict[str, str]:
    return {"router": "catalog"}


@router.get("/tierlist", response_model=TierlistResponse)
def get_tierlist(
    db: Annotated[Session, Depends(get_db)],
    patch: str | None = Query(default=None),
    rank: str = Query(default="all"),
) -> TierlistResponse:
    if patch is not None and not PATCH_PATTERN.match(patch):
        raise _invalid_param_error(
            "invalid_patch", "patch는 'MAJOR.MINOR' 형식이어야 합니다 (예: 14.5)"
        )
    if rank not in ALLOWED_RANKS:
        raise _invalid_param_error(
            "invalid_rank", f"rank는 {sorted(ALLOWED_RANKS)} 중 하나여야 합니다"
        )

    resolved_patch = _resolve_patch(db, patch)

    comps = (
        db.execute(
            select(Comp).where(
                Comp.patch_version == resolved_patch, Comp.rank_tier == rank
            )
        )
        .scalars()
        .all()
    )

    summaries = []
    for comp in comps:
        carry_champion_ids = list(
            db.execute(
                select(CompChampion.champion_id).where(
                    CompChampion.comp_id == comp.id,
                    CompChampion.is_carry.is_(True),
                )
            ).scalars()
        )
        summaries.append(
            CompSummary(
                id=comp.id,
                name=comp.name,
                tier_rank=comp.tier_rank,
                avg_place=comp.avg_place,
                play_rate=comp.play_rate,
                win_rate=comp.win_rate,
                playstyle_text=comp.playstyle_text,
                carry_champion_ids=carry_champion_ids,
            )
        )

    return TierlistResponse(patch_version=resolved_patch, rank=rank, comps=summaries)


@router.get("/comps/{comp_id}", response_model=CompDetailResponse)
def get_comp_detail(
    comp_id: int, db: Annotated[Session, Depends(get_db)]
) -> CompDetailResponse:
    comp = db.get(Comp, comp_id)
    if comp is None:
        raise _not_found_error(
            "comp_not_found", f"comp_id={comp_id}에 해당하는 조합이 없습니다"
        )

    champion_rows = db.execute(
        select(CompChampion, Champion)
        .join(Champion, Champion.id == CompChampion.champion_id)
        .where(CompChampion.comp_id == comp_id)
        .order_by(CompChampion.is_carry.desc(), CompChampion.champion_id)
    ).all()

    # recommended_items는 op.gg 원본 아이템 ID 문자열이라(챔피언 이름과 달리 op.gg가
    # 자체 제공하지 않는 표시 이름 없음) items 테이블에서 같은 patch_version 기준으로
    # 이름을 조회한다(riot_item_id는 FK가 아니라 문자열 매칭이라 patch_version을
    # 명시해야 다른 패치의 동명 아이템과 섞이지 않음 — 실 데이터로 매칭 확인됨).
    item_ids = {
        item_id
        for comp_champion, _ in champion_rows
        for item_id in comp_champion.recommended_items
    }
    item_name_by_id = (
        {
            row.riot_item_id: row.name_kr
            for row in db.execute(
                select(Item).where(
                    Item.patch_version == comp.patch_version,
                    Item.riot_item_id.in_(item_ids),
                )
            ).scalars()
        }
        if item_ids
        else {}
    )

    champions = [
        ChampionInComp(
            champion_id=comp_champion.champion_id,
            name_kr=champion.name_kr,
            name_en=champion.name_en,
            is_carry=comp_champion.is_carry,
            recommended_items=comp_champion.recommended_items,
            recommended_item_names=[
                item_name_by_id.get(item_id, item_id)
                for item_id in comp_champion.recommended_items
            ],
        )
        for comp_champion, champion in champion_rows
    ]

    augment_rows = db.execute(
        select(CompAugment, Augment)
        .join(Augment, Augment.id == CompAugment.augment_id)
        .where(CompAugment.comp_id == comp_id)
        .order_by(CompAugment.priority)
    ).all()
    augments = [
        AugmentInComp(
            augment_id=comp_augment.augment_id,
            name_kr=augment.name_kr,
            name_en=augment.name_en,
            priority=comp_augment.priority,
        )
        for comp_augment, augment in augment_rows
    ]

    return CompDetailResponse(
        id=comp.id,
        patch_version=comp.patch_version,
        name=comp.name,
        tier_rank=comp.tier_rank,
        avg_place=comp.avg_place,
        play_rate=comp.play_rate,
        win_rate=comp.win_rate,
        playstyle_text=comp.playstyle_text,
        champions=champions,
        augments=augments,
    )


@router.get("/items/builds", response_model=ItemBuildsResponse)
def get_item_builds(
    db: Annotated[Session, Depends(get_db)],
    patch: str | None = Query(default=None),
    champion_id: int | None = Query(default=None),
) -> ItemBuildsResponse:
    if patch is not None and not PATCH_PATTERN.match(patch):
        raise _invalid_param_error(
            "invalid_patch", "patch는 'MAJOR.MINOR' 형식이어야 합니다 (예: 14.5)"
        )

    resolved_patch = _resolve_patch(db, patch)

    stmt = select(ChampionItemBuild).where(
        ChampionItemBuild.patch_version == resolved_patch
    )
    if champion_id is not None:
        stmt = stmt.where(ChampionItemBuild.champion_id == champion_id)
    stmt = stmt.order_by(ChampionItemBuild.play_rate.desc())

    rows = db.execute(stmt).scalars().all()
    builds = [
        ItemBuild(
            id=row.id,
            champion_id=row.champion_id,
            item_combination=row.item_combination,
            play_rate=row.play_rate,
            avg_place=row.avg_place,
            win_rate=row.win_rate,
        )
        for row in rows
    ]

    return ItemBuildsResponse(
        patch_version=resolved_patch, champion_id=champion_id, builds=builds
    )


@router.get("/augments", response_model=AugmentsResponse)
def get_augments(
    db: Annotated[Session, Depends(get_db)],
    patch: str | None = Query(default=None),
    tier: str | None = Query(default=None),
) -> AugmentsResponse:
    if patch is not None and not PATCH_PATTERN.match(patch):
        raise _invalid_param_error(
            "invalid_patch", "patch는 'MAJOR.MINOR' 형식이어야 합니다 (예: 14.5)"
        )
    if tier is not None and tier not in ALLOWED_AUGMENT_TIERS:
        raise _invalid_param_error(
            "invalid_tier", f"tier는 {sorted(ALLOWED_AUGMENT_TIERS)} 중 하나여야 합니다"
        )

    resolved_patch = _resolve_patch(db, patch)

    stmt = select(Augment).where(Augment.patch_version == resolved_patch)
    if tier is not None:
        stmt = stmt.where(Augment.tier == tier)
    stmt = stmt.order_by(Augment.id)

    rows = db.execute(stmt).scalars().all()
    augments = [
        AugmentSummary(
            id=row.id,
            name_kr=row.name_kr,
            name_en=row.name_en,
            tier=row.tier,
            description=row.description,
            is_legend_related=row.is_legend_related,
            # 정책(policies.md 1번): is_legend_related=true는 win_rate를 null로
            # 강제 — DB에 값이 남아있더라도(현재는 항상 NULL이지만 방어적으로)
            # 응답에서 절대 노출하지 않는다.
            win_rate=None if row.is_legend_related else row.win_rate,
        )
        for row in rows
    ]

    return AugmentsResponse(patch_version=resolved_patch, augments=augments)


@router.get("/patches/current", response_model=CurrentPatchResponse)
def get_current_patch(
    db: Annotated[Session, Depends(get_db)],
) -> CurrentPatchResponse:
    current = db.execute(
        select(Patch).where(Patch.is_current.is_(True))
    ).scalar_one_or_none()
    if current is None:
        raise _not_found_error("no_current_patch", "현재 패치가 설정되어 있지 않습니다")

    return CurrentPatchResponse(
        version=current.version,
        set_number=current.set_number,
        released_at=current.released_at,
        detected_at=current.detected_at,
    )
