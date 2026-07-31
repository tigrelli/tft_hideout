import os

from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/env-check")
def env_check() -> dict[str, bool]:
    return {"database_url_set": bool(os.getenv("DATABASE_URL"))}
