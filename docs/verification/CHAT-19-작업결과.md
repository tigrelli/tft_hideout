# CHAT-19 : 작업결과

- **TASK**: 패치 버전 질문 직접 답변 경로 신설
- **상태**: PM 확인 요청 중(구현·자체검증 완료, 도커 재검증까지 완료)
- **선행 TASK**: CHAT-01, CHAT-04, CHAT-05 (CHAT-17 실사용 검증 중 PM 제보로 신설)
- **근거 문서**: PM 제보(2026-08-14, 스크린샷), `docs/reference/glossary.md` 챗봇 의도 분류(5종)
- **변경 파일**: `backend/services/chat_preprocessing.py`, `backend/services/chat_stream.py`, `backend/tests/test_chat04_input_preprocessing.py`, `backend/tests/test_chat05_streaming.py`

## 문제 재확인

PM이 배포된 사이트에서 챗봇에 "현재 패치버전은?"이라고 물었더니, 화면 상단엔 "패치 17.9"가 정상 표시되는데도 챗봇은 "현재 패치 버전은 확인되지 않았습니다"라며 리그 오브 레전드 패치 일정·Windows 11 핫패치 일정 등 전혀 무관한 내용을 근거로 답변(스크린샷 제보). 자동 패치 업데이트 파이프라인도 함께 재확인 요청받음.

## 조사 결과

### 1. 자동 패치 업데이트 파이프라인 — 이상 없음
`batch/patch_detection.py`(op.gg 버전 감지) → `batch/patch_transition.py`(정규화/임베딩 성공 시에만 `patches.is_current` 원자적 전환) → `.github/workflows/patch-detection.yml`(매일 03:00 KST 스케줄 + `workflow_dispatch`, `concurrency` 대기열 설정)까지 재확인. 코드·배포 설정 모두 정상이며 화면의 "패치 17.9" 표시와 일치. 사소한 문서 드리프트 1건 발견(수정 안 함, 다음 관련 TASK 때 함께 정리 권장): `batch/run_patch_batch.py:8-10` 상단 주석이 "schedule 트리거는 아직 안 켰다"고 돼 있는데 실제 워크플로우는 이미 스케줄이 켜져 있음.

### 2. 챗봇 패치 버전 오답 — 실제 버그(본 TASK 핵심)
- `intent_classification.py`의 1차 키워드 패턴(조합/아이템/증강체/메타)에 "패치"가 없어, "현재 패치버전은?"은 2차 Groq LLM 분류로 넘어감.
- 2차 분류 프롬프트가 `general_game_info`를 "게임 운영 정보 질문"으로 설명해 LLM이 패치 버전 질문을 이 범주로 오분류.
- `general_game_info`는 내부 DB를 전혀 안 쓰고 Tavily 웹검색만 근거로 쓰는 경로(CHAT-17)라, "패치버전" 웹검색 결과로 무관한 문서가 잡혀 그대로 답변에 반영됨.
- 정작 `patch_version`(`patches.is_current`)은 `chat_stream.py`의 `generate_answer_stream()`이 의도분류 이전에 이미 조회해두는데(`get_current_patch_version(db)`), 이 값이 `general_game_info` 경로(`_generate_web_search_answer`)에는 로깅용으로만 전달되고 프롬프트/답변 생성에는 전혀 쓰이지 않았음.

## 수정

패치 버전 질문은 의도분류·검색·LLM 호출 없이 이미 조회해둔 `patch_version`으로 결정론적으로 즉답하는 조기 반환 경로를 신설(기존 `CLARIFICATION_MESSAGE`/`OFF_TOPIC_MESSAGE`/`NO_CURRENT_PATCH_MESSAGE`와 동일한 패턴).

- `chat_preprocessing.py`: `_PATCH_VERSION_QUERY_PATTERN`(`패치\s*버전|버전.*패치|몇\s*패치`) + `is_patch_version_query()` 신규. "이번 패치에 뭐가 바뀌었어?" 같은 패치노트류 질문은 내부에 답할 데이터 자체가 없어 이 패턴에 포함하지 않고 기존 `general_game_info`(웹검색) 경로로 그대로 보냄 — "몇 패치인지"를 묻는 질문만 좁게 감지.
- `chat_stream.py`: `_patch_version_answer()` 신규(`"현재 서비스에 반영된 기준 패치는 '{patch_version}' 패치입니다."`). `generate_answer_stream()`에서 `NO_CURRENT_PATCH_MESSAGE` 조기 반환 직후, 캐시 조회·의도분류보다 먼저 `is_patch_version_query()`를 확인해 참이면 즉답 후 반환(다른 조기 반환과 동일하게 `chat_logs` 적재·캐시 대상 아님).

## 자체 검증

- pytest 신규 10건:
  - `test_chat04_input_preprocessing.py`: `is_patch_version_query()`가 "현재 패치버전은?"/"지금 패치 버전이 뭐야?"/"몇 패치야?"/"지금 몇패치야?"/"패치버전 알려줘" 5건은 True, "이번 패치에 뭐가 바뀌었어?"/"다음 패치는 언제야?"/"지금 메타에서 강한 조합 추천해줘" 3건은 False를 반환하는지 확인 — **DB 미의존, 로컬 실행 통과**
  - `test_chat05_streaming.py`: 패치 버전 질문이 `classify_fn`/`search_fn`/`web_search_fn`/`stream_fn`을 전혀 호출하지 않고 `patch_version` 값을 포함한 고정 문구로 즉답하는지(1건), `patch_version`이 없을 때는 이 분기보다 `NO_CURRENT_PATCH_MESSAGE`가 먼저 반환되는지(1건) — **DB(`migrated_engine`) 의존, 아래 한계 참고**
