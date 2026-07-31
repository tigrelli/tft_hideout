# TFT Hideout

TFT(전략적 팀 전투) 메타 정보 sLLM + RAG 서비스 — 웹사이트(카탈로그) + 챗봇(RAG+sLLM) + 사후 패인 분석.

개인/비상업 목적 MVP. 개발 진행 규칙은 [CLAUDE.md](CLAUDE.md), 실제 작업 현황은 [진행현황.md](진행현황.md)를 따른다.

## 저장소 구조

```
/frontend   - Next.js 앱 (FE-* TASK)
/backend    - FastAPI 앱 (API-*, CHAT-*, PGA-* TASK)
/batch      - GitHub Actions 배치 워커, 데이터 수집/정규화/임베딩 (DATA-* TASK)
/docs       - 기획 문서, WBS, 진행현황, 스파이크 리포트
```
