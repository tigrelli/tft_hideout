from fastapi import APIRouter

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/")
def catalog_root() -> dict[str, str]:
    return {"router": "catalog"}
