# CHAT-11 : 작업결과

- **TASK**: 후속질문 동적 생성(LLM 기반) 구현
- **상태**: 완료(PM 승인 2026-08-06)
- **선행 TASK**: CHAT-05, FE-09
- **근거 문서**: PRD 7-4, 화면설계서 2.7(SuggestedFollowupChips), 개발설계서 4.4(프롬프트 조립), `docs/verification/FE-09-작업결과.md`(설계 논의 배경)
- **변경 파일**:
  - `backend/services/chat_followups.py`(신규) — LLM 기반 후속 질문 생성
  - `backend/services/groq_client.py`(수정) — `call_groq_chat`에 `max_tokens` 파라미터 추가(기존 기본값 20 유지, 하위호환)
  - `backend/services/chat_stream.py`(수정) — `generate_answer_stream`에 `result` 사이드채널 파라미터, `build_sse_stream`에 `followups_fn` 파라미터 추가
  - `backend/routers/chat.py`(수정) — `/chat/message` 엔드포인트에 후속질문 생성 배선
  - `backend/tests/test_chat11_followups.py`(신규, 14건)
  - `frontend/src/lib/chat-stream.ts`(수정) — `event: followups` SSE 파싱(`onFollowups` 콜백)
  - `frontend/src/lib/use-chat-conversation.ts`(수정) — `ChatMessage.followups` 필드 추가
  - `frontend/src/components/chat-widget/chat-followup-chips.tsx`(재작성) — 정적 4개 예시 질문 → 동적 `questions` prop
  - `frontend/src/components/chat-widget/chat-widget.tsx`(수정) — 최근 봇 메시지의 `followups`를 칩에 전달
  - `frontend/src/components/__tests__/chat-widget.test.tsx`(수정, 2건 추가)
  - `docs/reference/api-spec.md`(수정) — `event: followups` SSE 이벤트 문서화

## 설계

- **기존 CHAT-05 계약을 바꾸지 않는 사이드채널 방식**: `generate_answer_stream`의 반환 타입(`Generator[str, None, None]`)을 그대로 유지하고, 선택적 `result: dict[str, object] | None` 파라미터를 추가했다. 성공적으로 "새로" 생성된 답변일 때만(`raw_answer != FALLBACK_MESSAGE`) `result["answer_text"]`를 채운다. 이 방식 덕분에 CHAT-05/08/09가 이미 검증해 둔 기존 pytest(약 20여 건)를 한 글자도 안 고치고 그대로 통과시켰다(무회귀 확인, FE-11 결과 문서와 동일한 원칙). 대안이었던 "제너레이터가 `(kind, payload)` 튜플을 yield하도록 전체 재설계"는 기존 테스트를 전부 다시 써야 해 기각.
- **후속질문 생성을 건너뛰는 경우(레이트리밋 절감이 핵심 설계 기준)**:
  1. 명확화/범위밖/패치없음 조기 반환 — 후속으로 이어갈 실질 답변이 없음
  2. **CHAT-08 캐시 히트** — 캐시의 목적 자체가 Groq 호출 절감인데 후속질문 때문에 매번 Groq를 호출하면 캐싱 이점이 반감되므로 의도적으로 제외
  3. Groq가 완전히 실패해 `FALLBACK_MESSAGE`(에러 안내문)로 대체된 턴 — 에러 문구에 대한 후속질문은 무의미하고, 이미 실패한 턴에 호출을 하나 더 얹지 않음
  4. 후속질문 자체의 Groq 호출이 실패해도(타임아웃 등) 재시도 없이 빈 목록으로 폴백(본 답변 스트리밍에는 영향 없음)
- **SSE 이벤트 확장**: `data: <token>` 반복 뒤에 `event: followups\ndata: <JSON string[]>\n\n`을 있을 때만 추가하고 항상 `event: done`으로 마무리. `followups_fn`을 안 넘기면 기존 API-09 동작 그대로라 하위호환.
- **프론트 설계 정정**: FE-09에서는 빈 대화 상태에 고정 4개 예시 질문을 보여줬으나, 화면설계서 2.7 모바일 와이어프레임을 다시 확인한 결과 칩은 **봇 답변 직후**에만 등장하는 구성이었다(빈 상태에는 칩이 없음). CHAT-11에서 이 부분을 스펙에 맞게 바로잡아, `ChatFollowupChips`는 이제 항상 "가장 최근 봇 메시지의 `followups` 배열"만 그대로 렌더링하고, 목록이 비어 있으면(=조기반환/캐시/폴백/생성실패) 아무것도 렌더링하지 않는다.
- **프롬프트**: 별도 시스템 프롬프트로 "최대 3개, 한 줄에 하나, 번호/기호 없이, 답변에 등장한 고유명사 활용"을 지시하고, 응답을 줄 단위로 분리 후 불릿 문자 제거·빈 줄 제거·3개로 절단해 파싱한다.

