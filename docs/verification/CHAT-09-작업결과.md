# CHAT-09 : 작업결과

- **TASK**: Q&A 로깅 구현
- **상태**: 완료(PM 승인 2026-08-04)
- **선행 TASK**: DATA-03, CHAT-05
- **근거 문서**: PRD 3-3·9-5
- **변경 파일**: `backend/services/chat_logging.py`(신규), `backend/services/chat_stream.py`(배선), `backend/tests/test_chat09_logging.py`(신규)

## 착수 전 확정한 사항 — 콜드스타트 판별 임계값

`chat_logs.cold_start`를 어떻게 판별할지 문서에 명시된 기준이 없어 이번에 직접 확정: **지연시간 10,000ms(10초) 이상이면 콜드스타트로 간주**. 근거 — Render 콜드스타트는 대시보드 안내상 실측 50초 이상 지연되고(SET-06), 웜 상태 목표는 PRD 3-3 기준 p50 3초 이하라, 그 사이의 안전한 지점을 임계값으로 잡았다. Groq/HF 콜드스타트도 총 지연시간에 자연히 반영되므로 이 하나의 임계값으로 백엔드(Render)·LLM(Groq)·임베딩(HF) 콜드스타트를 전부 포괄한다. 나중에 KPI-01 실측치를 보고 필요하면 조정 가능.

## 결과 요약

- **`chat_logging.py`**: `record_chat_log()` — `session_id`/`patch_version`/`user_query`/`intent`/`retrieved_doc_ids`(검색된 문서 id 목록)/`answer`/`latency_ms`/`cold_start`(임계값 기반 자동 판정) 전체 필드를 `chat_logs`에 적재.
- **`chat_stream.py`** 배선: `generate_answer_stream()`에서 Groq 스트리밍 시작 직전부터 CHAT-07 링크 삽입까지 완료된 시점까지 `time.monotonic()`으로 지연시간을 측정하고, **정상 답변 생성 흐름에서만** 로깅 호출. 명확화 요청/범위 밖 질문/현재 패치 없음 조기 반환 분기는 `intent`·`patch_version`이 아예 계산되지 않아 로깅 대상에서 제외(WBS 테스트 요구사항도 "정상 답변 생성" 전제와 일치).

## 자체 검증

- pytest 6건 신규(backend 전체 **163/163 통과**), ruff check/format 통과
  - `record_chat_log()`: 전체 필드 정확히 적재, 임계값 이상/미만 콜드스타트 판정, 빈 검색결과일 때 `retrieved_doc_ids=[]`
  - `generate_answer_stream()` 배선: 정상 흐름에서 `chat_logs` row가 실제로 생성되고 세션ID/패치버전/질의/답변이 정확히 들어가는지, 명확화 분기에서는 `chat_logs`가 생성되지 않는지(fake 함수가 호출되면 테스트가 실패하도록 설계해 파이프라인 자체가 안 도는 것도 함께 확인)
