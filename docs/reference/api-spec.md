# api-spec.md — API 명세 경량 참조본

> 원본: 개발설계서 v1.6 4.2·6장, 요구사항정의서 v1.1 5.2/5.3절.
> 이 파일은 세션 시작 시 원본 .docx 대신 먼저 참조한다 (CLAUDE.md 2장).

## 공통 규칙

- 단일 FastAPI 앱, 3개 라우터로 논리 분리: `/api/v1/catalog/*`(LLM 미경유, SQL 직접 조회) · `/api/v1/chat/*`(RAG+sLLM) · `/api/v1/analysis/*`(사후 패인 분석)
- 인증 없음(회원 시스템 미사용). IP 기준 rate limiting만 적용: `catalog/*` 분당 60회, `chat/*` 분당 10회
- `session_id`(UUID)는 클라이언트가 최초 접속 시 발급, 회원 식별자 아닌 대화 묶음 키로만 사용
- 챗봇 응답은 SSE(Server-Sent Events) 스트리밍
- 배치 워커(GitHub Actions)와 Metabase는 이 API를 거치지 않고 Supabase Postgres에 직접 연결

## 엔드포인트 목록

| Method | Path | 설명 | 담당 TASK |
|---|---|---|---|
| GET | `/api/v1/catalog/tierlist?patch=&rank=` | 티어리스트 조회 | API-02 |
| GET | `/api/v1/catalog/comps/{comp_id}` | 조합 상세 조회 | API-03 |
| GET | `/api/v1/catalog/items/builds?champion_id=&patch=` | 아이템 빌드 조회 | API-04 |
| GET | `/api/v1/catalog/augments?patch=&tier=` | 증강체 목록 조회(Legend 마스킹 포함) | API-05 |
| GET | `/api/v1/catalog/patches/current` | 현재 패치 정보 조회 | API-06 |
| POST | `/api/v1/chat/message` | 챗봇 메시지 전송(SSE 스트리밍) | API-09, CHAT-01~10 |
| GET | `/api/v1/chat/session/{session_id}/history` | 대화 이력 조회(drill-down용, 최근 3턴) | API-10 |
| POST | `/api/v1/analysis/link` | Riot ID → PUUID 변환(TTL 1시간 캐시) | API-11 |
| POST | `/api/v1/analysis/recent` | 최근 매치 분석 요청 | API-12, PGA-01~10 |
| GET | `/api/v1/analysis/{match_id}/report` | 상세 리포트 조회 | API-13 |

## 프론트엔드-백엔드 인터페이스

- 세션: `crypto.randomUUID()`로 클라이언트 발급, 이후 요청에 계속 실어 보냄
- 스트리밍: 챗봇 답변은 SSE로 체감 지연 최소화
- 클라이언트 저장: 사후 패인 분석 "최근 조회 계정 목록"은 브라우저 localStorage 배열(최대 5개, 화면설계서 2.5 가정)

## 외부 연동 (배치/실시간)

| 대상 | 호출 방식 | 용도 |
|---|---|---|
| op.gg MCP | 배치(GitHub Actions 크론, 매시간) | 메타 데이터 5종 도구(DATA-08) + `tft_get_play_style`은 PGA-07에서 실시간 호출(PUUID 필요, 2026-08-04 DATA-05 스파이크 결정) |
| Riot API (Match-V1) | 실시간(분석 요청 시점) | 개인 매치 조회 전용 |
| TFT DDragon | 배치(보조 신호) | ID↔이름 매핑 |
| Groq API | 실시간(SSE 스트리밍) | sLLM 추론(Llama 3.3 70B) |
| Hugging Face Inference API | 배치+실시간 | 임베딩(BGE-M3, 1024차원) |
