import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Comp, CompChampion, Patch
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

    resolved_patch = patch
    if resolved_patch is None:
        current = db.execute(
            select(Patch).where(Patch.is_current.is_(True))
        ).scalar_one_or_none()
        if current is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "no_current_patch",
                        "message": "현재 패치가 설정되어 있지 않습니다",
                    }
                },
            )
        resolved_patch = current.version

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
