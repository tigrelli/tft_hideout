from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 1024  # BGE-M3


class Base(DeclarativeBase):
    pass


class Patch(Base):
    __tablename__ = "patches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    released_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class Champion(Base):
    __tablename__ = "champions"
    __table_args__ = (
        UniqueConstraint(
            "patch_version", "riot_champion_id", name="uq_champions_patch_riot_id"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patch_version: Mapped[str] = mapped_column(
        String, ForeignKey("patches.version"), nullable=False
    )
    riot_champion_id: Mapped[str] = mapped_column(String, nullable=False)
    name_kr: Mapped[str] = mapped_column(String, nullable=False)
    name_en: Mapped[str] = mapped_column(String, nullable=False)
    cost: Mapped[int] = mapped_column(Integer, nullable=False)
    square_icon_url: Mapped[str | None] = mapped_column(String, nullable=True)


class Trait(Base):
    __tablename__ = "traits"
    __table_args__ = (
        UniqueConstraint(
            "patch_version", "riot_trait_id", name="uq_traits_patch_riot_id"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patch_version: Mapped[str] = mapped_column(
        String, ForeignKey("patches.version"), nullable=False
    )
    riot_trait_id: Mapped[str] = mapped_column(String, nullable=False)
    name_kr: Mapped[str] = mapped_column(String, nullable=False)
    name_en: Mapped[str] = mapped_column(String, nullable=False)
    tier_thresholds: Mapped[dict] = mapped_column(JSONB, nullable=False)


class ChampionTrait(Base):
    __tablename__ = "champion_traits"

    champion_id: Mapped[int] = mapped_column(
        ForeignKey("champions.id"), primary_key=True
    )
    trait_id: Mapped[int] = mapped_column(ForeignKey("traits.id"), primary_key=True)


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint(
            "patch_version", "riot_item_id", name="uq_items_patch_riot_id"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patch_version: Mapped[str] = mapped_column(
        String, ForeignKey("patches.version"), nullable=False
    )
    name_kr: Mapped[str] = mapped_column(String, nullable=False)
    name_en: Mapped[str] = mapped_column(String, nullable=False)
    item_type: Mapped[str] = mapped_column(String, nullable=False)
    riot_item_id: Mapped[str] = mapped_column(String, nullable=False)
    components: Mapped[dict] = mapped_column(JSONB, nullable=False)
    stats: Mapped[dict] = mapped_column(JSONB, nullable=False)
    square_icon_url: Mapped[str | None] = mapped_column(String, nullable=True)


class Augment(Base):
    __tablename__ = "augments"
    __table_args__ = (
        UniqueConstraint(
            "patch_version", "riot_augment_id", name="uq_augments_patch_riot_id"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patch_version: Mapped[str] = mapped_column(
        String, ForeignKey("patches.version"), nullable=False
    )
    name_kr: Mapped[str] = mapped_column(String, nullable=False)
    name_en: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_legend_related: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    riot_augment_id: Mapped[str] = mapped_column(String, nullable=False)
    # API-05 마스킹 대상. op.gg/Riot 어디에도 증강체 단위 승률 데이터 소스가 없어
    # 배치는 채우지 않고 항상 NULL(DATA-05 스파이크, PM 승인 2026-08-04)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)


class Comp(Base):
    __tablename__ = "comps"
    __table_args__ = (
        UniqueConstraint(
            "patch_version", "riot_comp_id", name="uq_comps_patch_riot_id"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patch_version: Mapped[str] = mapped_column(
        String, ForeignKey("patches.version"), nullable=False
    )
    riot_comp_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    tier_rank: Mapped[str] = mapped_column(String, nullable=False)
    avg_place: Mapped[float] = mapped_column(Float, nullable=False)
    play_rate: Mapped[float] = mapped_column(Float, nullable=False)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    playstyle_text: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # DATA-17: op.gg 상위 10위 목록에서 빠진(메타 회전) 조합의 소프트 삭제
    # 플래그. false여도 행은 유지되어 comp_champions/comp_augments·
    # match_analyses.matched_comp_id FK와 meta_document_embeddings 참조가
    # 끊기지 않는다 — 티어리스트 API만 is_active=true로 필터링한다.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CompChampion(Base):
    __tablename__ = "comp_champions"

    comp_id: Mapped[int] = mapped_column(ForeignKey("comps.id"), primary_key=True)
    champion_id: Mapped[int] = mapped_column(
        ForeignKey("champions.id"), primary_key=True
    )
    is_carry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # op.gg 응답의 아이템 ID 문자열 목록 그대로(batch/normalize.py comp_champion_rows).
    # DATA-02 마이그레이션 당시 dict로 잘못 가정했던 걸 FE-04 착수 중 실 데이터로
    # 발견해 바로잡음(2026-08-04) — JSONB 컬럼 자체는 스키마 변경 불필요.
    recommended_items: Mapped[list] = mapped_column(JSONB, nullable=False)
    # FE-14: op.gg tft_list_meta_decks 응답 units[].cell.{x,y}(x:1~7, y:1~4,
    # 4행x7열 실제 랭커 배치 좌표, 2026-08-06 실호출로 확인). 구 데이터(이
    # 컬럼 추가 전 배치가 채운 행)는 NULL — 프론트가 NULL이면 기존 is_carry
    # 휴리스틱 배치로 폴백한다.
    cell_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cell_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # FE-15: op.gg tft_list_meta_decks 응답 units[].tier(정수 2 또는 3, 성급,
    # 2026-08-06 실호출로 확인). 구 데이터(이 컬럼 추가 전 배치가 채운 행)와
    # 챔피언에 성급 정보가 없는 경우는 NULL — 프론트가 NULL이면 별 표시를 생략한다.
    star_level: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CompAugment(Base):
    __tablename__ = "comp_augments"

    comp_id: Mapped[int] = mapped_column(ForeignKey("comps.id"), primary_key=True)
    augment_id: Mapped[int] = mapped_column(ForeignKey("augments.id"), primary_key=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)


class ChampionItemBuild(Base):
    __tablename__ = "champion_item_builds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    champion_id: Mapped[int] = mapped_column(ForeignKey("champions.id"), nullable=False)
    patch_version: Mapped[str] = mapped_column(
        String, ForeignKey("patches.version"), nullable=False
    )
    item_combination: Mapped[dict] = mapped_column(JSONB, nullable=False)
    play_rate: Mapped[float] = mapped_column(Float, nullable=False)
    avg_place: Mapped[float] = mapped_column(Float, nullable=False)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False)


class MatchAnalysis(Base):
    __tablename__ = "match_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[str] = mapped_column(String, nullable=False)
    puuid: Mapped[str] = mapped_column(String, nullable=False)
    patch_version: Mapped[str] = mapped_column(
        String, ForeignKey("patches.version"), nullable=False
    )
    comp_deviation: Mapped[float] = mapped_column(Float, nullable=False)
    item_concentration: Mapped[float] = mapped_column(Float, nullable=False)
    augment_synergy: Mapped[float] = mapped_column(Float, nullable=False)
    matched_comp_id: Mapped[int | None] = mapped_column(
        ForeignKey("comps.id"), nullable=True
    )
    coaching_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    patch_version: Mapped[str] = mapped_column(
        String, ForeignKey("patches.version"), nullable=False
    )
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String, nullable=False)
    retrieved_doc_ids: Mapped[dict] = mapped_column(JSONB, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    cold_start: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class LinkClickEvent(Base):
    __tablename__ = "link_click_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    chat_log_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_logs.id"), nullable=True
    )
    target_page: Mapped[str] = mapped_column(String, nullable=False)
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AccountLinkEvent(Base):
    __tablename__ = "account_link_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    riot_id_hash: Mapped[str] = mapped_column(String, nullable=False)
    region: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    match_id: Mapped[str | None] = mapped_column(String, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class PatchDetectionRun(Base):
    __tablename__ = "patch_detection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    patch_version_before: Mapped[str] = mapped_column(String, nullable=False)
    patch_version_after: Mapped[str] = mapped_column(String, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)


class RagasEvalResult(Base):
    __tablename__ = "ragas_eval_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    eval_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sample_query: Mapped[str] = mapped_column(Text, nullable=False)
    faithfulness_score: Mapped[float] = mapped_column(Float, nullable=False)
    answer_relevancy_score: Mapped[float] = mapped_column(Float, nullable=False)
    patch_version: Mapped[str] = mapped_column(
        String, ForeignKey("patches.version"), nullable=False
    )


class ChatAnswerCache(Base):
    """캐시 전략(개발설계서 v1.7 4.6절): 첫 턴 질문만 캐시, patch_version 불일치 시
    자연 무효화, 패치 배치 완료 후 이전 patch_version 행은 DATA-15 배치가 DELETE."""

    __tablename__ = "chat_answer_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    patch_version: Mapped[str] = mapped_column(
        String, ForeignKey("patches.version"), nullable=False
    )
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String, nullable=True)
    retrieved_doc_ids: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class PuuidCache(Base):
    """캐시 전략(개발설계서 v1.7 4.6절): expires_at = 생성시점+1시간,
    Personal Key 레이트리밋 보호 목적의 단기 캐시."""

    __tablename__ = "puuid_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    puuid: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class MetaDocumentEmbedding(Base):
    __tablename__ = "meta_document_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "patch_version",
            "doc_type",
            "source_table",
            "source_id",
            name="uq_meta_document_embeddings_patch_doctype_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patch_version: Mapped[str] = mapped_column(
        String, ForeignKey("patches.version"), nullable=False
    )
    doc_type: Mapped[str] = mapped_column(String, nullable=False)
    source_table: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=False
    )
    doc_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False)
