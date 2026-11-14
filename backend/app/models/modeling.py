"""Сценарии, стратегии, расчёты и снимки данных — центр прослеживаемости (раздел 3.5).

Расчёт (Run) = прогон Стратегии через Сценарий на фиксированных Снимках данных
и фиксированной версии модели с фиксированным seed. Run неизменяем: пересчёт = новый Run.
"""

import datetime as dt
import uuid
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, ProvenanceMixin, Timestamps, UUIDPk, enum_col
from app.models.enums import ClimateMode, Completeness, MetricPeriod, RunStatus, StrategyType


class DataSnapshot(UUIDPk, Timestamps, Base):
    """Неизменяемая версия входных данных (раздел 6.3). Расчёт ссылается на снимок, а не на API."""

    __tablename__ = "data_snapshots"

    code: Mapped[str] = mapped_column(String(128), unique=True)  # power_ag_42.87_74.59_v2025-11-10
    source: Mapped[str] = mapped_column(String(64))  # nasa_power_daily_ag, gpm_imerg, ...
    product_version: Mapped[str | None] = mapped_column(String(64))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    bbox: Mapped[list[float] | None] = mapped_column(ARRAY(Float))  # [minx, miny, maxx, maxy]
    cell_elevation_m: Mapped[float | None] = mapped_column(Float)
    period_start: Mapped[date] = mapped_column(sa.Date)
    period_end: Mapped[date] = mapped_column(sa.Date)
    fetched_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    sha256: Mapped[str] = mapped_column(String(64))
    storage_uri: Mapped[str] = mapped_column(String(500))  # относительный путь / s3://...
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)


class ClimateDaily(Base):
    """Суточные климатические ряды (раздел 11.3).

    TODO(пилот): превратить в hypertable TimescaleDB:
        SELECT create_hypertable('climate_daily', 'date');
    На хакатоне ряды читаются прямо из Parquet-снимков, таблица — для пилота.
    """

    __tablename__ = "climate_daily"

    cell_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    date: Mapped[dt.date] = mapped_column(sa.Date, primary_key=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_snapshots.id", ondelete="CASCADE"), primary_key=True
    )
    t2m: Mapped[float | None] = mapped_column(Float)
    tmax: Mapped[float | None] = mapped_column(Float)
    tmin: Mapped[float | None] = mapped_column(Float)
    tdew: Mapped[float | None] = mapped_column(Float)
    rh: Mapped[float | None] = mapped_column(Float)
    ws2m: Mapped[float | None] = mapped_column(Float)
    rs: Mapped[float | None] = mapped_column(Float)  # МДж/м²/сут
    precip: Mapped[float | None] = mapped_column(Float)
    et0: Mapped[float | None] = mapped_column(Float)


class ModelVersion(UUIDPk, Timestamps, Base):
    """SemVer модели: изменение формулы = новая минорная версия + changelog (раздел 12.5)."""

    __tablename__ = "model_versions"

    semver: Mapped[str] = mapped_column(String(32), unique=True)
    changelog: Mapped[str | None] = mapped_column(Text)
    params_hash: Mapped[str | None] = mapped_column(String(64))


class Scenario(UUIDPk, Timestamps, ProvenanceMixin, Base):
    """Внешние условия (ползунки UC-3). farm_id = NULL — готовый сценарий для всех (FR-5.2)."""

    __tablename__ = "scenarios"

    farm_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    preset_code: Mapped[str | None] = mapped_column(String(50), unique=True)
    water_supply_factor: Mapped[float] = mapped_column(Float, default=1.0)  # 0.5..1.2
    # NULL = весь сезон; [7, 8] = только июль–август (FR-5.2).
    water_supply_months: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    supply_shift_days: Mapped[int] = mapped_column(Integer, default=0)     # -30..30
    temp_delta_c: Mapped[float] = mapped_column(Float, default=0.0)        # 0..3
    precip_factor: Mapped[float] = mapped_column(Float, default=1.0)       # 0.5..1.3
    price_factors: Mapped[dict] = mapped_column(JSONB, default=dict)       # {"crop": 1.0, ...}
    payment_delay_days: Mapped[int] = mapped_column(Integer, default=0)    # 0..120
    yield_factor: Mapped[float] = mapped_column(Float, default=1.0)        # 0.7..1.3
    climate_mode: Mapped[ClimateMode] = mapped_column(enum_col(ClimateMode),
                                                      default=ClimateMode.HISTORICAL_YEAR)
    climate_params: Mapped[dict] = mapped_column(JSONB, default=dict)  # {"year": 2023} и т.п.


