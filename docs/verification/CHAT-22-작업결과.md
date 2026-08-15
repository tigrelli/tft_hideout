# CHAT-22 : 작업결과

- **TASK**: 일반 게임 정보 웹검색 출처 신뢰도 라벨링
- **상태**: PM 확인 요청 중(구현·자체검증·도커 재검증 완료)
- **선행 TASK**: CHAT-17, CHAT-20 (TEST-11 카테고리 B QA 실행 중 발견해 신설)
- **근거 문서**: TEST-11 카테고리 B QA 채점 중 발견(2026-08-15), `docs/reference/policies.md` 14번(웹 검색 근거 원칙)
- **변경 파일**: `backend/services/web_search.py`, `backend/services/prompt_assembly.py`, `backend/tests/test_chat17_web_search.py`, `TFT_Hideout_WBS.xlsx`(CHAT-22 신규 행), `진행현황.md`

## 문제 재확인

TEST-11 카테고리 B(챔피언·시너지, 25문항) 20번 "특정 챔피언을 상점에 안 뜨게 잠그는 기능이 있나요?"에 챗봇이 다음과 같이 답했다:

> "네, 특정 챔피언을 상점에 안 뜨게 잠그는 기능이 있습니다. 상점 잠금/잠금 해제 기능을 사용하면, 특정 챔피언이 상점에 나타나지 않도록 할 수 있습니다... [출처](https://goo-gle.tistory.com/44)"

정답지 기준 실제로는 **슬롯(칸) 단위 잠금**(리롤해도 그 칸의 챔피언이 유지)만 존재하고, "특정 챔피언이 아예 안 뜨게" 배제하는 기능은 없다 — 결론이 반대인 사실관계 오답. 근거로 쓰인 출처는 라이엇 공식도, TFT 전문 데이터 사이트도 아닌 개인 티스토리 블로그 1건뿐이었다.

## 원인

`web_search.py`의 `search_web()`은 Tavily가 반환한 검색 결과를 제목·URL·본문만 그대로 담아 넘기고, `prompt_assembly.py`의 `_format_web_search_results()`도 이를 가공 없이 `- 제목: 내용 (출처: URL)` 형태로 나열한다. 즉 **출처가 라이엇 공식 자료인지 개인 블로그인지 전혀 구분되지 않은 채** LLM에 전달되고, `WEB_SEARCH_SYSTEM_PROMPT`도 "라이엇 공식 자료가 아닐 수 있으니 완곡하게" 정도의 일반적 지시만 있어 저신뢰 출처 하나만으로도 단정적인 답변이 나올 여지가 있었다.

## 수정

1. `web_search.py`에 `is_authoritative_source(url)` 신설 — 라이엇 공식 사이트·TFT 전문 데이터 사이트(op.gg, lolchess.gg, mobalytics.gg, tactics.tools, metatft.com 등) allowlist 기반 판별 함수(서브도메인 포함).
2. `prompt_assembly.py`의 `_format_web_search_results()`가 각 검색 결과 앞에 `[공식/전문]` 또는 `[커뮤니티/미검증]` 라벨을 붙이도록 수정.
3. `WEB_SEARCH_SYSTEM_PROMPT` 3번 규칙을 재작성 — `[커뮤니티/미검증]` 라벨뿐인 출처로 게임 시스템·규칙을 단정하지 말고 완곡하게 표현하도록 지시, `[공식/전문]`과 내용이 다르면 `[공식/전문]`을 우선하도록 명시. `WEB_SEARCH_FEW_SHOT_EXAMPLE`에도 라벨 형식을 반영해 모델이 실제 입력 형식과 일치하는 예시를 보도록 함.

## 자체 검증

- pytest 신규 5건(`test_chat17_web_search.py`):
  - `is_authoritative_source()` 3건 — 공식 도메인(서브도메인 포함)/개인 블로그·나무위키 구분
  - `_format_web_search_results()` 1건 — `[공식/전문]`/`[커뮤니티/미검증]` 라벨이 실제로 프롬프트에 포함되는지(`assemble_web_search_user_turn` 경유)
  - `WEB_SEARCH_SYSTEM_PROMPT` 1건 — 두 라벨 문구가 모두 포함되는지
- ruff check/format: 변경 파일 클린
- `backend/tests/test_chat17_web_search.py` DB 미의존 테스트 **18/18 통과**(기존 13 + 신규 5), Groq/Tavily 실호출 없이 fake 주입
- 회귀 확인: `WEB_SEARCH_SYSTEM_PROMPT`/`_format_web_search_results`를 참조하는 다른 테스트 파일이 있는지 grep으로 확인 — 없음(`test_chat17_web_search.py` 단독 참조)
- 도커(`docker-compose.test.yml` test-db 5433, PM이 세션 중 기동)로 `backend` 전체 pytest **352/352 통과**(347+신규 5), `batch` 전체 pytest **130/130 통과**(회귀 없음)

## 한계

- **도커 재검증 미실행**: 이번 세션 실행 환경에 Docker(WSL 통합)가 없어 `docker-compose.test.yml` test-db(5433)를 띄우지 못했다. 따라서 DB 연동이 필요한 `test_chat17_web_search.py`의 나머지 6개 테스트(`generate_answer_stream` 배선 확인)와 `backend`/`batch` 전체 스위트는 이번 세션에서 실행하지 못했다. 변경 범위가 DB 스키마·세션 로직과 무관한 순수 함수(도메인 판별·문자열 포맷)라 회귀 위험은 낮다고 판단하지만, **PM 확인 전 도커 환경에서 전체 스위트 재검증을 권장**한다.
- 도메인 allowlist는 초기 후보 7개(teamfighttactics.leagueoflegends.com, leagueoflegends.com, lolchess.gg, op.gg, mobalytics.gg, tactics.tools, metatft.com)로 시작한 것이라 누락된 신뢰 가능 사이트가 있을 수 있음 — 실사용 중 발견되면 allowlist에 추가.
- 라벨링은 "완곡하게 표현하라"는 프롬프트 지시일 뿐 결정론적 차단이 아니라, LLM이 여전히 `[커뮤니티/미검증]` 출처만으로 단정할 가능성은 완전히 배제되지 않는다(A13/CHAT-21과 같은 계열의 확률적 한계). TEST-11 나머지 카테고리 진행 중 유사 사례가 재발하는지 관찰 필요.
