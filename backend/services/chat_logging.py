"""CHAT-09: chat_logs 적재(질의/의도/근거문서/patch/지연시간/콜드스타트, PRD 3-3/9-5).
RAGAS 주간 배치 평가(KPI-02)의 입력이자 KPI-01 지표 계산의 기반이 된다.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from db.models import ChatLog, MetaDocumentEmbedding

# Render 콜드스타트는 실측 50초 이상 지연(무료 인스턴스 슬립 해제, SET-06 스모크
# 테스트 대시보드 안내문), 웜 상태 목표는 p50 3초 이하(PRD 3-3) — 그 사이의
# 안전한 지점인 10초를 콜드스타트 판별 임계값으로 삼는다.
COLD_START_THRESHOLD_MS = 10_000


def record_chat_log(
    db: Session,
    *,
    session_id: str,
    patch_version: str,
    user_query: str,
    intent: str,
    retrieved_docs: list[MetaDocumentEmbedding],
    answer: str,
    latency_ms: int,
) -> ChatLog:
    """의도분류·검색·프롬프트조립이 전부 이뤄진 정상 답변 생성 흐름에서만 호출된다
    (명확화 요청/범위 밖 질문/현재 패치 없음 등 조기 반환 분기는 intent·patch_version이
    없어 로깅 대상이 아님 — WBS 테스트 요구사항도 "정상 답변 생성" 전제)."""
    log = ChatLog(
        session_id=session_id,
        patch_version=patch_version,
        user_query=user_query,
        intent=intent,
        retrieved_doc_ids=[doc.id for doc in retrieved_docs],
        answer=answer,
        latency_ms=latency_ms,
        cold_start=latency_ms >= COLD_START_THRESHOLD_MS,
        created_at=datetime.now(UTC),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
