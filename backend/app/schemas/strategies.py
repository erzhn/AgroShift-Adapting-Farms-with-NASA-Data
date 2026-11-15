"""Схемы модуля «Стратегии и деньги» (М8, М9, М11–М13).

Единицы: деньги — целые сомы, вода — м³, декады — индекс 1–36, месяцы — 1–12.
"""

from typing import Literal

from pydantic import BaseModel, Field

StrategyType = Literal["income", "resilient", "water_light", "user"]


class Percentiles(BaseModel):
    p10: int
    p50: int
    p90: int


class ScenarioIn(BaseModel):
    """Сценарий условий — ползунки UC-3. Значения по умолчанию = базовые условия."""

    water_supply_factor: float = Field(1.0, ge=0.5, le=1.2, description="Подача воды, 0.8 = −20%")
    supply_shift_days: float = Field(0, ge=-30, le=30, description="Сдвиг подачи, + позже")
    temp_delta_c: float = Field(0, ge=0, le=3)
    precip_factor: float = Field(1.0, ge=0.5, le=1.3)
    water_months: list[int] = Field(
        default_factory=list, description="Месяцы 1–12, к которым относится множитель подачи; "
        "пусто — весь сезон"
    )
    price_factor: float = Field(1.0, ge=0.5, le=1.5, description="Цена всей продукции")
    price_factors: dict[str, float] = Field(
        default_factory=dict, description="Цена отдельной культуры (crop_id) или 'milk'"
    )
    feed_price_factor: float = Field(1.0, ge=0.5, le=1.5)
    payment_delay_days: float = Field(0, ge=0, le=120, description="Дополнительная задержка оплаты")
    yield_factor: float = Field(1.0, ge=0.7, le=1.3)


class GenerateRequest(BaseModel):
    scenario: ScenarioIn = Field(default_factory=ScenarioIn)
    seed: int = 42


class Decision(BaseModel):
    field_id: str
    field_name: str
    crop_id: str
    crop_name_ru: str
    crop_name_en: str
    area_ha: float
    action: Literal["keep", "switch", "uproot_and_sow"]
    capex_som: int = 0


class WorstDecade(BaseModel):
    decade: int = Field(description="1–36")
    deficit_m3: int
    field_id: str | None = None
    field_name: str | None = None


class Unsold(BaseModel):
    crop_id: str
    tonnes: float
    max_volume_t: float


class CashGapOut(BaseModel):
    """Кассовый разрыв по медианной траектории + вероятность по выборкам."""

    first_month: int | None = Field(description="1–12; null — разрыва нет")
    worst_month: int | None
    depth_som: int = Field(description="min(Cash − резерв); < 0 при разрыве")
    financing_needed_som: int
    probability: float = Field(description="Доля выборок с разрывом")


class StrategyMetrics(BaseModel):
    income_som: Percentiles
    cvar10_som: int
    gross_water_m3: Percentiles
    peak_water_m3: int = Field(description="Среднее брутто в пиковые декады")
    worst_decade: WorstDecade | None
    cash_gap: CashGapOut
    investment_som: int
    feed_self_sufficiency: float = Field(description="0–1, медиана")
    feed_purchase_som: int = Field(description="Покупка корма за год, медиана")
    max_yield_loss: float = Field(description="Худшая медианная потеря урожая по полям, 0–1")
    unsold: list[Unsold] = []
    win_share: float | None = Field(None, description="Доля выборок, где стратегия лучшая")


class FinancingOut(BaseModel):
    """Стратегия держит резерв только с привлечёнными деньгами (пример 15.3)."""

    amount_som: int = Field(description="Сколько привлечь, сом; считается по плохим годам")
    month: int | None = Field(description="1–12: к какому месяцу нужны деньги")
    p_gap_limit: float = Field(description="С этой суммой разрыв не чаще этой доли лет")


class StrategyOut(BaseModel):
    id: str
    run_id: str
    farm_id: str
    types: list[StrategyType] = Field(description="Несколько — стратегии совпали (8.11)")
    decisions: list[Decision]
    summary_ru: str
    summary_en: str
    metrics: StrategyMetrics
    flags: list[str] = Field(
        description="cash_gap_risk, depends_on_conditions, experimental, incomplete, "
        "needs_financing, no_buyer, rotation_violation"
    )
    financing: FinancingOut | None = Field(
        None, description="Ни одна схема не держит резерв: эта — лучшая по цели, но с кредитом"
    )
    agro_status: Literal["approved", "experimental"]
    completeness: Literal["full", "partial"]
    unknown_inputs: list[str] = []


class ExcludedStrategy(BaseModel):
    """Стратегия не построена: какое ограничение её исключило (UC-2, шаг 5)."""

    type: StrategyType
    constraint: str
    p_gap_limit: float
    best_p_gap: float
    financing_needed_som: int = Field(description="Сколько привлечь лучшей схеме (по плохим годам)")


