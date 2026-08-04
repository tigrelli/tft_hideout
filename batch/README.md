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

## 모듈

- `opgg_client.py`(DATA-08): op.gg MCP(`https://mcp-api.op.gg/mcp`) TFT 도구 5종 호출 클라이언트. `tft_get_play_style`은 PUUID가 필요한 개인화 도구라 PGA-07에서 별도로 다룬다(`docs/spike/opgg-schema.md` 참고).
