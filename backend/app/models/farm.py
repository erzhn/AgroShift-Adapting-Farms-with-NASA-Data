"""Цифровой профиль хозяйства — разделы 3.3, 7.1 ТЗ.

Инварианты (7.2):
- деньги — целые сомы (BigInteger), тыйыны не используются;
- вода — м³ и мм (1 мм на 1 га = 10 м³);
- сумма площадей культур на поле в любом году <= area_ha (допуск 0,1%) — проверяется в сервисе;
- финансовые поля (cash, obligations) в пилоте шифруются на уровне приложения (AES-256-GCM).
"""

import datetime as dt
import uuid
from datetime import date

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.db.base import Base, ProvenanceMixin, Timestamps, UUIDPk, enum_col
from app.models.enums import (
    HerdPurpose,
    IrrigationMethod,
    ObligationType,
    Ownership,
    Rootstock,
    SourceType,
    Species,
)


class Farm(UUIDPk, Timestamps, Base):
    __tablename__ = "farms"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), unique=True
    )
    name: Mapped[str] = mapped_column(String(200))
    district: Mapped[str | None] = mapped_column(String(100))
    village: Mapped[str | None] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(2), default="ky")
    # Минимальные расходы семьи в месяц (Family_m в М9), сом
    family_reserve_som: Mapped[int | None] = mapped_column(BigInteger)
    # Доступный труд по месяцам, чел.-ч (12 значений)
    labour_hours_month: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    # Согласия фермера (раздел 12.3) — три отдельных переключателя, по умолчанию выключены
    consent_agronomist: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_canal_plan: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_analytics: Mapped[bool] = mapped_column(Boolean, default=False)

    fields: Mapped[list["Field"]] = relationship(back_populates="farm",
                                                 cascade="all, delete-orphan")
    orchards: Mapped[list["Orchard"]] = relationship(cascade="all, delete-orphan")
    herds: Mapped[list["Herd"]] = relationship(cascade="all, delete-orphan")
    equipment: Mapped[list["Equipment"]] = relationship(cascade="all, delete-orphan")
    obligations: Mapped[list["Obligation"]] = relationship(cascade="all, delete-orphan")
    cash_accounts: Mapped[list["CashAccount"]] = relationship(cascade="all, delete-orphan")


class Field(UUIDPk, Timestamps, ProvenanceMixin, Base):
    __tablename__ = "fields"

    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"),
                                               index=True)
    name: Mapped[str] = mapped_column(String(100))
    # Контур поля (FR-1.4). Может отсутствовать: тогда есть точка + площадь вручную.
    geometry = mapped_column(Geometry("POLYGON", srid=4326), nullable=True)
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    area_ha: Mapped[float] = mapped_column(Float)
    elevation_m: Mapped[float | None] = mapped_column(Float)   # NASADEM
    slope_deg: Mapped[float | None] = mapped_column(Float)
    soil_type: Mapped[str | None] = mapped_column(String(32))  # из справочника или "unknown"
    taw_mm_per_m: Mapped[float | None] = mapped_column(Float)  # доступная влага почвы
    irrigation_method: Mapped[IrrigationMethod] = mapped_column(
        enum_col(IrrigationMethod), default=IrrigationMethod.FURROW
    )
    canal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("canals.id"))
    intake_point = mapped_column(Geometry("POINT", srid=4326), nullable=True)

    # GeoJSON для API без лишних зависимостей (shapely не нужен)
    geometry_geojson: Mapped[str | None] = column_property(func.ST_AsGeoJSON(geometry))
    location_geojson: Mapped[str | None] = column_property(func.ST_AsGeoJSON(location))

    farm: Mapped[Farm] = relationship(back_populates="fields")
    seasons: Mapped[list["CropSeason"]] = relationship(cascade="all, delete-orphan")


class Orchard(UUIDPk, Timestamps, Base):
    """Сад — отдельная модель на горизонт до 25 лет (М7)."""

    __tablename__ = "orchards"

    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"),
                                               index=True)
    field_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fields.id"))
    species: Mapped[str] = mapped_column(String(50))  # apple, apricot, ...
    variety: Mapped[str | None] = mapped_column(String(100))
    planted_year: Mapped[int | None] = mapped_column(Integer)
    density_trees_ha: Mapped[int | None] = mapped_column(Integer)
    rootstock: Mapped[Rootstock | None] = mapped_column(enum_col(Rootstock))
    yield_curve_id: Mapped[str | None] = mapped_column(String(64))