class Provenance(BaseModel):
    model_version: str
    seed: int
    n_samples: int
    years: list[int]
    inputs_status: dict[str, str] = Field(
        description="farm/water: 'service' — данные владельца модуля, 'stub' — встроенная "
        "заглушка (не данные NASA)"
    )
    warnings: list[str] = []


class GenerateResponse(BaseModel):
    generation_id: str
    farm_id: str
    farm_name: str
    scenario: ScenarioIn
    schemes_checked: int
    schemes_truncated: bool
    peak_decades: list[int]
    strategies: list[StrategyOut]
    excluded: list[ExcludedStrategy]
    provenance: Provenance
    result_hash: str


class CashflowMonth(BaseModel):
    month: int
    cash: Percentiles
    components: dict[str, int] = Field(description="Средние по выборкам; расходы — со знаком −")


class CashflowResponse(BaseModel):
    run_id: str
    strategy_id: str
    opening_cash_som: int
    reserve_som: int
    months: list[CashflowMonth]
    gap: CashGapOut
    receivable_som: int = Field(description="Выручка, которая придёт после декабря (медиана)")
    completeness: Literal["full", "partial"]
    unknown_inputs: list[str] = []
    provenance: Provenance


class StressRequest(ScenarioIn):
    with_fix: bool = Field(True, description="Подобрать исправленный план (C)")


class FieldLoss(BaseModel):
    field_id: str
    field_name: str
    crop_id: str
    yield_loss: float = Field(description="Медианная потеря урожая, 0–1")


class PlanOutcome(BaseModel):
    income_som: Percentiles
    cash_p10: list[int]
    cash_p50: list[int]
    cash_gap: CashGapOut
    gross_water_m3: int
    worst_decade: WorstDecade | None
    field_losses: list[FieldLoss]
    feed_purchase_t: float
    feed_purchase_som: int
    unsold: list[Unsold] = []
    decisions: list[Decision]


class StressAnswers(BaseModel):
    """Пять ответов UC-3 для исходного плана в новых условиях."""

    water_decade: WorstDecade | None
    vulnerable_field: FieldLoss | None
    cash_gap: CashGapOut
    feed_extra_purchase_som: int = Field(description="Насколько выросла покупка корма против базы")
    unsold: list[Unsold]
    fix_summary_ru: str
    fix_summary_en: str


class StressResponse(BaseModel):
    run_id: str
    scenario: ScenarioIn
    baseline: PlanOutcome = Field(description="A — исходный план, базовые условия")
    stressed: PlanOutcome = Field(description="B — исходный план, новые условия")
    fixed: PlanOutcome | None = Field(description="C — исправленный план, новые условия")
    fixed_financing: FinancingOut | None = Field(
        None,
        description="Смены культур мало: сколько привлечь плану C (или B, если C нет), "
        "чтобы разрыв был не чаще 10% лет",
    )
    fix_needed: bool
    fix_found: bool
    damage_som: int = Field(description="A − B по медиане дохода")
    adaptation_gain_som: int = Field(description="C − B")
    change_cost_som: int = Field(description="Capex_C + ΔVarCost")
    answers: StressAnswers
    elapsed_ms: int
    reserve_som: int
    provenance: Provenance


class HistoricalFrequency(BaseModel):
    count: int
    of: int


class BreakpointOut(BaseModel):
    factor: str = Field(description="water_supply_factor, temp_delta_c, price, feed_price_factor…")
    subject: str | None = Field(None, description="crop_id или 'milk' для фактора price")
    subject_name_ru: str | None = None
    subject_name_en: str | None = None
    unit: Literal["percent", "days", "celsius"]
    base_value: float
    threshold_value: float
    delta: float = Field(description="Отклонение от базы: в % для percent, иначе в единицах")
    violated_constraint: Literal["cash_gap", "yield_loss"]
    month: int | None = None
    field_id: str | None = None
    field_name: str | None = None
    already_broken: bool = False
    historical_frequency: HistoricalFrequency | None = Field(
        None, description="В скольких годах из истории условия были не лучше порога"
    )
    safety_margin_sigma: float | None = None


class BaseViolation(BaseModel):
    """План нарушает ограничение уже в базовых условиях."""

    violated_constraint: Literal["cash_gap", "yield_loss"]
    month: int | None = None
    field_id: str | None = None
    field_name: str | None = None


class BreakpointsResponse(BaseModel):
    run_id: str
    base_violation: BaseViolation | None = None
    breakpoints: list[BreakpointOut] = Field(description="Сначала самые близкие к поломке")
    holds: list[str] = Field(description="Факторы, по которым план не ломается в диапазоне")
    yield_loss_limit: float
    provenance: Provenance


class RunSummary(BaseModel):
    """Сводка прогона для ИИ-помощника: только числа ядра (get_run_summary)."""

    run_id: str
    strategy_id: str
    farm_id: str
    types: list[StrategyType]
    summary_ru: str
    summary_en: str
    decisions: list[Decision]
    metrics: StrategyMetrics
    flags: list[str]
    breakpoints: list[BreakpointOut] | None = Field(
        None, description="Заполнено, если точки поломки уже считались"
    )
    provenance: Provenance
