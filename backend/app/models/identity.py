"""Пользователи, рабочие пространства и роли — раздел 4 ТЗ."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk, enum_col
from app.models.enums import AccessScope, Role, WorkspaceType


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"

    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    name: Mapped[str | None] = mapped_column(String(200))
    language: Mapped[str] = mapped_column(String(2), default="ky")  # ky | ru | en

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", foreign_keys="Membership.user_id", cascade="all, delete-orphan"
    )


class Workspace(UUIDPk, Timestamps, Base):
    """Рабочее пространство: хозяйство, кооператив, канал АВП или организация."""

    __tablename__ = "workspaces"

    type: Mapped[WorkspaceType] = mapped_column(enum_col(WorkspaceType))
    name: Mapped[str] = mapped_column(String(200))
    region_id: Mapped[str | None] = mapped_column(String(64))  # код района/области

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class Membership(UUIDPk, Timestamps, Base):
    """Роль пользователя в рабочем пространстве. Один человек — несколько ролей."""

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "workspace_id", "role",
                                       name="uq_memberships_user_ws_role"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                               index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[Role] = mapped_column(enum_col(Role))
    # Объём доступа агронома/кооператива, выданный владельцем (раздел 4.4)
    scope: Mapped[AccessScope | None] = mapped_column(enum_col(AccessScope))
    granted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="memberships", foreign_keys=[user_id])
    workspace: Mapped[Workspace] = relationship(back_populates="memberships")
