# glossary.md — 용어·분류 체계 경량 참조본

> 원본: PRD v1.3 1장/4장, 요구사항정의서 v1.1 1.4/1.5절. 원본 버전이 바뀔 때만 이 파일을 갱신한다.
> 이 파일은 세션 시작 시 원본 .docx 대신 먼저 참조한다 (CLAUDE.md 2장).

## 핵심 용어

| 용어 | 정의 |
|---|---|
| sLLM | 소형 언어 모델. Groq 무료 티어가 호스팅하는 오픈소스 모델(Llama 3.3 70B 등) 사용 |
| RAG | 검색 증강 생성. 관련 문서를 먼저 검색하고 그 결과를 근거로 LLM이 답변 생성 |
| 패치(patch) | TFT 밸런스 업데이트 단위(약 2주 주기). 모든 레코드에 `patch_version` 태깅 |
| Personal Key | Riot API 키 단계. 심사 없이 발급, 레이트리밋 Development Key와 동일(상향 불가), 개인/소규모 비공개 커뮤니티 용도 |
| op.gg MCP | 메타 데이터(조합/아이템/증강체/빌드)의 1차이자 유일한 소스. TFT 도구 6종 중 5종은 집계·메타 전용(개인 전적 조회 없음), 나머지 1종(`tft_get_play_style`)은 Riot PUUID가 필요한 개인화 도구라 PGA-07(코칭 문장 생성)에서만 사용(DATA-05 스파이크 확인, 2026-08-04) |
| MVP | 이 프로젝트 범위 = 개인/비상업 목적, 본인+지인 약 10명 |

## 챗봇 의도 분류 (4종, 고정)

1. 조합 추천 — 검색 대상: comps, comp_champions, comp_augments
2. 아이템 추천 — 검색 대상: champion_item_builds
3. 증강체 추천 — 검색 대상: augments, comp_augments (is_legend_related=true는 win_rate 컨텍스트 제외)
4. 일반 전략 질문 — comps+augments+item_builds 통합 검색

1차 키워드/정규식 매칭 → 애매할 때만 2차 Groq LLM 분류.

## 반응형 브레이크포인트 (전체 서비스 공통)

| 구분 | 범위 | Tailwind 접두사 |
|---|---|---|
| 모바일 | < 768px | 기본(prefix 없음) |
| 태블릿 | 768px ~ 1023px | `md:` |
| 데스크톱 | 1024px 이상 | `lg:` |

## 요구사항 ID 접두어 (요구사항정의서 1.5)

| 접두어 | 구분 |
|---|---|
| FR-CAT / FR-CHB / FR-PGA / FR-DAT / FR-KPI | 기능요구사항(카탈로그/챗봇/사후분석/데이터/KPI) |
| NFR-PERF / NFR-AVL / NFR-SEC / NFR-CMP / NFR-OPS / NFR-UX | 비기능요구사항(성능/가용성/보안/정책준수/운영/UX) |
| IFR | 인터페이스 요구사항 |
| CR | 제약사항 |

## WBS 코드 접두어

`SET`(시스템설정) · `DATA`(데이터파이프라인) · `API`(백엔드API) · `CHAT`(챗봇RAG) · `PGA`(사후패인분석) · `FE`(프론트엔드) · `KPI`(KPI/모니터링) · `TEST`(테스트) · `REL`(배포/릴리즈)

## IA 화면 7개 (URL)

| 화면 | URL |
|---|---|
| 티어리스트(홈) | `/` (= `/tierlist`) |
| 조합 상세 | `/comps?id={comp_id}`(2026-08-04 PM 결정, 원문 IA v1.2는 `/comps/{comp_id}` — 정적 export에서 패치마다 comp_id가 전부 새로 생겨 재배포 없이는 신규 조합 상세 링크가 깨지는 문제를 원천 차단하기 위해 쿼리스트링으로 변경, FE-04 작업결과 참고) |
| 아이템 빌드 | `/items/builds` |
| 증강체 정보 | `/augments` |
| 사후 패인 분석 | `/analysis` |
| 분석 리포트 상세 | `/analysis/{match_id}/report` |
| 챗봇 위젯 | 없음(전역 컴포넌트) |
