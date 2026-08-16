# CHAT-23 : 작업결과 (완료 — PM 승인 2026-08-16)

- **TASK**: Groq LLM 모델 마이그레이션(llama-3.3-70b-versatile 폐기 대응)
- **긴급도**: 높음 — Groq가 2026-06-17 공지, **2026-08-16(오늘) 폐기**. 폐기 이후 기존 모델로의 요청은 서빙되지 않아 방치 시 챗봇 전체(의도분류·오프토픽 검증·본답변 생성·후속질문 생성)가 즉시 중단됨.
- **계기**: PM이 Groq에서 받은 폐기 공지 메일 내용을 전달, 대체 모델 확인·적용 요청.

## 조사 내용

- Groq 공식 문서(`console.groq.com/docs/deprecations`) 확인 — `llama-3.3-70b-versatile` 폐기일 2026-08-16, 권장 대체 모델 `openai/gpt-oss-120b` 또는 `qwen/qwen3.6-27b`.
- `console.groq.com/docs/models` 확인 — `openai/gpt-oss-120b`는 **프로덕션(정식)** 등급, `qwen/qwen3.6-27b`는 **프리뷰(베타)** 등급. 둘 다 컨텍스트 윈도우 131,072 토큰.
- `console.groq.com/docs/rate-limits` 확인 — 무료 티어 기준 두 모델 동일: RPM 30 · TPM 8K · **TPD 200,000**(기존 llama-3.3-70b-versatile의 TPD 100,000 대비 2배 — TEST-11에서 발견한 하루 할당량 부족 문제 완화에도 도움).
- 프로덕션 서비스 안정성을 고려해 **정식 등급인 `openai/gpt-oss-120b`를 채택**, 프리뷰 등급 `qwen/qwen3.6-27b`는 보류.

## 변경 사항

- `backend/services/groq_client.py:7` — `GROQ_MODEL = "llama-3.3-70b-versatile"` → `GROQ_MODEL = "openai/gpt-oss-120b"` (한 곳에서 상수로 관리되어 `call_groq_chat`·`stream_groq_chat` 양쪽에 자동 반영, 의도분류·오프토픽 검증·본답변 생성·후속질문 생성 등 모든 Groq 호출 경로가 이 상수를 공유).
- `CLAUDE.md` 3장 기술스택 표의 "LLM 추론" 행 갱신, 11장 변경이력에 v1.14 추가.

## 자체 검증

- **pytest**: `docker-compose.test.yml`로 로컬 테스트 DB 기동 후 백엔드 전체 스위트 실행 — **352 passed**, 실패/에러 없음(정책상 테스트는 Groq를 mock하므로 이 통과는 "기존 로직이 모델 상수 교체로 깨지지 않았다"만 보증, 실제 모델 유효성은 아래 라이브 호출로 별도 확인).
- **라이브 스모크 테스트**(실제 Groq API 키로 직접 호출, `.env`의 `GROQ_API_KEY` 사용):
  - `call_groq_chat("...", "What is 2+2?")` → `"2 + 2 equals 4"` (정상 응답)
  - `stream_groq_chat("...", "TFT가 뭐야?")` → 스트리밍 정상 동작, 완결된 한국어 답변 생성 확인
- **프로덕션 사전 점검**(배포 전, 커밋 시점 기준 구모델 상태): `https://tft-hideout-backend.onrender.com/api/v1/chat/message`에 실제 질의 — 오프토픽("안녕")·TFT 질문("챔피언 상점에는 몇 명이 나오나요?") 둘 다 아직 정상 응답(폴백 아님). 폐기 공지일(2026-08-16) 당일이지만 Groq가 즉시 차단하지는 않은 것으로 확인됨 — 그럼에도 시한부 상태라 배포를 미룰 이유는 없음.
- 배포 후 프로덕션 스모크 확인은 이 문서 하단 "배포 후 확인" 절에 추가 예정.

## PM 결정 사항 (2026-08-16 승인)

- `openai/gpt-oss-120b` 채택 승인. TEST-11은 처음부터 재시작하지 않고 현재 진행 상태(A~D 완료 85/157, E 부분 3/15)를 그대로 이어받기로 결정 — 기존 발견 사항(B20/D4/D10/E2 등 확정 오답 계열)이 새 모델에서도 재현되는지는 카테고리 F~H 진행과 함께 자연스럽게 관찰하되, 별도의 소급 재검증 라운드는 진행하지 않음.
