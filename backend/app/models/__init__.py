"""Все ORM-модели (раздел 7.1 ТЗ). Импорт здесь нужен Alembic для autogenerate."""

from app.models.audit import AuditLog, ChatMessage, ChatSession
from app.models.catalog import (
    CostNorm,
    Crop,
    CropVariant,
    Investment,
    PriceItem,
    RotationTemplate,
)
from app.models.farm import (
    CashAccount,
    CropSeason,
    Equipment,
    Farm,
    Field,
    Goal,
    Herd,
    Obligation,
    Orchard,
    PlanFact,
    WaterEvent,
)
from app.models.identity import Membership, User, Workspace
from app.models.modeling import (
    Breakpoint,
    ClimateDaily,
    DataSnapshot,
    ModelVersion,
    Run,
    RunMetric,
    Scenario,
    Strategy,
)
from app.models.water import (
    Canal,
    CanalPlan,
    CanalProposal,
    SupplySchedule,
    WaterRight,
    canal_plan_members,
)

__all__ = [
    "AuditLog", "Breakpoint", "Canal", "CanalPlan", "CanalProposal", "CashAccount",
    "ChatMessage", "ChatSession", "ClimateDaily", "CostNorm", "Crop", "CropSeason",
    "CropVariant", "DataSnapshot", "Equipment", "Farm", "Field", "Goal", "Herd", "Investment",
    "Membership", "ModelVersion", "Obligation", "Orchard", "PlanFact", "PriceItem",
    "RotationTemplate", "Run", "RunMetric", "Scenario", "Strategy", "SupplySchedule", "User",
    "WaterEvent", "WaterRight", "Workspace", "canal_plan_members",
]
