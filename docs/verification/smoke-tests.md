# 인프라 배포/시크릿 스모크 테스트 기록

SET-* 등 인프라 TASK의 1회성 스모크 테스트 결과를 WBS 코드별로 기록한다.
CLAUDE.md 10.2절 정책에 따라 이런 실제 배포/시크릿 확인은 CI에 자동화하지 않고
콘솔에서 1회성으로 검증하므로, 검증한 사실 자체를 여기 남겨 다음 세션이
반복 조사하지 않도록 한다. `진행현황.md` 변경 이력에는 한 줄 요약만 남긴다.

## SET-06 (2026-07-31)

- Render 웹서비스 `tft-hideout-backend` 생성(Singapore 리전), `render.yaml` Blueprint로 배포 설정
- 더미 FastAPI 앱(`/health`)으로 검증: pytest·ruff 통과
- `develop`→`main` PR #1 머지 시 Render 자동 재배포 확인
- 배포 URL `https://tft-hideout-backend.onrender.com/health` → 200, `{"status":"ok"}`

## SET-07 (2026-07-31)

- Cloudflare Workers(정적 assets) `tft-hideout` 생성, GitHub 연동 자동배포 구성
- 최초 `wrangler.toml`을 `pages_build_output_dir`로 설정했으나, 프로젝트가 신형 "Workers Builds"로 생성되어 해당 설정이 무시됨을 확인 → `[assets] directory = "./frontend"` 방식(Workers 정적 assets)으로 전환해 해결
- `develop`→`main` PR #2·#3 머지 시 자동 재배포(새 버전) 확인
- `workers.dev` 라우트는 기본 비활성(Disabled) 상태 — Domains 탭에서 수동으로 켜야 외부 접근 가능
- 배포 URL `https://tft-hideout.suraholic.workers.dev/` → 200, 더미 페이지 정상 표시

## SET-08 (2026-07-31)

- `.github/workflows/manual-smoke.yml` 추가(`workflow_dispatch` + `concurrency` 그룹 패턴)
- `main` 브랜치에서 수동 트리거(Run workflow) 실행 → Success, 10초
- 경고("Node.js 20 is deprecated", `actions/checkout@v4` 관련)는 GitHub 측 런타임 지원종료 사전 공지로 실행 결과와 무관 — 추후 `actions/checkout@v5`로 교체 고려
- 참고: `schedule`(cron) 트리거는 `workflow_dispatch`와 함께 등록해 개발 중에는 수동 실행으로 로직 검증 가능. cron은 UTC 기준, 최소 주기 5분, 실제 실행 시각은 GitHub 부하에 따라 지연 가능, 기본 브랜치(`main`)의 워크플로우 파일만 인식, 저장소 60일 미활동 시 스케줄 자동 비활성화(DATA-12·KPI-02에서 실제 적용 예정)

## SET-09 (2026-07-31)

- backend에 `/env-check` 엔드포인트 추가(`DATABASE_URL` 존재 여부만 bool로 반환, 값은 노출 안 함) + pytest(`test_env_check.py`)
- GitHub Actions: 저장소 시크릿 `DATABASE_URL` 등록. `manual-smoke.yml`에 값 미노출 확인 스텝 추가 → 수동 실행 로그에 `DATABASE_URL secret set: true` 확인, 값 자체는 로그에 없음
- Render: `tft-hideout-backend` 서비스에 `DATABASE_URL` 환경변수 등록 → 자동 재배포 후 `/env-check` → `{"database_url_set": true}` 확인
- Cloudflare: 현재 `tft-hideout` Worker가 정적 assets 전용이라 "Variables cannot be added to a Worker that only has static assets" 제약으로 환경변수 등록 불가 확인. FE-01(Next.js 앱으로 전환 시 서버 진입점 생김)에서 함께 처리하기로 결정 — 그 전까지 프론트엔드용 시크릿/환경변수는 보류

## SET-11 (2026-08-03, 시도 실패 — 보류)

