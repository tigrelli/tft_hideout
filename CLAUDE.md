# CLAUDE.md — TFT Hideout 개발 가이드

이 문서는 **클로드 코드(Claude Code)**가 이 저장소에서 작업할 때 반드시 따라야 하는 규칙을 정의한다.
프로젝트의 실제 진행 상태와 다음 작업 지시는 이 문서가 아니라 **`진행현황.md`**를 항상 최신 기준으로 삼는다.

---

## 1. 프로젝트 개요

- **프로젝트명**: TFT Hideout
- **제품**: TFT(전략적 팀 전투) 메타 정보 sLLM + RAG 서비스 — 웹사이트(카탈로그) + 챗봇(RAG+sLLM) + 사후 패인 분석
- **범위**: 개인/비상업 목적 MVP (본인 + 지인 약 10명 규모)
- **팀 구성**: PM 1명 + 클로드 코드(개발 전담). 클로드 코드는 아래 4장 워크플로우를 반드시 준수한다.
- **근거 문서** (읽기 전용, 저장소 루트에 위치):
  - `/docs/reference/*.md` — **세션 시작 시 1차로 참조하는 경량 요약본** (glossary/schema/api-spec/policies/design-tokens, 2장 참고)
  - `/docs/source/*.docx` — **각 문서의 최신 확정본 원본** (아래 6종, 세부 rationale·특정 절 대조가 필요할 때만 열람):
    - `TFT_sLLM_PRD_v1.3_최종.docx` — 제품 요구사항 (무엇을·왜 만드는지, 확정본)
    - `TFT_sLLM_개발설계서_v1.7.docx` — 기술 설계 (아키텍처·DB 스키마·API 명세)
    - `TFT_sLLM_IA_v1.1.docx` — 정보구조(사이트맵·URL·화면-데이터 매핑)
    - `TFT_sLLM_화면설계서_v1.2.docx` — 화면별 컴포넌트·인터랙션·반응형 스펙 (Figma "TFT_Hideout" 연동)
    - `TFT_sLLM_디자인가이드_v1.0.docx` — 컬러·타이포그래피·컴포넌트 시각 규칙
    - `TFT_sLLM_요구사항정의서_v1.1.docx` — 요구사항 ID(FR-*, NFR-*) 단위 정리본
  - `/docs/archive/*` — 구버전 초안(PRD v1.2, 개발설계서 v1.5·v1.6, 화면설계서 v1.0/v1.1, IA v1.0, 요구사항정의서 v1.0, 브레인스토밍.md). **이 폴더는 참조하지 않는다** — 이력 보존용이며 최신 근거가 아니다.
  - `TFT_Hideout_WBS.xlsx` — 전체 작업분해구조(WBS), 94개 TASK. `테스트 요구사항` 컬럼(K열)에 TASK별 구체적 테스트 항목이 명시되어 있다
  - `진행현황.md` — **실제 개발은 이 파일 기준으로 진행한다**
  - `/docs/test-scenarios.md` — TEST-00에서 작성하는 정책·크리티컬 로직 테스트 시나리오 문서 (TEST-00 완료 후 생성됨)
  - `/docs/spike/*.md` — DATA-05~07 스파이크 결과 기록

문서 간 내용이 다르면 PRD(v1.3) → 개발설계서(v1.7) → IA/화면설계서/디자인가이드 순으로 우선한다. `/docs/reference/*.md`는 원본을 압축한 요약본이므로, 원본과 다르면 원본이 맞다 — 이 경우 SET-15 TASK를 다시 열어 참조본을 갱신한다. 새 문서 버전이 나오면 이전 버전은 `/docs/archive/`로 옮기고 `/docs/source/`에는 항상 최신 확정본 1개만 유지한다.

---

## 2. 세션 시작 시 컨텍스트 로딩 규칙 (토큰 최소화)

클로드 코드 세션은 매번 새로 시작되며 이전 세션의 대화 기록을 기억하지 못한다. 원본 근거 문서 6종은 각각 수십 페이지 분량의 `.docx`이므로, TASK 하나를 위해 매번 전체를 다시 읽으면 토큰이 크게 낭비된다. 아래 규칙을 지킨다.

### 2.1 세션 시작 시 항상 읽는 것 (최소 세트)

