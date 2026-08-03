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
