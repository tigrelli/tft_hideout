# DATA-16 : 작업결과

- **TASK**: 증강체 설명 템플릿 플레이스홀더 정리
- **상태**: 완료(PM 승인 2026-08-05)
- **선행 TASK**: DATA-08
- **근거 문서**: `docs/verification/FE-06-작업결과.md`(2026-08-05 발견)
- **변경 파일**: `batch/normalize.py`(`clean_augment_description()` 신규 + `augment_rows()`에 적용), `batch/tests/test_data10_normalize.py`(pytest 6건 신규), `frontend/src/components/augments/augment-card.tsx`(`whitespace-pre-line` 추가), `frontend/src/components/__tests__/augment-card.test.tsx`(테스트 1건 신규)

## 문제 재확인

FE-06 실데이터 검증 중 발견한 대로, op.gg 증강체 설명 원문(357개 중 99개, 약 28%)에 아래 두 패턴이 섞여 있었다(2026-08-05 실호출로 재확인):
1. `<br>` 리터럴 태그(줄바꿈 의도) — React가 텍스트로 그대로 이스케이프해 화면에 `<br>` 문자 자체가 노출됨.
2. `@TFTUnitProperty.item:...@` / `@TFTUnitProperty.:...@` 형태의 미해석 수치 템플릿 — op.gg 클라이언트 자체 UI에서만 별도 수치 데이터로 치환되는 것으로 보이며, op.gg MCP 5개 도구 중 어디에도 이 수치를 채워줄 소스가 없다(DATA-05 스파이크 범위 확인). 일부는 `<rules>...</rules>` 같은 추가 HTML 유사 태그로 감싸여 있음.

## 구현

`batch/normalize.py`에 `clean_augment_description()` 추가, `augment_rows()`가 `description`을 DB에 넣기 전에 항상 이 함수를 거치도록 배선:
1. `<br\s*/?>` → 실제 개행(`\n`)으로 변환(정규식, 대소문자 무관).
2. `@[^@]*@` 패턴(미해석 수치 템플릿) → `(수치 정보 없음)`으로 치환 — **실제 수치로는 치환 불가**(위 사유), 대신 깨진 템플릿 문법 자체가 노출되지 않도록 함.
3. `<rules>`/`</rules>` 등 나머지 HTML 유사 태그(`</?[a-zA-Z][^<>]*>`) 제거.
4. 3줄 이상 연속 개행은 2줄로 축소, 앞뒤 공백 정리.

프론트(`AugmentCard`)는 정리된 `\n`을 실제로 줄바꿈해 보여주도록 `whitespace-pre-line` 클래스 추가(기존 FE-06의 `wrap-break-word`와 함께 사용).

## 자체 검증

- **batch**: pytest 6건 신규(순수 함수 단위 테스트 5건 + `augment_rows()` 통합 테스트 1건, 실제 op.gg 응답에서 발견된 패턴 그대로 재현한 합성 fixture 사용 — 정책상 pytest는 실 API 미호출). 전체 **80/80 통과**, ruff check/format 통과.
- **frontend**: Vitest 1건 신규(전체 **59/59 통과**), `tsc --noEmit`/eslint/prettier/`next build` 전부 통과.
- **실제 op.gg 데이터로 검증**(2026-08-05, 로컬에서 `augment_rows()`를 실제 op.gg 응답 357개 전체에 실행): 정리 후 `description`에 `<`·`@` 문자가 남은 행 **0건**(정리 전 99건). 예시 3개 직접 확인:
  - `TFT17_Augment_AurelionSolGodAugment`: `"...증명하세요.\n\n선택한 퀘스트: (수치 정보 없음)"`
  - `TFT17_Augment_Timebreaker_Timestream`: `"...획득합니다.\n\n(체력: (수치 정보 없음), 공격 속도: (수치 정보 없음)%)"`
  - `TFT17_Augment_ThreshGodAugment`(`<rules>` 태그 포함 케이스): `"...얻습니다.\n\n체력: (수치 정보 없음)\n공격 속도: (수치 정보 없음)%"`

## 운영 데이터 백필 완료 (2026-08-05, PM 승인 후 실행)

이 수정은 다음 배치 실행부터 새로 수집되는 증강체에는 자동 적용되지만, 이미 운영 DB(`augments` 테이블, 357행)에 저장된 기존 `description`은 그대로라 별도 반영이 필요했다. FE-05와 달리 op.gg 재호출이 필요 없는 순수 텍스트 정리라, `augments` 테이블만 읽고 쓰는 1회성 백필 스크립트(레포 미커밋, 실행 후 삭제)를 운영 DB에 직접 실행 — **357행 중 105행 변경, 252행은 원래도 정리 대상 패턴이 없어 변경 없음**. 운영 API(`GET /catalog/augments`)로 재확인한 결과 357개 전체에서 `<`·`@` 잔여 패턴 **0건** 확인. DATA-16 전체 종료.
