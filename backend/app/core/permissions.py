"""Матрица прав из раздела 4.3 ТЗ — единственный источник правды для авторизации.

R — чтение, W — изменение, A — утверждение, "agg" — только агрегаты (k >= 10).
"*" в ТЗ (доступ агронома/кооператива только по приглашению владельца) проверяется
отдельно через Membership.scope — см. app/api/deps.py.

TODO(пилот): дублировать на уровне БД через Row Level Security (раздел 11.3).
"""

from enum import StrEnum

from app.models.enums import Role


class Obj(StrEnum):
    FARM_PROFILE = "farm_profile"          # профиль хозяйства, поля
    FARM_FINANCE = "farm_finance"          # финансы хозяйства
    FACT_EVENTS = "fact_events"            # факт поливов и работ
    STRATEGIES = "strategies"              # стратегии и сценарии
    CANAL_CROP_PLAN = "canal_crop_plan"    # план посевов (без денег) для плана канала
    CANAL_SUPPLY = "canal_supply"          # лимиты и график подачи канала
    CANAL_PROPOSAL = "canal_proposal"      # предложение согласования канала
    ROTATIONS = "rotations"                # схемы севооборота и каталог культур
    PRICES = "prices"                      # справочники цен
    DATA_SOURCES = "data_sources"          # источники данных, версии моделей


F, WK, AG, CO, AVP, AN, AD = (Role.FARMER, Role.WORKER, Role.AGRONOMIST, Role.COOP,
                              Role.AVP, Role.ANALYST, Role.ADMIN)

# (объект, роль) -> набор прав. Нет ключа = нет доступа.
MATRIX: dict[Obj, dict[Role, str]] = {
    Obj.FARM_PROFILE:    {F: "RW", WK: "R", AG: "RW*", CO: "R*", AVP: "R", AN: "agg", AD: "R"},
    Obj.FARM_FINANCE:    {F: "RW", AG: "RW*"},
    Obj.FACT_EVENTS:     {F: "RW", WK: "RW", AG: "RW*", CO: "R*", AVP: "R", AN: "agg", AD: "R"},
    Obj.STRATEGIES:      {F: "RW", WK: "R", AG: "RW*", CO: "R*", AD: "R"},
    Obj.CANAL_CROP_PLAN: {F: "RW", WK: "R", AG: "RW*", CO: "R", AVP: "R", AN: "agg", AD: "R"},
    Obj.CANAL_SUPPLY:    {F: "R", WK: "R", AG: "R", CO: "R", AVP: "RW", AN: "agg", AD: "R"},
    Obj.CANAL_PROPOSAL:  {F: "R", WK: "R", AG: "R", CO: "R", AVP: "RW", AD: "R"},
    Obj.ROTATIONS:       {F: "R", WK: "R", AG: "RWA", CO: "R", AVP: "R", AN: "R", AD: "RW"},
    Obj.PRICES:          {F: "R", AG: "RW", CO: "RW", AN: "R", AD: "RWA"},
    Obj.DATA_SOURCES:    {F: "R", AG: "R", AN: "R", AD: "RWA"},
}

# Фермер может отвечать на предложение канала (согласие/отказ) — особый случай "R + согласие"
FARMER_CAN_RESPOND_TO_PROPOSAL = True


def allowed(role: Role, obj: Obj, action: str) -> bool:
    """action: "R" | "W" | "A". Для "*" нужна дополнительная проверка scope приглашения."""
    rights = MATRIX.get(obj, {}).get(role, "")
    if rights == "agg":
        return False  # агрегаты отдаются только через /analytics с k-анонимностью
    return action in rights.replace("*", "")


def needs_owner_grant(role: Role, obj: Obj) -> bool:
    return MATRIX.get(obj, {}).get(role, "").endswith("*")
