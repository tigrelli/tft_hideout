import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import ChampionItemBuild, Comp, CompAugment, CompChampion, Patch
from db.session import get_db

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])

PATCH_PATTERN = re.compile(r"^\d+\.\d+$")
# op.gg 실제 랭크 구간 값은 DATA-05 스파이크 완료 후 확정 — 지금은 "all"만 실사용, 나머지는 자리표시
ALLOWED_RANKS = {"all", "challenger", "grandmaster", "master"}


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
    is_carry: bool
    recommended_items: dict


class AugmentInComp(BaseModel):
    augment_id: int
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
        select(CompChampion)
        .where(CompChampion.comp_id == comp_id)
        .order_by(CompChampion.is_carry.desc(), CompChampion.champion_id)
    ).scalars()
    champions = [
        ChampionInComp(
            champion_id=row.champion_id,
            is_carry=row.is_carry,
            recommended_items=row.recommended_items,
        )
        for row in champion_rows
    ]

    augment_rows = db.execute(
        select(CompAugment)
        .where(CompAugment.comp_id == comp_id)
        .order_by(CompAugment.priority)
    ).scalars()
    augments = [
        AugmentInComp(augment_id=row.augment_id, priority=row.priority)
        for row in augment_rows
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