1. `CLAUDE.md`(이 문서) — 전체
2. `진행현황.md` — 전체 정독 대신 이번에 착수할 TASK 행과 그 선행 TASK 상태만 확인(WBS 코드로 검색)
3. `TFT_Hideout_WBS.xlsx` — 해당 TASK **행 1개**(TASK설명·근거문서·완료기준·테스트요구사항 컬럼)만 확인, 파일 전체를 훑지 않는다
4. `/docs/reference/*.md` 중 아래 2.3 표에서 해당 TASK 그룹에 맞는 파일 1~2개 — 원본 `.docx`보다 훨씬 짧은 경량 요약본

### 2.2 원본 `.docx`는 아래 경우에만 연다

- `/docs/reference/*.md`에 없는 세부 rationale·배경 설명이 필요할 때
- WBS `근거 문서` 컬럼이 가리키는 특정 절(예: "설계서 4.5.1")의 원문을 직접 대조해야 할 때 — 이때도 문서 전체를 읽지 말고 해당 절 근처만 확인한다
- 문서 간 내용이 상충해 1장의 우선순위 규칙으로도 해결이 안 될 때

### 2.3 TASK 그룹별 최소 참조 파일

| TASK 그룹 | 우선 참조 | 필요시에만(원본) |
|---|---|---|
| SET-* | 이 문서 5·10장 | 설계서 2·7장(인프라 스택 상세) |
| DATA-* | `schema.md`, `/docs/spike/*.md`(스파이크 완료 후) | 개발설계서 4.3·5장 |
| API-* | `schema.md`, `api-spec.md` | 개발설계서 4.2·6장 |
| CHAT-* | `policies.md`, `glossary.md`(의도 4분류) | 개발설계서 4.4 전체 |
| PGA-* | `schema.md`, `/docs/test-scenarios.md`(TEST-00 완료본) | 개발설계서 4.5 전체 |
| FE-* | `design-tokens.md`, 화면설계서의 **해당 화면 절만** | 디자인가이드 전체, Figma MCP |
| KPI-* | `schema.md`(로그 테이블) | PRD 3-3 |
| TEST-* | 대상 TASK들의 WBS 행 + `/docs/test-scenarios.md` | - |

### 2.4 세션 종료 시 지식 기록

새로 확인한 사실(스파이크 결과, 애매했던 부분에 대한 PM 결정 등)은 다음 세션이 같은 조사를 반복하지 않도록 즉시 `/docs/spike/*.md` 또는 `/docs/reference/*.md`에 append한다. 이 파일들은 "다음 세션의 나"를 위한 메모라고 생각하고 기록한다.

### 2.5 절대 하지 말 것

- 세션 시작 시 6개 원본 `.docx`를 습관적으로 전부 재확인하지 않는다.
- `진행현황.md`나 `TFT_Hideout_WBS.xlsx` 전체를 처음부터 끝까지 다시 읽지 않는다 — 필요한 TASK 코드만 찾아서 본다.
- 이미 구현된 코드가 문서와 다르면 임의로 문서를 재해석해 코드에 맞추지 말고, 먼저 PM에게 어느 쪽이 최신인지 확인한다.

---

## 3. 기술 스택 (개발설계서 2장 확정 사항)

| 영역 | 선택 |
|---|---|
| 프론트엔드 | Next.js(React), Tailwind CSS, Cloudflare Pages 배포 |
| 백엔드 | FastAPI(Python), Render 무료 컨테이너, 단일 앱 내 3개 라우터(catalog/chat/analysis) |
| 구조화 DB | PostgreSQL (Supabase 무료) |
| 벡터 DB | pgvector (Supabase 내장, HNSW 인덱스) |
| 캐시 | PostgreSQL 테이블 (`chat_answer_cache`, `puuid_cache`) — 별도 캐시 인프라 없이 구조화 DB 재사용 (v1.7, 이전 Redis/Upstash) |
| LLM 추론 | Groq API 무료 티어 · Llama 3.3 70B Versatile |
| 임베딩 | BGE-M3 (Hugging Face Inference API) |
| RAG 프레임워크 | LangChain (Python) |
| 배치 스케줄러 | GitHub Actions (패치 감지 폴링 + 배치 워커) |
| KPI 대시보드 | Metabase (Render 2번째 서비스) |
| RAG 품질 평가 | RAGAS (주간 배치) |

브레이크포인트: 모바일 `<768px` / 태블릿 `768~1023px` / 데스크톱 `1024px~` (Tailwind 기본 `md:`/`lg:` 그대로 매핑).

---

## 4. 개발 진행 워크플로우 (필수 준수)

이 프로젝트는 **PM 1명 + 클로드 코드**로 운영된다. 아래 순서를 어떤 상황에서도 건너뛰지 않는다.

