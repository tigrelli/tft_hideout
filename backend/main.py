import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from middleware.rate_limit import RateLimitMiddleware
from routers import analysis, catalog, chat, kpi

app = FastAPI()

# 모든 API는 인증 없이 공개 호출되므로(policies.md 6번, IP 기준 rate limit만 적용)
# 쿠키/세션 자격증명이 없어 allow_credentials 없이 오리진만 허용해도 안전하다.
# FE-03에서 실제 브라우저로 호출해보고 나서야 CORS 미설정으로 전부 막혀있던
# 걸 발견(pytest TestClient·curl은 브라우저 CORS 정책을 적용하지 않아 못 봤음).
ALLOWED_ORIGINS = [
    "https://tft-hideout.suraholic.workers.dev",  # SET-07 배포 URL
    "http://localhost:3000",
    "http://localhost:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)

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
