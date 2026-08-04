# SET-06 : 작업결과

- **TASK**: Render 백엔드 배포 파이프라인 구성
- **상태**: 완료(PM 승인 2026-07-31)
- **선행 TASK**: SET-01,SET-03
- **커밋**: a58ff61(PR #1)

## 결과 요약

Render 웹서비스(tft-hideout-backend, Singapore) 생성, render.yaml Blueprint로 배포 설정. /health 엔드포인트만 있는 더미 FastAPI 앱으로 배포 검증(pytest·ruff 통과), develop→main PR #1 머지 시 자동 재배포 확인, 배포된 Render URL /health 200 확인

---
*이 파일은 CLAUDE.md v1.8(2026-08-03) 컨벤션 도입 시점에 진행현황.md 변경 이력을 근거로 소급 작성됨.*

## 추가 기록 (2026-08-04, DATA-14 검증 중 발견) — Render Blueprint 운영 시 주의사항

`render.yaml`의 `buildCommand`에 `alembic upgrade head`를 추가하는 커밋(`ed3f1e3`)을 push했는데도 실제 배포에 반영되지 않아 운영 DB에 스키마가 계속 없던 문제가 있었다. 원인 2가지(상세: `docs/verification/DATA-14-작업결과.md`):

1. 이 서비스의 **Root Directory가 `backend`**로 설정돼 있어(SET-06 결정), 저장소 **루트**에 있는 `render.yaml` 변경은 Render의 auto-deploy 트리거 대상이 아니다(Root Directory 밖의 파일 변경은 무시됨).
2. `render.yaml`(Blueprint)로 생성한 서비스는 이후 파일이 바뀌어도 **서비스에 실제 적용된 Build Command 등 설정이 자동 동기화되지 않는다** — Render 대시보드에서 수동으로 Sync하거나 Settings에서 직접 값을 고쳐야 반영된다.

**향후 `render.yaml`을 수정할 때는 push 후 Render 대시보드 Settings에서 실제 설정값이 바뀌었는지 반드시 확인할 것.** 필요하면 Settings에서 직접 고치는 게 더 확실하다.
