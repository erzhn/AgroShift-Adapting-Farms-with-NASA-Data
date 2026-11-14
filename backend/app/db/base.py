"""Базовый класс ORM и общие миксины."""

import enum
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import MetaData, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Стабильные имена индексов/ограничений — чтобы Alembic-миграции были детерминированными
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPk:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          default=uuid.uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True),
                                                 server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True),
                                                 server_default=func.now(), onupdate=func.now())


class ProvenanceMixin:
    """Статус входов (раздел 6.3, инвариант 7.2: «значение без источника не сохраняется»).

    Для таблиц с несколькими входными числами: {"taw_mm_per_m": {"source_type": "reference",
    "confidence": 0.5, "note": "SoilGrids"}, ...}. От source_type/confidence зависит ширина
    диапазона в Монте-Карло (М10).
    """

    provenance: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


def enum_col(enum_cls: type[enum.Enum]) -> sa.Enum:
    """Enum хранится как VARCHAR со значением (не нативный тип PG) — проще миграции."""
    return sa.Enum(enum_cls, native_enum=False, length=32,
                   values_callable=lambda e: [m.value for m in e])