class Strategy(UUIDPk, Timestamps, Base):
    __tablename__ = "strategies"

    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"),
                                               index=True)
    type: Mapped[StrategyType] = mapped_column(enum_col(StrategyType))
    name: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)  # одна фраза-суть (FR-4.2)
    horizon_years: Mapped[int] = mapped_column(Integer, default=3)
    # [{"year": 2027, "field_id": ..., "crop_variant": "maize_silage", "area_ha": 2.0}, ...]
    # + инвестиции, изменения стада, каналы сбыта
    decisions: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    agronomy_status: Mapped[str] = mapped_column(String(32), default="experimental")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

    runs: Mapped[list["Run"]] = relationship(back_populates="strategy")


class Run(UUIDPk, Timestamps, Base):
    __tablename__ = "runs"

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategies.id", ondelete="CASCADE"), index=True
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenarios.id"))
    snapshot_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)))
    model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_versions.id"))
    seed: Mapped[int] = mapped_column(BigInteger)
    n_samples: Mapped[int] = mapped_column(Integer)
    status: Mapped[RunStatus] = mapped_column(enum_col(RunStatus), default=RunStatus.QUEUED)
    completeness: Mapped[Completeness] = mapped_column(enum_col(Completeness),
                                                       default=Completeness.COMPLETE)
    unknown_inputs: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    results_uri: Mapped[str | None] = mapped_column(String(500))  # Parquet полных выборок
    results_sha256: Mapped[str | None] = mapped_column(String(64))  # тест воспроизводимости
    error: Mapped[str | None] = mapped_column(Text)

    strategy: Mapped[Strategy] = relationship(back_populates="runs")
    metrics: Mapped[list["RunMetric"]] = relationship(cascade="all, delete-orphan")
    breakpoints: Mapped[list["Breakpoint"]] = relationship(cascade="all, delete-orphan")


class RunMetric(UUIDPk, Base):
    """Сводная метрика прогона: P10/P50/P90 по периоду."""

    __tablename__ = "run_metrics"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"),
                                              index=True)
    metric: Mapped[str] = mapped_column(String(64))  # net_income_som, water_gross_m3, ...
    period: Mapped[MetricPeriod] = mapped_column(enum_col(MetricPeriod))
    period_key: Mapped[str] = mapped_column(String(16))  # "2027", "2027-07", "2027-D20"
    p10: Mapped[float | None] = mapped_column(Float)
    p50: Mapped[float | None] = mapped_column(Float)
    p90: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))


class Breakpoint(UUIDPk, Base):
    """Точка поломки (М13)."""

    __tablename__ = "breakpoints"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"),
                                              index=True)
    factor: Mapped[str] = mapped_column(String(64))
    threshold_value: Mapped[float] = mapped_column(Float)
    violated_constraint: Mapped[str] = mapped_column(String(64))
    historical_frequency: Mapped[float | None] = mapped_column(Float)  # 7/30 = 0.233
    margin_sd: Mapped[float | None] = mapped_column(Float)  # запас прочности в σ фактора
    explanation_key: Mapped[str] = mapped_column(String(100))
    explanation_params: Mapped[dict] = mapped_column(JSONB, default=dict)
