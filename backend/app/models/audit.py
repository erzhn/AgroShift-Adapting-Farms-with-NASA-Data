"""Журнал аудита (только добавление) и история ИИ-помощника."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import BigInteger, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk


class AuditLog(Base):
    """Любое изменение чужих данных, лимитов канала и справочников — с диффом (раздел 12.3).

    TODO(пилот): REVOKE UPDATE, DELETE ON audit_log — журнал только для добавления.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32))  # create / update / delete / approve
    diff: Mapped[dict] = mapped_column(JSONB, default=dict)
    at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=func.now())


class ChatSession(UUIDPk, Timestamps, Base):
    __tablename__ = "chat_sessions"

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    farm_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    language: Mapped[str] = mapped_column(String(2), default="ru")

    messages: Mapped[list["ChatMessage"]] = relationship(cascade="all, delete-orphan",
                                                         order_by="ChatMessage.created_at")


class ChatMessage(UUIDPk, Timestamps, Base):
    __tablename__ = "chat_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user / assistant / tool
    content: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    linked_run_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)),
                                                            default=list)
