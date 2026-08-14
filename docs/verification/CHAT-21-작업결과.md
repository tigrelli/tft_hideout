# CHAT-21 : 작업결과

- **TASK**: 게임 공식 명칭 포함 질문의 의도분류 오탐 수정
- **상태**: PM 확인 요청 중(구현·자체검증·도커 재검증 완료)
- **선행 TASK**: CHAT-01 (TEST-11 카테고리 A QA 실행 중 PM 제보로 신설)
- **근거 문서**: PM 제보(2026-08-14, TEST-11 QA 중 발견)
- **변경 파일**: `backend/services/intent_classification.py`, `backend/tests/test_chat01_intent_classification.py`

## 문제 재확인

TEST-11(예상질문지 기반 종합 QA) 카테고리 A 25문항을 프로덕션 챗봇에 실제로 질의하던 중, "TFT(전략적 팀 전투)는 어떤 게임인가요?"(카테고리 A 1번, 정답지는 "최대 8명이 챔피언·아이템을 배치해 자동 전투하는 오토배틀러 게임" 수준의 답을 기대) 질문에 챗봇이 게임 설명 뒤에 완전히 무관한 조합 통계를 덧붙였다:

> "...게임의 결과는 플레이어의 전략과 조합, 아이템 및 증강체의 사용에 따라 결정됩니다. **17.9 패치 기준으로는 [운명술사 트위스티드 페이트] 조합이 평균 등수 2.99, 승률 정보 비공개로 강세입니다.** (참고: 게임 정보)"

## 원인

`intent_classification.py`의 1차 키워드 패턴 `INTENT_GENERAL_STRATEGY: re.compile(r"메타|전략")`이 질문 문자열 어디든 "전략"이 있으면 매칭된다. 그런데 TFT의 한글 공식 명칭 자체가 "전략적 팀 전투"라서, 사용자가 게임 이름을 그대로 언급하기만 해도(질문 내용과 무관하게) 이 키워드에 걸려 `general_strategy`로 분류되고, 하이브리드 검색(CHAT-02)이 조합 문서를 끌어와 답변에 섞는다. `INTENT_ADDITIONAL_INSTRUCTION[general_strategy]`가 "'메타'를 묻는 질문이면 티어가 가장 높은 조합부터 우선 언급하라"고 지시해, 관련 없는 질문에도 최상위 티어 조합이 끼어들 여지를 만든다.

## 수정

1차 키워드 매칭 직전에 `_GAME_NAME_PATTERN`(`전략적\s*팀\s*전투`)으로 그 고정 구문만 제거한 사본을 매칭에 사용한다(`classify_by_keyword()`). 실제 LLM에 전달되는 질문 원문·검색 쿼리는 전혀 변경하지 않고, 1차 키워드 매칭 판단에만 영향을 준다. 게임 명칭 밖에서 실제로 "전략"을 언급하는 질문(예: "전략적 팀 전투에서 초반 전략 어떻게 짜?")은 구문 제거 후에도 "전략"이 남아 기존대로 `general_strategy`로 정상 분류된다.

## 자체 검증

- pytest 신규 2건(`test_chat01_intent_classification.py`):
  - `test_classify_by_keyword_ignores_official_game_name_phrase`: "TFT(전략적 팀 전투)는 어떤 게임인가요?", "전략적 팀 전투 처음 시작하는데 뭐부터 해야해?" 모두 `None`(키워드 오분류 없음, 2차 LLM 위임) 반환 확인
  - `test_classify_by_keyword_still_matches_strategy_keyword_outside_game_name`: "전략적 팀 전투에서 초반 전략 어떻게 짜야해?"는 여전히 `general_strategy`로 정상 분류(회귀 방지)
- ruff check/format: 변경 파일 클린
- 도커(`docker-compose.test.yml` test-db 5433)로 `backend` 전체 pytest **347/347 통과**(345+신규 2), `batch` 전체 pytest **130/130 통과**(회귀 없음)

## 한계

- "전략적 팀 전투"라는 고정 구문만 예외 처리한 것이라, 게임 명칭을 다르게 줄여 쓰는 표현(예: "롤토체스", "TFT"만 단독 사용 등)은 애초에 "전략"이라는 글자를 포함하지 않아 이번 버그 대상이 아니었다(원래도 문제 없었음). 향후 유사한 고정 구문 충돌이 다른 키워드(조합/아이템/증강체/메타)에서도 발견되면 같은 패턴(매칭용 사본에서 구문 제거)으로 대응.
