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
