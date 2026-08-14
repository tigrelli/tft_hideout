# CHAT-20 : 작업결과

- **TASK**: 일반 게임 정보 웹검색 쿼리 스코핑·출처 라벨 개선
- **상태**: PM 확인 요청 중(구현·자체검증·도커 재검증 완료)
- **선행 TASK**: CHAT-17 (CHAT-19 대응 중 PM이 이어서 제보)
- **근거 문서**: PM 제보(2026-08-14, 스크린샷 2장), `docs/reference/policies.md` 14번(웹 검색 근거 원칙)
- **변경 파일**: `backend/services/chat_stream.py`, `backend/services/prompt_assembly.py`, `backend/tests/test_chat17_web_search.py`

## 문제 재확인

PM이 챗봇에 "언제 서비스가 종료되나요?"(TFT 시즌 종료를 의도)라고 물었더니, 챗봇이 DHS(미국 국토안보부) 셧다운·미국 세금 거주권·게임 배너 관련 등 전혀 무관한 웹검색 결과를 근거로 "서비스 종료 정보는 확인되지 않았다"고 답하면서도, 그 무관한 출처 3개를 전부 `[출처](URL)`로 구분 없이 나열해 화면에 "출처" 링크가 3줄 반복됨. PM이 실제 TFT 시즌/패치 일정 표(PBE 2026-07-28, 라이브 2026-08-26/18.1 패치)를 캡처로 함께 제시하며 "웹검색으로 이미 확인 가능한데 검색 자체가 잘못된 것 아니냐"고 제보.

## 원인

1. **검색 쿼리에 TFT 스코핑이 없음**: `chat_stream.py`의 `general_game_info` 분기가 Tavily에 `search_query_text`(첫 턴이면 사용자 메시지 원문 그대로)를 그대로 넘긴다. "언제 서비스가 종료되나요?"에는 "TFT" 같은 스코핑 키워드가 전혀 없어, Tavily가 전 세계 아무 "서비스 종료"나 "종료" 관련 결과를 반환함 — 내부 RAG(CHAT-02)는 `doc_type` SQL 필터로 항상 TFT 데이터 안에서만 검색되는 것과 달리, 웹검색은 쿼리 문자열 자체가 유일한 스코핑 수단인데 이게 비어 있었음.
2. **무관한 결과도 무조건 출처로 나열**: `WEB_SEARCH_SYSTEM_PROMPT` 2번 규칙이 "참고한 출처 URL을 반드시 포함하라"고만 지시해, 실제로 답변에 쓴 정보인지와 무관하게 검색 결과 URL을 전부 `[출처](URL)`로 나열하게 유도. 여러 개를 인용해도 라벨이 항상 동일하게 "출처"라 화면에서 구분이 안 됨(프론트는 마크다운 링크를 그대로 렌더링할 뿐이라 프론트 버그 아님, 프롬프트 지시 문제).

## 수정

- `chat_stream.py`: `_build_web_search_query_text()` 신규 — Tavily에 보내는 쿼리에만 `"TFT(전략적 팀 전투) "` 접두어를 붙여 검색을 스코핑(프롬프트에 표시되는 사용자 질문 원문·대화 이력은 변경 없음, 검색 문자열만 보강).
- `prompt_assembly.py`: `WEB_SEARCH_SYSTEM_PROMPT` 1번 규칙에 "무관한 항목이 섞여 있어도 근거로 삼지 말라"는 문구 추가, 2번 규칙을 "실제로 답변에 근거로 사용한 출처만" 포함하고 "확인되지 않았습니다"로 답할 때는 출처를 붙이지 않으며, 2개 이상 인용 시 `[출처 1]`/`[출처 2]`처럼 번호로 구분하도록 재작성.

## 자체 검증

- pytest 신규 2건:
  - `test_general_game_info_web_search_query_is_scoped_with_tft_context`: `web_search_fn`에 전달되는 쿼리에 "TFT"가 포함되고 원래 질문 텍스트("언제 서비스가 종료되나요?")도 함께 유지되는지 확인
  - `test_web_search_system_prompt_requires_citing_only_used_sources_with_numbering`: 프롬프트에 "실제로 답변에 근거로 사용한 출처만"·"출처 1"·"출처 2" 문구가 포함되는지 확인
  - 기존 `test_web_search_system_prompt_requires_citation_and_polite_tone`의 `"출처 URL" in ...` 단언을 재작성된 문구에 맞춰 `"출처" in ...`로 조정(문구가 정당하게 바뀐 것이라 완화, 나머지 두 단언은 그대로)
- ruff check/format: 변경 파일 전체 클린
- 도커(`docker-compose.test.yml` test-db 5433)로 `backend` 전체 pytest **345/345 통과**(343+신규 2), `batch` 전체 pytest **130/130 통과**(회귀 없음)

## 한계

- 쿼리 스코핑은 접두어 추가 방식이라, Tavily가 그래도 무관한 결과를 반환하면(스코핑을 걸어도 검색엔진 자체의 관련도 판단에 달림) 1번 규칙("확인되지 않았습니다")과 2번 규칙(무관 출처 미인용)이 최종 방어선이다 — 완전히 무관한 결과가 0%가 되는 것을 보장하지는 않는다.
- 출처 번호("출처 1"/"출처 2")는 모델이 프롬프트 지시를 따르는 데 의존하는 결정론적이지 않은 방어라, CHAT-06/CHAT-18의 `verify_grounding`류 사후 정규식 검증까지는 아니다(URL 근거검증(`verify_web_citation`)은 기존대로 유지되어 할루시네이션 URL은 계속 걸러짐).
