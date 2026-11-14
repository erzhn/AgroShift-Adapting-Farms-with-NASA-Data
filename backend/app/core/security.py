"""Аутентификация.

Хакатон: демо-режим — пользователь не логинится, роль берётся из заголовка X-Demo-Role
(переключатель «Фермер / АВП», раздел 14.1).
Пилот: вход по SMS-коду (FR-1.1) -> JWT на 30 дней (раздел 12.3).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import get_settings
from app.models.enums import Role


@dataclass(frozen=True)
class Principal:
    user_id: UUID | None
    roles: frozenset[Role] = field(default_factory=frozenset)
    language: str = "ru"
    is_demo: bool = False

    def has(self, role: Role) -> bool:
        return role in self.roles


def create_access_token(user_id: UUID, roles: list[Role]) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "roles": [r.value for r in roles],
        "iat": now,
        "exp": now + timedelta(days=s.jwt_expire_days),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> Principal:
    s = get_settings()
    data = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    return Principal(user_id=UUID(data["sub"]), roles=frozenset(Role(r) for r in data["roles"]))
