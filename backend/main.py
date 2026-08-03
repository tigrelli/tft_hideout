import os

from fastapi import FastAPI

from routers import analysis, catalog, chat, kpi

app = FastAPI()

app.include_router(catalog.router)
app.include_router(chat.router)
app.include_router(analysis.router)
app.include_router(kpi.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/env-check")
def env_check() -> dict[str, bool]:
    return {"database_url_set": bool(os.getenv("DATABASE_URL"))}