- ruff check/format: 변경 파일 전체 클린
- 회귀 확인용으로 DB 미의존 테스트 전체(`--ignore`로 DB 의존 파일 제외) 150건 실행 — 전부 통과, 기존 동작 회귀 없음

## 도커 재검증 완료

PM이 로컬 도커를 기동해줘서 `docker-compose.test.yml` test-db(5433)로 위 "한계"였던 DB 의존 테스트 미실행을 해소.

- `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/tft_hideout_test` 설정 후 `backend` 전체 pytest **335/335 통과**(기존 325 + 이번 TASK 신규 10건, `test_chat05_streaming.py` 신규 2건 포함 전부 통과)
- `batch` 전체 pytest **130/130 통과**(회귀 없음 — 이번 TASK는 batch 코드를 건드리지 않았으나 공유 모듈 영향 확인 차 함께 실행)
- 검증 후 `docker compose -f docker-compose.test.yml down`으로 컨테이너 정리

## 배포 후 프로덕션 스모크 체크

`render.yaml`(`branch: main`, `autoDeploy: true`, `rootDir: backend`)에 따라 push 시 Render가 자동 재배포됨을 확인. 배포 완료 후 프로덕션에 직접 확인:

- `GET /api/v1/catalog/patches/current` → `{"version":"17.9",...}` (사이트 상단 표시와 일치)
- `POST /api/v1/chat/message` `{"message":"현재 패치버전은?"}` → `"현재 서비스에 반영된 기준 패치는 '17.9' 패치입니다."` 즉답(스크린샷 제보의 웹검색 오답 흐름 재현 안 됨, Groq/Tavily 호출 없어 지연도 없음)
- 이 조기 반환 경로는 `chat_logs` 미적재 설계라 프로덕션 DB에 부가 영향 없음

Cloudflare(프론트엔드)는 이번 변경 대상이 아니라 별도 확인 불필요.

## 2026-08-14 회귀 수정 — "현재패치는?"처럼 신호 단어가 없는 최소 표현 미탐지(PM 재제보)

배포 후 PM이 프로덕션에서 "현재패치는?"이라고 물었더니 여전히 예전과 같은(리그 오브 레전드 패치 일정 등 무관한) 웹검색 오답이 나온다고 재제보.

- **원인**: 최초 구현의 `_PATCH_VERSION_QUERY_PATTERN`(`패치\s*버전|버전.*패치|몇\s*패치`)이 "버전"/"몇" 같은 명시적 신호 단어가 있는 문장만 잡도록 너무 좁게 설계됨 — "현재패치는?"은 "패치" 외에 다른 신호 단어가 전혀 없어 그대로 놓치고 기존 `general_game_info`(웹검색) 경로로 빠짐. 배포는 정상 반영돼 있었고(직전 "현재 패치버전은?" 테스트는 정상 즉답), 이건 배포 문제가 아니라 정규식 커버리지 부족이었음.
- **수정**: 판정 로직을 재설계 — (1) 명시적 신호 단어(`버전`/`몇`/`무슨`/`어떤`)가 있으면 즉시 True, (2) 없으면 패치노트류 배제 단어(`바뀌`/`변경`/`달라진`/`패치노트`/`너프`/`버프`/`추가된`)가 있는지 확인해 있으면 False, (3) 그래도 남는 경우 "(현재/지금/이번) 패치 (는/가/…) (뭐야/…)?" 형태의 최소 질문 패턴(`_BARE_PATCH_QUERY_PATTERN`)으로 흡수. "패치" 자체가 없으면 항상 False(기존 다른 의도 오염 없음).
- pytest 신규 8건(총 18건) — "현재패치는?"/"지금 패치는?"/"패치가 뭐야?"/"패치는 뭐예요?"/"패치가 몇이야?"/"무슨 패치야?"/"어떤 패치야?" 등 True 케이스, "패치노트 알려줘" False 케이스 추가. `backend` 전체 343/343 통과(도커 재검증, 335+신규 8), ruff 클린.
- PM 승인 후 커밋(`d7f6edb`)·push, Render 자동 재배포 완료 확인. 재배포 직후(빌드 진행 중) 2회는 이전 버전이 응답해 예전과 동일한 웹검색 오답이 재현됐으나, 재배포 완료 후 프로덕션에서 "현재패치는?" 재확인 → `"현재 서비스에 반영된 기준 패치는 '17.9' 패치입니다."` 정상 즉답 확인.

## 한계

- "패치 버전"과 "패치노트(변경사항)"를 구분하는 규칙 기반 판단이라, "이번 패치 버전에서 바뀐 점은?"처럼 신호 단어(버전)와 배제 단어(바뀐)가 함께 섞인 질문은 신호 단어 우선 원칙에 따라 여전히 즉답(버전만) 대상으로 분류된다 — 실사용 중 이런 질문이 실제로 나오면 후속 TASK로 재조정 필요.
- 규칙 기반이라 위 목록에 없는 완전히 새로운 표현(동의어·오타 등)은 여전히 놓칠 수 있다 — 실사용 중 재발하면 신호/배제 단어 목록에 추가하는 방식으로 확장.
