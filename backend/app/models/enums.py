"""Перечисления предметной области (разделы 4, 6.3, 7.1 ТЗ)."""

from enum import StrEnum


class SourceType(StrEnum):
    """Статус входа — раздел 3.5 и 6.3. Пропуск != ноль: неизвестное — это UNKNOWN, не 0."""

    MEASURED = "measured"
    SATELLITE = "satellite"
    MODEL = "model"
    REFERENCE = "reference"
    USER_ESTIMATE = "user_estimate"
    UNKNOWN = "unknown"


class WorkspaceType(StrEnum):
    FARM = "farm"
    COOP = "coop"
    CANAL = "canal"
    ORG = "org"


class Role(StrEnum):
    FARMER = "farmer"
    WORKER = "worker"
    AGRONOMIST = "agronomist"
    COOP = "coop"
    AVP = "avp"
    ANALYST = "analyst"
    ADMIN = "admin"


class AccessScope(StrEnum):
    """Объём доступа агронома по приглашению — раздел 4.4."""

    FIELDS = "fields"
    FIELDS_STRATEGIES = "fields_strategies"
    ALL = "all"


class IrrigationMethod(StrEnum):
    FURROW = "furrow"          # бороздковый
    FLOOD = "flood"            # напуск
    SPRINKLER = "sprinkler"    # дождевание
    DRIP = "drip"              # капельный
    NONE = "none"              # богара


class Species(StrEnum):
    COW = "cow"
    SHEEP = "sheep"
    GOAT = "goat"
    HORSE = "horse"


class HerdPurpose(StrEnum):
    MILK = "milk"
    MEAT = "meat"


class Ownership(StrEnum):
    OWN = "own"
    RENT = "rent"
    COOP = "coop"


class Rootstock(StrEnum):
    SEEDLING = "seedling"        # семенной
    SEMI_DWARF = "semi_dwarf"    # полукарликовый
    DWARF = "dwarf"              # карликовый


class MaturityClass(StrEnum):
    EARLY = "early"
    MID = "mid"
    LATE = "late"


class RotationStatus(StrEnum):
    APPROVED = "approved"
    EXPERIMENTAL = "experimental"


class PriceItemKind(StrEnum):
    CROP = "crop"
    FEED = "feed"
    INPUT = "input"
    SERVICE = "service"


class InvestmentType(StrEnum):
    DRIP = "drip"
    SPRINKLER = "sprinkler"
    UPROOTING = "uprooting"
    PLANTING = "planting"
    STORAGE = "storage"
    ANIMALS = "animals"


class ObligationType(StrEnum):
    LOAN = "loan"
    CONTRACT_SUPPLY = "contract_supply"
    FEED_PURCHASE = "feed_purchase"


class StrategyType(StrEnum):
    INCOME = "income"            # Больше дохода
    RESILIENT = "resilient"      # Пережить плохой год
    WATER_LIGHT = "water_light"  # Меньше зависимости от воды
    GRADUAL = "gradual"          # Развиваться постепенно
    USER = "user"                # Мой вариант


class ClimateMode(StrEnum):
    HISTORICAL_YEAR = "historical_year"
    PERCENTILE = "percentile"
    CMIP6 = "cmip6"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Completeness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


class MetricPeriod(StrEnum):
    DECADE = "decade"
    MONTH = "month"
    SEASON = "season"
    YEAR = "year"


class CanalPlanStatus(StrEnum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    AGREED = "agreed"
    REJECTED = "rejected"


class ProposalResponse(StrEnum):
    PENDING = "pending"
    AGREE = "agree"
    REJECT = "reject"
    COUNTER = "counter"