class Herd(UUIDPk, Timestamps, Base):
    __tablename__ = "herds"

    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"),
                                               index=True)
    species: Mapped[Species] = mapped_column(enum_col(Species))
    head_count: Mapped[int] = mapped_column(Integer)
    purpose: Mapped[HerdPurpose] = mapped_column(enum_col(HerdPurpose))
    feed_ration_id: Mapped[str | None] = mapped_column(String(64))


class Equipment(UUIDPk, Timestamps, Base):
    __tablename__ = "equipment"

    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"),
                                               index=True)
    type: Mapped[str] = mapped_column(String(50))  # tractor, seeder, baler, ...
    capacity: Mapped[str | None] = mapped_column(String(50))
    ownership: Mapped[Ownership] = mapped_column(enum_col(Ownership))


class Obligation(UUIDPk, Timestamps, Base):
    """Долги, контракты на поставку, закупки корма. Финансы: не передаются АВП и кооперативу."""

    __tablename__ = "obligations"

    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"),
                                               index=True)
    type: Mapped[ObligationType] = mapped_column(enum_col(ObligationType))
    # [{"month": "2027-04", "amount_som": 15000}, ...]
    amounts_by_month: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    counterparty: Mapped[str | None] = mapped_column(String(200))
    penalty_som: Mapped[int | None] = mapped_column(BigInteger)


class CashAccount(UUIDPk, Timestamps, Base):
    """Свободные средства хозяйства (UC-1, шаг «Деньги»)."""

    __tablename__ = "cash_accounts"

    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"),
                                               index=True)
    name: Mapped[str] = mapped_column(String(100), default="Основной")
    balance_som: Mapped[int] = mapped_column(BigInteger)
    as_of: Mapped[date] = mapped_column(sa.Date)


class Goal(UUIDPk, Timestamps, Base):
    """План от цели (UC-6): превращается в жёсткие ограничения оптимизатора М11."""

    __tablename__ = "goals"

    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"),
                                               index=True)
    min_income_som: Mapped[int | None] = mapped_column(BigInteger)
    keep_herd: Mapped[bool] = mapped_column(Boolean, default=False)
    max_debt_som: Mapped[int | None] = mapped_column(BigInteger)
    horizon_years: Mapped[int] = mapped_column(Integer, default=3)
    priority_weights: Mapped[dict] = mapped_column(JSONB, default=dict)


class CropSeason(UUIDPk, Timestamps, Base):
    """Культура на поле в сезон. Одно поле — одна основная культура + опц. пожнивная."""

    __tablename__ = "crop_seasons"

    field_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"),
                                                index=True)
    crop_variant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crop_variants.id"))
    year: Mapped[int] = mapped_column(Integer)
    is_main: Mapped[bool] = mapped_column(Boolean, default=True)
    sowing_date: Mapped[date | None] = mapped_column(sa.Date)
    harvest_date: Mapped[date | None] = mapped_column(sa.Date)
    planned_yield_t_ha: Mapped[float | None] = mapped_column(Float)
    actual_yield_t_ha: Mapped[float | None] = mapped_column(Float)


class WaterEvent(UUIDPk, Timestamps, Base):
    """Факт полива (UC-8)."""

    __tablename__ = "water_events"

    field_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"),
                                                index=True)
    date: Mapped[dt.date] = mapped_column(sa.Date)
    hours: Mapped[float | None] = mapped_column(Float)
    volume_m3: Mapped[float | None] = mapped_column(Float)
    measured: Mapped[bool] = mapped_column(Boolean, default=False)
    source_type: Mapped[SourceType] = mapped_column(enum_col(SourceType),
                                                    default=SourceType.USER_ESTIMATE)
    entered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class PlanFact(UUIDPk, Timestamps, Base):
    """План-факт по метрике за сезон (М16)."""

    __tablename__ = "plan_facts"

    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"),
                                               index=True)
    season: Mapped[int] = mapped_column(Integer)
    metric: Mapped[str] = mapped_column(String(64))
    planned: Mapped[float | None] = mapped_column(Float)
    actual: Mapped[float | None] = mapped_column(Float)
    deviation: Mapped[float | None] = mapped_column(Float)
    cause_note: Mapped[str | None] = mapped_column(Text)
