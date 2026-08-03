from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patch_version: Mapped[str] = mapped_column(
        String, ForeignKey("patches.version"), nullable=False
    )
    riot_champion_id: Mapped[str] = mapped_column(String, nullable=False)
    name_kr: Mapped[str] = mapped_column(String, nullable=False)
    name_en: Mapped[str] = mapped_column(String, nullable=False)
    cost: Mapped[int] = mapped_column(Integer, nullable=False)


class Trait(Base):
    __tablename__ = "traits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patch_version: Mapped[str] = mapped_column(
        String, ForeignKey("patches.version"), nullable=False
    )
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


class Augment(Base):
    __tablename__ = "augments"

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


class Comp(Base):
    __tablename__ = "comps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patch_version: Mapped[str] = mapped_column(
        String, ForeignKey("patches.version"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    tier_rank: Mapped[str] = mapped_column(String, nullable=False)
    avg_place: Mapped[float] = mapped_column(Float, nullable=False)
    play_rate: Mapped[float] = mapped_column(Float, nullable=False)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    playstyle_text: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class CompChampion(Base):
    __tablename__ = "comp_champions"

    comp_id: Mapped[int] = mapped_column(ForeignKey("comps.id"), primary_key=True)
    champion_id: Mapped[int] = mapped_column(
        ForeignKey("champions.id"), primary_key=True
    )
    is_carry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recommended_items: Mapped[dict] = mapped_column(JSONB, nullable=False)


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