1. **작업 선택**: `진행현황.md`에서 상태가 `대기`이고 선행 TASK가 모두 `완료`인 TASK를 WBS 코드 순서(그룹 → 하위영역 → 번호)로 선택한다. 어떤 TASK를 하는지 세션 시작 시 PM에게 먼저 알린다. 선택한 TASK가 `진행현황.md`의 "테스트 시나리오 사전 정의 현황(TEST-00)" 표에 포함된 항목(API-05, CHAT-04, CHAT-06, PGA-04/05/06/07/09, DATA-13)이라면, TEST-00이 먼저 완료되어 시나리오 문서(`/docs/test-scenarios.md`)가 존재하는지 확인한 뒤 착수한다.
2. **테스트 작성**: WBS `테스트 요구사항` 컬럼(K열)에 명시된 테스트를 먼저 작성한다(가능한 경우 구현 이전에, 최소한 구현과 함께). 정책·크리티컬 로직 TASK는 1번에서 확인한 사전 시나리오 문서를 그대로 테스트 케이스로 옮긴다.
3. **구현**: 선택한 TASK 1개 단위로만 구현한다. 여러 TASK를 한 번에 묶어 진행하지 않는다(WBS는 클로드 세션 단위로 최소 분할되어 있음).
4. **자체 검증**: TASK의 완료 기준(DoD, WBS `완료 기준` 컬럼)과 2번에서 작성한 테스트가 모두 통과하는지 스스로 점검한다. 테스트가 없거나 실패하면 완료로 보고하지 않는다.
5. **PM 확인 요청**: 구현이 끝나면 반드시 PM에게 결과(변경 파일, 테스트 실행 로그, 스크린샷 등)를 제시하고 **완료 여부 확인을 요청**한다. **PM 확인 전에는 절대 완료 처리하지 않는다.**
6. **진행현황 업데이트**: PM이 확인(승인)한 뒤에만 `진행현황.md`의 해당 WBS 코드 행 상태를 `완료`로, PM확인 컬럼을 갱신한다. PM이 수정을 요청하면 상태를 `진행중`으로 유지하고 반영 후 다시 5번으로 돌아간다.
7. **커밋/푸시**: **git 커밋과 push는 PM이 완료를 확인한 이후에만 실행한다.** PM 확인 전 커밋/푸시 금지. 커밋 메시지는 10장의 Conventional Commits 규칙 + WBS 코드를 따른다. 예: `feat(FE-03): 티어리스트 홈 페이지 구현`. PR을 올리면 SET-14의 CI 게이트가 테스트를 자동 실행하므로, 실패 시 머지 전에 반드시 수정한다.
8. **다음 TASK로 이동**: 7번까지 끝난 후에만 다음 TASK를 선택한다.

> 요약: **작업선택(사전 시나리오 확인) → 테스트 작성 → 구현 → 자체검증(테스트 통과) → PM확인요청 → (승인) → 진행현황.md 갱신 → git commit/push(CI 통과) → 다음 TASK.** 이 순서를 반대로 하지 않는다(특히 커밋을 먼저 하고 나중에 확인받는 방식, 테스트 없이 완료 보고하는 방식 모두 금지).

### 커밋/브랜치 규칙
- 브랜치: `main`(배포 대상) / `develop`(통합) / `task/{WBS코드}`(개별 작업, 예: `task/FE-03`)
- PR 제목에도 WBS 코드를 포함한다.
- PM 승인 없이 `main`/`develop`에 직접 push하지 않는다.

---

## 5. 저장소 구조 (SET-03 기준)

```
/frontend   - Next.js 앱 (FE-* TASK)
/backend    - FastAPI 앱 (API-*, CHAT-*, PGA-* TASK)
/batch      - GitHub Actions 배치 워커, 데이터 수집/정규화/임베딩 (DATA-* TASK)
/docs       - 기획 문서, WBS, 진행현황, 스파이크 리포트
  /docs/reference  - 경량 참조본(glossary/schema/api-spec/policies/design-tokens.md, SET-15)
  /docs/source     - 근거 문서 원본의 최신 확정본만(docx 6종), 항상 이 폴더 것을 기준으로 삼는다
  /docs/archive    - 구버전 초안(참조 금지, 이력 보존용)
  /docs/spike      - DATA-05~07 스파이크 결과
```

---

## 6. 프론트엔드 작업 시 디자인 스킬 사용 규칙 (SET-12 연계)