## 레이트리밋 영향 검토 (DoD 필수 항목)

- **호출 증가**: 캐시 미스이면서 조기반환/폴백이 아닌 "실제로 새로 생성된" 턴에 한해 Groq 호출이 1회(스트리밍 답변) → 최대 2회(스트리밍 답변 + 후속질문 완성)로 늘어난다. CHAT-08 캐시는 첫 턴에만 적용되고 후속 턴은 원래도 매번 Groq를 호출하므로, 대화가 길어질수록(후속 턴이 많을수록) 후속질문 호출의 상대적 비중이 커진다.
- **비용/지연 억제 장치**: (1) 캐시 히트·조기반환·폴백 턴은 아예 호출 안 함(위 설계 참고), (2) 재시도 없음(실패하면 즉시 빈 목록, 본 답변 재시도 로직과 분리), (3) `max_tokens=200`으로 캡(답변 스트리밍은 무제한/스트리밍이라 상대적으로 가벼움), (4) 후속질문 실패가 메인 답변 스트리밍의 지연이나 성공 여부에 전혀 영향을 주지 않음(SSE 토큰 스트림 이후 별도 단계).
- **결론/후속 조치**: 개인+지인 10명 규모(policies.md 10번) 트래픽에서는 Groq 무료 티어 한도에 여유가 있을 것으로 예상되나, 실측치는 없다. **배포 후 KPI-01 응답지연·이용률 지표로 모니터링**하고, 한도 압박이 확인되면 (a) 후속질문을 매 턴이 아닌 확률적/N턴마다로 제한하거나 (b) PM과 처음에 논의했던 규칙 기반(비-LLM) 생성으로 전환하는 두 가지 완화 옵션을 제안한다. 코드 변경 없이 우선 모니터링만 하는 것을 권장.

## 자체 검증

- **backend pytest**: `test_chat11_followups.py` 신규 14건(질문 파싱·불릿 제거·3개 절단·빈 답변/LLM 실패 시 빈 목록, `build_sse_stream` followups 이벤트 유무, `generate_answer_stream` result 사이드채널이 정상 흐름에서만 채워지고 조기반환/캐시히트/Groq완전실패에서는 안 채워짐, `result` 미전달 시 기존 동작 무변화) — **backend 전체 199/199 통과**(기존 CHAT-05/08/09 테스트 무수정 통과로 무회귀 확인), `ruff check`/`ruff format --check` 통과.
- **frontend Vitest+RTL**: `chat-widget.test.tsx`에 CHAT-11 케이스 2건 추가(followups 이벤트 → 동적 칩 렌더링 + 칩 클릭 시 해당 질문 그대로 전송, followups 없으면 칩 미렌더링) — **frontend 전체 79/79 통과**, `eslint`/`prettier --check`/`tsc --noEmit`/`next build`(정적 export, 4개 페이지 정상 생성) 전부 통과.
- **실제 브라우저/배포 백엔드 검증에 대한 한계(투명 공개)**: FE-09 때와 달리 이번 변경은 백엔드 계약(SSE 이벤트) 자체를 바꾸는데, Render는 `main` 브랜치에서만 자동배포되고(`render.yaml`) 별도 스테이징 환경이 없다(SET-06). 이 세션 환경에는 로컬 `GROQ_API_KEY`도 없어, 실제 Groq를 호출하는 완전한 로컬 실행도 불가능했다. 따라서 **실제 Groq 응답으로 SSE `event: followups`가 브라우저에서 렌더링되는 end-to-end 검증은 이번 PM 확인 전에는 못 했다** — pytest/Vitest가 각각 백엔드 SSE 생성부와 프론트 SSE 소비부를 양쪽에서 mock으로 강하게 커버하고 있어 배선 자체의 신뢰도는 높지만, 실제 네트워크·Groq 응답 형식과의 최종 접점은 검증하지 못한 상태다. **제안**: `main` 머지 후 배포되면 실제 사이트에서 메시지 1건을 보내 후속질문 칩이 뜨는지 1회성 스모크 체크를 하겠습니다(SET-* 인프라 스모크와 동일한 성격, 필요하면 `docs/verification/smoke-tests.md`에 기록).

## PM 확인 결과

2026-08-06 PM 승인. 레이트리밋 검토 결론(모니터링 우선, 코드 변경 없음) 그대로 진행. 실제 브라우저/배포 백엔드 검증은 `main` 머지·Render 배포 후 스모크 체크로 진행하기로 합의(`docs/verification/smoke-tests.md` 또는 본 문서에 결과 추가 기록 예정).
