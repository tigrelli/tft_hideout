from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/kpi", tags=["kpi"])


@router.get("/")
def kpi_root() -> dict[str, str]:
    return {"router": "kpi"}