FE-* TASK(프론트엔드 코딩)를 진행할 때는 임의로 스타일을 새로 정의하지 말고 아래 소스를 우선 참조한다.

1. **`/docs/reference/design-tokens.md`** — 컬러 토큰, 타이포그래피, spacing, 컴포넌트 반경 등 확정 값의 1차 참조(2장 원칙). 상세 배경이 필요할 때만 디자인가이드 원본(`/docs/source/TFT_sLLM_디자인가이드_v1.0.docx`) 확인.
2. **Figma 파일** "TFT_Hideout" (화면설계서 v1.2에 URL 기재) — 데스크톱 와이어프레임 원본. Figma MCP(Dev Mode)가 연결되어 있다면 `get_design_context`/`get_screenshot` 등으로 실제 프레임을 조회해 구현과 대조한다.
3. **화면설계서**(`/docs/source/TFT_sLLM_화면설계서_v1.2.docx`) — 해당 TASK가 다루는 화면 절만 열람(화면별 컴포넌트 목록·상태(state)·반응형 동작표).
4. Cowork/Claude Code 환경에 `screen-design-generator` 스킬 또는 Figma MCP 커넥터가 설치되어 있지 않다면, 새 FE-* TASK를 시작하기 전에 PM에게 설치를 요청한다(1회성 설정, SET-12).
5. 디자인가이드·화면설계서에 "디자인 재량"/"미확정"으로 표시된 항목(티어 배지 색상 등)은 `design-tokens.md` 하단 "미확정 항목"의 권장안을 기본값으로 채택하고, 변경이 필요하면 구현 전에 PM에게 확인한다.

---

## 7. 구현 시 반드시 지켜야 할 정책 (놓치면 안 되는 항목)

전체 체크리스트는 `/docs/reference/policies.md` 참고. 핵심만 요약:

- **Legend 계열 증강체 승률 비노출**: `is_legend_related=true`인 증강체는 웹사이트·챗봇 어디서도 승률을 표시하지 않는다. 전처리(컨텍스트 제외)와 후처리(정규식 재검사) 이중 방어 필수 (API-05, CHAT-06).
- **상대 플레이어 프라이버시**: 사후 패인 분석에서 비식별 상대 Riot ID 노출 금지, 닉네임 마스킹은 LLM 생성 이후 정규식으로 재확인 (PGA-09).
- **패치 데이터 정합성**: 모든 레코드에 `patch_version` 태깅, `patches.is_current`는 전체 배치가 성공한 마지막 순간에만 트랜잭션으로 전환 (DATA-13).
- **비로그인 세션**: 회원가입/로그인 시스템을 만들지 않는다. `session_id`(UUID)는 대화 묶음 키일 뿐 회원 식별자가 아니다.
- **RAG 근거 원칙**: 챗봇 답변은 검색된 문서에 없는 내용을 추측하지 않고, 패치 버전과 근거를 항상 명시한다.
- **인증 없음**: 모든 API는 인증을 두지 않고 IP 기준 rate limiting만 적용한다(catalog 분당 60, chat 분당 10).
- **무료 인프라 한도**: Render 콜드스타트, Groq/HF 무료 티어 요청 제한을 항상 고려해 재시도·폴백을 구현한다.

---

## 8. 구현 착수 시 먼저 처리할 스파이크 (DATA-05, DATA-06, DATA-07)

아래 3개는 PRD/개발설계서가 "1.0 확정을 막는 항목이 아니라 구현 착수 시 1회 확인하면 되는 스파이크"로 명시한 항목이다. 데이터 파이프라인(DATA-08 이후) 작업 전에 반드시 먼저 수행하고 결과를 `/docs/spike/`에 기록한다.

1. op.gg MCP 실제 응답 스키마 확인 (patch_version 상당 필드 존재 여부)
2. TFT DDragon 신규 구조 확인 (Set 18, 2026-08-12 언리얼 엔진 이전에 따른 분리)
3. `is_legend_related` 판별 방법 확인 (라벨 존재 여부, 없으면 수동 유지 목록)

---

## 9. 범위 외 (이번 개발에 포함하지 않음)

로그인/RSO 인증, 이용약관·개인정보처리방침 페이지, 디스코드봇 등 챗봇 추가 채널, 실시간 인게임 오버레이 코칭, 유료 인프라 전환, LLM이 직접 분석 판단을 내리는 AI 코칭 고도화. (상세: PRD 14장·15장, 요구사항정의서 8장)

---

