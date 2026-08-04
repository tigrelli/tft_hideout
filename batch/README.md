# batch

GitHub Actions 기반 배치 워커. 패치 감지 폴링, 데이터 수집/정규화/임베딩을 담당한다. (DATA-* TASK)

## 개발

```
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format .
```

DB가 필요한 테스트(`test_data10_*`)는 `docker compose -f ../docker-compose.test.yml up -d` 후 `DATABASE_URL`/`TEST_DATABASE_URL`을 backend와 동일하게 설정하고 실행한다(policies.md 12번).

## 모듈

- `opgg_client.py`(DATA-08): op.gg MCP(`https://mcp-api.op.gg/mcp`) TFT 도구 5종 호출 클라이언트. `tft_get_play_style`은 PUUID가 필요한 개인화 도구라 PGA-07에서 별도로 다룬다(`docs/spike/opgg-schema.md` 참고).
- `id_name_mapping.py`(DATA-09): Community Dragon(`raw.communitydragon.org`) 기반 챔피언·특성 ID→이름 매핑. 매핑 누락 시 세트 접두어 제거 폴백.
- `db_session.py`: 배치용 DB 세션. 테이블 정의는 `backend/db/models.py`를 그대로 재사용한다(스키마 이중 관리 방지 — batch·backend가 같은 DB를 공유).
- `normalize.py`(DATA-10): op.gg/Community Dragon raw 응답 → 구조화 테이블(champions/traits/items/augments/comps/comp_champions/champion_item_builds) upsert. `comp_augments`는 op.gg 5개 도구 어디에도 데이터 소스가 없어 비워둠(추후 소스 확보 시 추가).
