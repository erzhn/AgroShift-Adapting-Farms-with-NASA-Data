"""Справочники: культуры (FAO-56/33), севообороты, цены, нормы затрат, инвестиции."""

import datetime as dt
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, ProvenanceMixin, Timestamps, UUIDPk, enum_col
from app.models.enums import (
    InvestmentType,
    MaturityClass,
    PriceItemKind,
    RotationStatus,
    SourceType,
)


class Crop(UUIDPk, Timestamps, ProvenanceMixin, Base):
    __tablename__ = "crops"

    code: Mapped[str] = mapped_column(String(50), unique=True)  # maize, alfalfa, ...
    name_ky: Mapped[str] = mapped_column(String(100))
    name_ru: Mapped[str] = mapped_column(String(100))
    name_en: Mapped[str] = mapped_column(String(100))
    family: Mapped[str | None] = mapped_column(String(50))  # для правил севооборота
    is_perennial: Mapped[bool] = mapped_column(sa.Boolean, default=False)

    # FAO-56: Kc по стадиям, длительность 4 стадий (ini, dev, mid, late), дни
    kc_ini: Mapped[float] = mapped_column(Float)
    kc_mid: Mapped[float] = mapped_column(Float)
    kc_end: Mapped[float] = mapped_column(Float)
    stage_days: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    height_m: Mapped[float | None] = mapped_column(Float)  # для коррекции Kc (FAO-56 ур. 62)
    root_depth_m: Mapped[float] = mapped_column(Float)
    p_depletion: Mapped[float] = mapped_column(Float)
    # FAO-33: Ky за сезон и по 4 стадиям (М6 перемножает по стадиям)
    ky: Mapped[float] = mapped_column(Float)
    ky_stages: Mapped[list[float] | None] = mapped_column(ARRAY(Float))
    # Температурные пороги
    t_base: Mapped[float] = mapped_column(Float)
    t_min_kill: Mapped[float | None] = mapped_column(Float)
    gdd_required: Mapped[float | None] = mapped_column(Float)  # если задано — стадии по GDD
    t_crit_heat: Mapped[float | None] = mapped_column(Float)   # T_crit для F_heat
    k_heat: Mapped[float | None] = mapped_column(Float)        # k_heat для F_heat
    water_critical_stages: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))

    variants: Mapped[list["CropVariant"]] = relationship(back_populates="crop",
                                                         cascade="all, delete-orphan")


class CropVariant(UUIDPk, Timestamps, ProvenanceMixin, Base):
    __tablename__ = "crop_variants"

    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"),
                                               index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    maturity_class: Mapped[MaturityClass] = mapped_column(enum_col(MaturityClass))
    stage_days_override: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    yield_potential_t_ha: Mapped[float] = mapped_column(Float)
    product: Mapped[str | None] = mapped_column(String(50))  # grain / silage / hay / fruit

    crop: Mapped[Crop] = relationship(back_populates="variants")


class RotationTemplate(UUIDPk, Timestamps, Base):
    """Схема севооборота. В рекомендации попадают только approved (принцип «агроном в контуре»)."""

    __tablename__ = "rotation_templates"

    zone_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(200))
    sequence: Mapped[list[str]] = mapped_column(ARRAY(String(50)))  # коды культур по годам
    min_gap_rules: Mapped[dict] = mapped_column(JSONB, default=dict)
    approved_by: Mapped[str | None] = mapped_column(String(200))  # ФИО агронома
    approved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    status: Mapped[RotationStatus] = mapped_column(enum_col(RotationStatus),
                                                   default=RotationStatus.EXPERIMENTAL)


class PriceItem(UUIDPk, Timestamps, Base):
    __tablename__ = "price_items"

    item_kind: Mapped[PriceItemKind] = mapped_column(enum_col(PriceItemKind))
    item_code: Mapped[str] = mapped_column(String(50), index=True)
    region: Mapped[str] = mapped_column(String(64))
    unit: Mapped[str] = mapped_column(String(16))  # t, kg, l, head, service
    price_som: Mapped[int] = mapped_column(BigInteger)
    date: Mapped[dt.date] = mapped_column(sa.Date)
    source_type: Mapped[SourceType] = mapped_column(enum_col(SourceType))
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    source_note: Mapped[str | None] = mapped_column(Text)  # stat.gov.kg, рынок, ...
    farm_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farms.id"))  # «свои цены»


class CostNorm(UUIDPk, Timestamps, ProvenanceMixin, Base):
    __tablename__ = "cost_norms"

    crop_variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crop_variants.id", ondelete="CASCADE"), index=True
    )
    operation: Mapped[str] = mapped_column(String(64))  # seeds, fertilizer, fuel, water_fee, ...
    month: Mapped[int] = mapped_column(Integer)  # 1..12
    cost_som_ha: Mapped[int] = mapped_column(BigInteger)
    labour_h_ha: Mapped[float] = mapped_column(Float, default=0)
    equipment_type: Mapped[str | None] = mapped_column(String(50))


class Investment(UUIDPk, Timestamps, Base):
    __tablename__ = "investments"

    code: Mapped[str] = mapped_column(String(50), unique=True)
    type: Mapped[InvestmentType] = mapped_column(enum_col(InvestmentType))
    name_ru: Mapped[str] = mapped_column(String(200))
    capex_som: Mapped[int] = mapped_column(BigInteger)       # на единицу (обычно на 1 га)
    opex_som_year: Mapped[int] = mapped_column(BigInteger, default=0)
    lifetime_years: Mapped[int] = mapped_column(Integer)
    efficiency_gain: Mapped[float | None] = mapped_column(Float)  # напр. новый η_field
    subsidy_share: Mapped[float] = mapped_column(Float, default=0.0)
