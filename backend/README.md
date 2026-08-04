# backend

FastAPI(Python) 단일 앱, catalog/chat/analysis/kpi 4개 라우터. Render에 배포한다. (API-*, CHAT-*, PGA-* TASK, API-01에서 스캐폴딩 예정)

## 로컬 테스트 실행

DB 마이그레이션 관련 테스트는 로컬 Docker Postgres(pgvector)를 사용한다(운영 Supabase에 붙지 않음, `docs/reference/policies.md` 12번).

```bash
# 저장소 루트에서
docker compose -f docker-compose.test.yml up -d

cd backend
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt -r requirements-dev.txt
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5433/tft_hideout_test"
pytest
```

## Alembic 마이그레이션

- 모델: `db/models.py` (SQLAlchemy declarative)
- `alembic revision --autogenerate -m "<설명>"` 후 `alembic/versions/`의 파일명을 `<타임스탬프>_<WBS코드>_<설명>.py` 형식으로 변경
- `alembic upgrade head`로 적용
