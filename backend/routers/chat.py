from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.get("/")
def chat_root() -> dict[str, str]:
    return {"router": "chat"}