## 10. 코딩 컨벤션 및 테스트 규칙

### 10.1 언어별 코딩 컨벤션

**백엔드/배치 (Python, `/backend`, `/batch`)**
- 포맷/린트: `ruff`(format+lint) 필수. 커밋 전 `ruff check .`, `ruff format .` 통과.
- 타입: 함수 시그니처(파라미터·반환값)에 타입힌트 필수. 전체 strict mypy는 MVP 규모상 강제하지 않되, `match_analyses` 스코어링(PGA-04~07)과 정책 마스킹(API-05, CHAT-06, PGA-09) 관련 모듈은 mypy 통과를 권장.
- API 요청/응답: 모든 엔드포인트는 Pydantic 모델로 요청/응답 스키마를 정의한다(암묵적 dict 반환 금지).
- 에러 응답 포맷 통일: `{"error": {"code": "...", "message": "..."}}` 구조로 고정, HTTP 상태코드와 함께 반환.
- 네이밍: 변수/함수 `snake_case`, 클래스 `PascalCase`, 모듈/파일명 `snake_case`. docstring·주석은 한국어 허용.
- DB 마이그레이션: Alembic 사용. 마이그레이션 파일명에 해당 WBS 코드 포함(예: `202607301200_data01_create_patches.py`).
- 로깅: 구조화 로그(JSON). `riot_id`, `puuid`, 상대 닉네임 등 민감정보는 로그에도 마스킹 후 기록(콘솔·파일 모두 원문 금지).
- 시크릿: 코드/커밋에 API 키·DB 비밀번호 하드코딩 금지. `.env`(로컬)·GitHub Secrets·Render/Cloudflare 환경변수만 사용, `.env`는 `.gitignore`에 포함.

**프론트엔드 (TypeScript/Next.js, `/frontend`)**
- 포맷/린트: ESLint + Prettier 필수, TypeScript `strict: true`.
- 네이밍: 컴포넌트 파일/함수 `PascalCase`, 훅 `useXxx`, 파일명은 컴포넌트 `PascalCase.tsx` 그 외 `kebab-case`.
- 상태: 서버 데이터는 컴포넌트 로컬 fetch 대신 공용 데이터 fetching 유틸(예: 공통 API 클라이언트)로 통일.
- 접근성: 인터랙티브 요소(버튼·드롭다운·바텀시트)는 최소한의 `aria-*` 속성과 키보드 포커스 처리를 포함한다.

### 10.2 테스트 규칙 (TASK별 필수)

- **원칙**: DATA-*/API-*/CHAT-*/PGA-*/FE-*/KPI-* 코딩 TASK는 각각 WBS `테스트 요구사항` 컬럼에 명시된 자동화 테스트를 작성하고 통과해야 4번(자체 검증)을 만족한 것으로 간주한다. 별도의 `TEST-*` 그룹(TEST-00~10)은 개별 TASK 단위 테스트를 대체하는 것이 아니라, 여러 TASK가 끝난 뒤 통합·회귀·정책 준수를 교차 검증하는 후속 단계다.
- **프레임워크**: 백엔드/배치 = `pytest`(+ FastAPI `TestClient`) · 프론트엔드 컴포넌트 = `Vitest` + `React Testing Library` · 프론트엔드 E2E = `Playwright`(TEST-08이 전체 플로우 통합) · RAG 품질 = `RAGAS`(KPI-02).
- **사전 시나리오 정의(TEST-00)**: 정책 준수·크리티컬 계산 로직이 걸린 TASK(`API-05`, `CHAT-04`, `CHAT-06`, `PGA-04`, `PGA-05`, `PGA-06`, `PGA-07`, `PGA-09`, `DATA-13`)는 구현에 착수하기 전에 `/docs/test-scenarios.md`에 입력값·기대출력·경계값을 표로 정리하고 PM 합의를 받는다(TEST-00, 진행현황.md "테스트 시나리오 사전 정의 현황" 표 참고). 이 문서가 곧 해당 TASK의 테스트 케이스 초안이 된다.
- **외부 API 목(mock) 정책**: 자동화 테스트에서 op.gg MCP·Riot API·Groq·Hugging Face를 실제로 호출하지 않는다. DATA-05~07 스파이크 결과를 기반으로 한 고정 fixture(JSON)를 사용해 Personal Key 레이트리밋·무료 티어 한도를 테스트에서 소모하지 않는다. 실제 연동 확인은 각 SET-* 스모크 테스트(1회성)로 한정한다.
- **fixture는 반드시 합성(가짜) 데이터로 구성**: op.gg/Riot API 스파이크(DATA-05~07)로 실제 응답 스키마(필드 구조)는 확인하되, pytest fixture에 박아넣는 값 자체는 실제 Riot ID·PUUID·닉네임·매치 데이터를 그대로 복사하지 않고 합성 값으로 치환한다(스키마는 실제, 값은 가짜). 이는 저장소를 향후 public으로 전환할 가능성(REL-05 참고)을 염두에 둔 조치로, 나중에 git 히스토리를 정리할 필요가 없게 만든다.
- **CI 게이트(SET-14)**: PR 생성/push 시 GitHub Actions가 backend pytest와 frontend Vitest를 자동 실행하고, 실패 시 브랜치 보호 규칙으로 머지를 차단한다. 로컬에서 테스트를 건너뛰고 커밋하더라도 PR 단계에서 최종적으로 걸러진다.
- **커밋 컨벤션**: Conventional Commits 접두어(`feat`/`fix`/`test`/`chore`/`docs`/`refactor`) + WBS 코드. 예: `test(PGA-04): 조합 이탈도 계산 단위 테스트 추가`, `fix(CHAT-06): Legend 승률 후처리 필터 누락 수정`.

