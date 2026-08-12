# SET-17 : 작업결과

- **TASK**: 웹 검색 API 키 발급 및 검증(Tavily)
- **상태**: 완료(PM 승인 2026-08-12)
- **선행 TASK**: -
- **근거 문서**: PM 결정(2026-08-12, 웹검색 스코프 검토), SET-10 발급 절차 패턴

## 결과 요약

CHAT-17(웹검색 기반 일반 게임 정보 답변)에 필요한 Tavily API 키를 발급하고 로컬 `.env`·GitHub Secrets·Render 환경변수에 등록했다. Tavily는 무료 티어가 월 1,000크레딧으로 매월 갱신되는 방식이라(카드 등록 불요) Groq/HF와 같은 "무료 인프라 한도" 운영 패턴에 부합한다(2026-08-12 스코프 검토 시 Serper 등과 비교해 채택).

- `.env`: PM이 `TAVILY_API_KEY` 등록
- `.env.example`: 키 항목 추가(값 없이, 다른 키와 동일 패턴)
- GitHub Secrets: PM이 저장소 시크릿에 등록(대시보드 확인)
- Render: PM이 `tft-hideout-backend` 서비스 환경변수에 등록(대시보드 확인)

## 자체 검증

- 로컬에서 실제 Tavily Search API 1회 호출(`query="TFT Set 18 release date"`) → HTTP 200, 검색 결과 3건 정상 수신(실제 URL·제목 포함)
- 상세 로그: `docs/verification/smoke-tests.md` SET-17 항목

## 보류 항목

- Render 환경변수의 라이브 반영 확인(`/env-check` 확장 등)은 지금 push하면 CHAT-16·존댓말 수정과의 배치 커밋 계획과 어긋나므로, CHAT-17 실제 배포 시점에 함께 진행하기로 PM과 합의(2026-08-12)
