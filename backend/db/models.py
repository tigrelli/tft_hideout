from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
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
