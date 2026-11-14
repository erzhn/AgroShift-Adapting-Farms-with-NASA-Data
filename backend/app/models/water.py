"""Канал, подача, водные права, совместный план канала (UC-5, М15)."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Column, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk, enum_col
from app.models.enums import CanalPlanStatus, ProposalResponse, SourceType


class Canal(UUIDPk, Timestamps, Base):
    __tablename__ = "canals"

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id"))
    name: Mapped[str] = mapped_column(String(200))
    avp_name: Mapped[str | None] = mapped_column(String(200))
    geometry = mapped_column(Geometry("MULTILINESTRING", srid=4326), nullable=True)
    snow_catchment_geometry = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)
    # η_conv — КПД доставки (раздел 8.5). По умолчанию 0,35–0,70 с пометкой «оценка»
    conveyance_efficiency: Mapped[float] = mapped_column(Float, default=0.5)
    conveyance_source_type: Mapped[SourceType] = mapped_column(
        enum_col(SourceType), default=SourceType.USER_ESTIMATE
    )
    invite_code: Mapped[str | None] = mapped_column(String(16), unique=True)  # FR-8.1

    supply: Mapped[list["SupplySchedule"]] = relationship(cascade="all, delete-orphan")


class SupplySchedule(UUIDPk, Timestamps, Base):
    """Доступная подача на голове канала по декадам (FR-8.2)."""

    __tablename__ = "supply_schedules"
    __table_args__ = (sa.UniqueConstraint("canal_id", "season", "decade_index",
                                          name="uq_supply_canal_season_decade"),)

    canal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("canals.id", ondelete="CASCADE"),
                                                index=True)
    season: Mapped[int] = mapped_column(Integer)
    decade_index: Mapped[int] = mapped_column(Integer)  # 0..35 (см. agroshift_core.calendar)
    volume_m3: Mapped[float] = mapped_column(Float)
    source_type: Mapped[SourceType] = mapped_column(enum_col(SourceType))
    reliability: Mapped[float] = mapped_column(Float, default=0.8)  # 0..1


class WaterRight(UUIDPk, Timestamps, Base):
    """Сезонный лимит хозяйства: м³ или «часы полива по очереди»."""

    __tablename__ = "water_rights"

    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"),
                                               index=True)
    canal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("canals.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    limit_m3: Mapped[float | None] = mapped_column(Float)
    limit_hours: Mapped[float | None] = mapped_column(Float)
    flow_l_s: Mapped[float | None] = mapped_column(Float)  # расход на водовыпуске
    turn_interval_days: Mapped[int | None] = mapped_column(Integer)
    turn_hours: Mapped[float | None] = mapped_column(Float)  # длительность одной очереди
    failure_months: Mapped[list[int] | None] = mapped_column(sa.ARRAY(Integer))  # «месяцы срывов»
    legal_basis: Mapped[str | None] = mapped_column(String(200))
    source_type: Mapped[SourceType] = mapped_column(enum_col(SourceType))
    confidence: Mapped[float] = mapped_column(Float, default=0.5)


canal_plan_members = Table(
    "canal_plan_members",
    Base.metadata,
    Column("canal_plan_id", ForeignKey("canal_plans.id", ondelete="CASCADE"), primary_key=True),
    Column("farm_id", ForeignKey("farms.id", ondelete="CASCADE"), primary_key=True),
)


class CanalPlan(UUIDPk, Timestamps, Base):
    __tablename__ = "canal_plans"

    canal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("canals.id", ondelete="CASCADE"),
                                                index=True)
    season: Mapped[int] = mapped_column(Integer)
    status: Mapped[CanalPlanStatus] = mapped_column(enum_col(CanalPlanStatus),
                                                    default=CanalPlanStatus.DRAFT)
    # Итоги координации: пик до/после, суммарный выигрыш (для экрана АВП)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)

    proposals: Mapped[list["CanalProposal"]] = relationship(cascade="all, delete-orphan")


class CanalProposal(UUIDPk, Timestamps, Base):
    """Предложение конкретному хозяйству. Деньги других хозяйств не раскрываются."""

    __tablename__ = "canal_proposals"

    canal_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canal_plans.id", ondelete="CASCADE"), index=True
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    # {"kind": "shift_sowing" | "variant" | "area", ...детали}
    change: Mapped[dict] = mapped_column(JSONB)
    water_delta_m3: Mapped[float] = mapped_column(Float, default=0)
    income_delta_som: Mapped[int] = mapped_column(BigInteger, default=0)
    compensation_som: Mapped[int] = mapped_column(BigInteger, default=0)
    response: Mapped[ProposalResponse] = mapped_column(enum_col(ProposalResponse),
                                                       default=ProposalResponse.PENDING)
    counter_note: Mapped[str | None] = mapped_column(Text)
    responded_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
