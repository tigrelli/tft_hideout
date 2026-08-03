## WBS 코드

<!-- 예: SET-13, FE-03 등. 여러 TASK를 한 PR에 묶지 않는다(CLAUDE.md 4장) -->

## 변경 내용

<!-- 무엇을 왜 바꿨는지 1~3줄 요약 -->

## 테스트

<!-- WBS `테스트 요구사항` 컬럼 기준 테스트 실행 결과(로그/스크린샷) -->

- [ ] 관련 테스트 작성·통과 확인 (pytest/Vitest/Playwright 등)
- [ ] `ruff check .` / `ruff format --check .` 통과 (백엔드·배치 변경 시)
- [ ] ESLint/TypeScript strict 통과 (프론트엔드 변경 시)

## PM 확인

- [ ] PM이 결과(변경 파일·테스트 로그·스크린샷)를 확인하고 완료를 승인함 (CLAUDE.md 4장 5~6단계)
- [ ] `진행현황.md`의 해당 WBS 코드 행 상태를 갱신함

<!-- PM 승인 전 커밋은 가능하나, main/develop 머지는 PM 승인 이후에만 진행한다 -->