---

## 11. 문서 변경 이력

| 버전 | 일자 | 내용 |
|---|---|---|
| v1.0 | 2026-07-30 | WBS(90개 TASK)·진행현황.md와 함께 최초 작성. 근거: PRD v1.3(최종), 개발설계서 v1.6, IA v1.1, 화면설계서 v1.2, 디자인가이드 v1.0, 요구사항정의서 v1.1 |
| v1.1 | 2026-07-30 | PM 리뷰 반영 — 9장 "코딩 컨벤션 및 테스트 규칙" 신설(언어별 컨벤션, TASK별 테스트 프레임워크, mock 정책, CI 게이트, 사전 테스트 시나리오 규칙). 워크플로우(3장)에 "테스트 작성" 단계 및 CI 통과 조건 추가. WBS에 `테스트 요구사항` 컬럼과 SET-14(CI 테스트 게이트)·TEST-00(핵심 시나리오 사전정의) TASK 추가되어 전체 92개 TASK로 갱신 |
| v1.2 | 2026-07-30 | PM 리뷰 반영 — 2장 "세션 시작 시 컨텍스트 로딩 규칙" 신설(토큰 최소화를 위한 최소 읽기 세트, TASK 그룹별 참조 파일 매핑, 세션 종료 시 지식 기록 규칙). `/docs/reference/*.md` 5종(glossary/schema/api-spec/policies/design-tokens) 신규 작성 및 SET-15 TASK로 반영, 전체 93개 TASK로 갱신. 전 섹션 번호 재정렬(2장 삽입에 따라 기존 2~10장이 3~11장으로 이동) |
| v1.3 | 2026-07-30 | 근거 문서 원본을 저장소 루트에서 `/docs/source/`(최신 확정본 6종)와 `/docs/archive/`(구버전 초안·브레인스토밍, 참조 금지)로 재정리. 1장·5장·6장의 문서 경로 표기를 `/docs/source/...`로 갱신 |
| v1.4 | 2026-07-30 | PM 결정 반영 — 향후 저장소를 포트폴리오 목적으로 public 전환할 가능성을 대비해 10.2절에 "fixture는 합성 데이터로만 구성" 규칙 추가. `/docs/reference/policies.md`에 11번(테스트 fixture 프라이버시) 신설. REL-05(포트폴리오 공개 전환 준비 체크리스트) TASK를 배포릴리즈 그룹 마지막에 신규 추가, 전체 94개 TASK로 갱신 |
| v1.5 | 2026-07-31 | PM 결정 반영 — Redis(Upstash) 제거, 캐싱을 PostgreSQL 테이블(`chat_answer_cache`, `puuid_cache`) 기반으로 전환. 3장 기술스택 표 갱신, 근거 문서를 개발설계서 v1.7(3장·4.6절·5장·7장·9장 갱신, `/docs/source/`)로 교체하고 구버전 v1.6은 `/docs/archive/`로 이동. WBS SET-05(Upstash Redis 생성) 취소, DATA-03/DATA-15/CHAT-08 TASK 설명을 Postgres 기반으로 갱신(진행현황.md·WBS.xlsx 동시 반영). TASK 수는 94개 유지(SET-05는 취소 상태로 코드 결번 보존) |
