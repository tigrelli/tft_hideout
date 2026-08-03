from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


@router.get("/")
def analysis_root() -> dict[str, str]:
    return {"router": "analysis"}
