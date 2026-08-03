import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from routers import analysis, catalog, chat, kpi

app = FastAPI()

app.include_router(catalog.router)
app.include_router(chat.router)
app.include_router(analysis.router)
app.include_router(kpi.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """CLAUDE.md 10.1: 에러 응답은 {"error": {"code", "message"}} 구조로 고정."""
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = exc.detail
    else:
        content = {"error": {"code": "http_error", "message": str(exc.detail)}}
    return JSONResponse(status_code=exc.status_code, content=content)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/env-check")
def env_check() -> dict[str, bool]:
    return {"database_url_set": bool(os.getenv("DATABASE_URL"))}