- `tft-hideout-backend`가 속한 Render 프로젝트는 Blueprint 동기화가 아니라 서비스 개별 수동 생성 방식으로 운영 중임을 확인(`render.yaml`에 서비스를 추가해도 자동 반영 안 됨). Metabase 서비스도 대시보드에서 "New service → Web Service → Deploy an existing image" 방식(`docker.io/metabase/metabase:latest`)으로 수동 생성해야 함
- 무료 플랜(Free, 512MB RAM)으로 배포 시도 → **OOM으로 배포 실패**("Ran out of memory (used over 512MB) while running your code")
- `JAVA_OPTS=-Xmx400m`로 JVM 힙을 제한해도 실패함 — 힙 한도는 컨테이너 전체 메모리 상한과 별개이며, 메타스페이스·스레드 스택·JIT 코드캐시 등 부가 오버헤드만으로도 512MB를 초과하는 것으로 보임. Metabase 공식 권장 사양(최소 1GB)과 Render 무료 플랜(512MB 고정)이 애초에 안 맞는 조합
- PM 결정 대기 상태로 보류. 재개 시 고려할 옵션: ① 더 공격적인 JVM 튜닝(`-Xmx256m` + `-XX:MaxMetaspaceSize`, `-XX:+UseSerialGC` 등) 후 재시도(무료 유지되나 배포 성공/안정성 불확실) ② Render 유료 플랜(Starter, 월 $7)으로 Metabase 서비스만 전환(CLAUDE.md "무료 인프라" 원칙에서 벗어나는 지출이라 별도 PM 승인 필요) ③ Metabase 대체 도구 검토(기술스택 변경이라 PM 결정 필요)
- `render.yaml`에 Metabase 서비스 정의(`env: image`, `docker.io/metabase/metabase:latest`, `JAVA_OPTS=-Xmx400m`)를 추가했으나 위 사유로 아직 커밋/push 안 함(`task/SET-11` 브랜치 로컬에만 존재)

## SET-14 (2026-08-03)

- `.github/workflows/ci.yml` 신설: `backend-tests`(ruff check/format + pytest), `frontend-tests`(frontend/package.json 존재 여부로 조건부 실행, 아직 FE-01 전이라 스킵)
- 더미 실패 테스트(`assert False`)를 임시로 추가해 PR #8(`task/SET-14` → `main`)에서 CI 실행 → `backend-tests` 실패(빨간 X, 18초) 정상 확인
- GitHub Settings → Branches에서 `main`/`develop` 브랜치 보호 규칙(Require status checks: `backend-tests`, `frontend-tests`) 생성 시도 → **"Your protected branch rules for your branch won't be enforced on this private repository until you move to a GitHub Team or Enterprise organization account"** 경고, 규칙 목록에 "Not enforced"로 표시됨. 실제로 실패한 PR의 Merge 버튼(Confirm merge)이 비활성화되지 않고 그대로 활성 상태인 것도 확인 — **GitHub 무료 플랜(Private 저장소)은 브랜치 보호 규칙을 설정할 수는 있으나 실제 강제(enforce)하지 않는 제약**
- PM 결정: 유료 전환(GitHub Pro, 월 $4) 없이 **소프트 게이트로 운영** — CI 실패 표시(빨간 X)는 PM이 머지 전 참고하는 신호로만 쓰고, 실제 머지 차단은 기존 워크플로우 규칙("PM 승인 후에만 커밋/머지")으로 대신함. 저장소가 향후 Public 전환(REL-05)되거나 GitHub Pro로 업그레이드되면 동일 규칙이 자동으로 강제되기 시작하니 별도 재작업 불필요
- 더미 테스트 제거 커밋 push 후 동일 PR에서 `backend-tests`/`frontend-tests` 모두 통과(초록 체크)로 전환되는지 PM 확인 예정

## 운영 인시던트 — Render 환경변수 누락 + CHAT-08 캐시 오염 (2026-08-06)

CHAT-11(후속질문 동적 생성) 배포 후 스모크 체크 중 발견. 상세 진단 과정·근본 원인·수정 내역은 `docs/verification/CHAT-11-작업결과.md`의 "배포 후 스모크 체크 결과" 절 참고. 여기서는 인프라 사실만 요약:

- `tft-hideout-backend`(Render) 환경변수에서 `HUGGINGFACE_API_KEY`·`GROQ_API_KEY`가 어느 시점엔가 빠져 있었다(원인 불명 — 수동 설정값이라 SET-09 등록 이후 재설정된 적 없이 계속 있어야 정상). PM이 두 값을 다시 등록·재배포해 해결.
- 위 장애로 실패한 첫 응답(폴백 메시지)이 CHAT-08 캐시에 그대로 저장되는 별도 코드 버그가 있었음을 발견 → `fix/chat08-cache-poisoning`(PR #15)로 수정, 운영 DB에 이미 저장된 오염 캐시 1행은 1회성 스크립트(레포 미커밋, `chat_answer_cache.id=4`)로 내용 확인 후 삭제.
- **후속 조치 필요**: `HUGGINGFACE_API_KEY`/`GROQ_API_KEY`가 왜 빠졌는지는 결국 확인 못 함. Render 대시보드에서 팀원 접근 권한/최근 변경 이력을 확인하거나, 향후 유사 증상(챗봇이 계속 폴백만 응답) 재발 시 이 문서를 참고해 (1) Render 환경변수 존재 여부 (2) `chat_answer_cache` 오염 여부 순으로 확인할 것.
