"""Прогон одного плана хозяйства через выборки: урожай → корма (М8) → деньги по месяцам (М9).

Вход — уже посчитанная вода по каждой части плана (М1–М6, модуль воды): множитель урожая и
брутто/дефицит по декадам для каждой выборки (исторического года NASA). Здесь на неё
навешиваются сбыт, корма и денежный поток. Чистая функция: без БД, сети и случайности —
шум цен приходит готовым массивом.

Оси массивов: S — выборки, 12 — месяцы года, 36 — декады.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

from agroshift_core.cashflow import cash_path, delay_payments, sell_with_channel
from agroshift_core.feed import FeedBalance, feed_balance

MONTHS = 12
DECADES = 36
DECADE_TO_MONTH = np.arange(DECADES) // 3


@dataclass(frozen=True)
class CropParams:
    """Экономика культуры. `price_som_t = None` — цена неизвестна (пропуск ≠ ноль)."""

    crop_id: str
    yield_t_ha: float
    price_som_t: float | None
    cost_som_ha_by_month: tuple[float, ...]
    harvest_shares: tuple[float, ...]  # доля урожая по месяцам, сумма = 1
    is_feed: bool = False
    dm_share: float = 1.0  # доля сухого вещества в убранной массе
    max_volume_t: float | None = None  # ёмкость канала сбыта; None — без ограничения
    distress_factor: float = 0.6  # цена срочной реализации относительно цены канала
    establish_yield_factor: float = 1.0  # урожай первого года новой посадки


@dataclass(frozen=True)
class PlanPart:
    """Культура на поле (или на части поля) + её вода по выборкам."""

    field_id: str
    crop_id: str
    area_ha: float
    yield_mult: np.ndarray  # (S,) Ya/Ym из модели воды
    gross_m3: np.ndarray  # (S, 36) потребность брутто на эту площадь
    deficit_m3: np.ndarray  # (S, 36) дефицит нетто на эту площадь
    new_planting: bool = False
    capex_som: float = 0.0  # разовые вложения (например, выкорчёвка)
    capex_month: int = 2


@dataclass(frozen=True)
class FarmEcon:
    """Деньги, скот и корма хозяйства; массивы — по 12 месяцам."""

    opening_cash_som: float
    reserve_som: float
    family_by_month: tuple[float, ...]
    debt_by_month: tuple[float, ...]
    milk_income_by_month: tuple[float, ...]
    herd_cost_by_month: tuple[float, ...]
    feed_demand_dm_kg: tuple[float, ...]
    feed_opening_stock_dm_kg: float
    feed_price_som_t: float
    feed_dm_share: float = 0.85
    water_fee_som_m3: float = 0.0
    payment_delay_days: float = 0.0


@dataclass(frozen=True)
class Conditions:
    """Экономическая часть сценария. Водная и климатическая уже учтены в PlanPart."""

    price_factor: float = 1.0  # все продукты, включая молоко
    price_factors: Mapping[str, float] = field(default_factory=dict)  # по культурам / "milk"
    feed_price_factor: float = 1.0
    payment_delay_days: float = 0.0  # дополнительная задержка оплаты
    yield_factor: float = 1.0

    def price_mult(self, key: str) -> float:
        return self.price_factor * self.price_factors.get(key, 1.0)


@dataclass(frozen=True)
class Noise:
    """Ценовой шум по выборкам (common random numbers)."""

    price: Mapping[str, np.ndarray]  # crop_id / "milk" -> (S,)
    feed: np.ndarray  # (S,)


@dataclass(frozen=True)
class PlanResult:
    cash: np.ndarray  # (S, 12) остаток на конец месяца
    income: np.ndarray  # (S,) чистый доход за год, до расходов семьи и долга
    flows: dict[str, np.ndarray]  # компоненты денежного потока, (S, 12)
    receivable: np.ndarray  # (S,) выручка, которая придёт уже после декабря
    gross_m3: np.ndarray  # (S, 36)
    deficit_m3: np.ndarray  # (S, 36)
    yield_loss: np.ndarray  # (число частей, S) доля потери урожая
    feed: FeedBalance
    unsold_t: dict[str, np.ndarray]  # crop_id -> (S,) объём без покупателя
    capex_som: float
    var_cost_som: float
    unknown_inputs: tuple[str, ...]

    @property
    def completeness(self) -> str:
        return "partial" if self.unknown_inputs else "full"


def evaluate_plan(
    parts: Sequence[PlanPart],
    crops: Mapping[str, CropParams],
    farm: FarmEcon,
    cond: Conditions,
    noise: Noise,
) -> PlanResult:
    n = int(noise.feed.shape[0])
    ones = np.ones(MONTHS)

    volume: dict[str, np.ndarray] = {}
    harvest_feed_dm = np.zeros((n, MONTHS))
    var_cost = np.zeros(MONTHS)
    capex = np.zeros(MONTHS)
    gross = np.zeros((n, DECADES))
    deficit = np.zeros((n, DECADES))
    yield_loss = np.zeros((len(parts), n))
    feed_sale_price: float | None = None
    unknown: list[str] = []

    for i, part in enumerate(parts):
        crop = crops[part.crop_id]
        mult = np.clip(part.yield_mult * cond.yield_factor, 0.0, None)
        yield_loss[i] = np.clip(1.0 - mult, 0.0, 1.0)
        establish = crop.establish_yield_factor if part.new_planting else 1.0
        harvest_t = part.area_ha * crop.yield_t_ha * establish * mult
        by_month = harvest_t[:, None] * np.asarray(crop.harvest_shares)[None, :]
        if crop.is_feed:
            harvest_feed_dm += by_month * 1000.0 * crop.dm_share
            if crop.price_som_t is not None:
                feed_sale_price = crop.price_som_t / (1000.0 * crop.dm_share)
        else:
            volume[crop.crop_id] = volume.get(crop.crop_id, 0.0) + by_month
        var_cost += part.area_ha * np.asarray(crop.cost_som_ha_by_month)
        capex[part.capex_month] += part.capex_som
        gross += part.gross_m3
        deficit += part.deficit_m3

    # --- Продажа урожая: цена месяца × объём, с ёмкостью канала сбыта ---
    shipped = np.zeros((n, MONTHS))
    unsold: dict[str, np.ndarray] = {}
    for crop_id, vol in volume.items():
        crop = crops[crop_id]
        if crop.price_som_t is None:
            unknown.append(f"price:{crop_id}")
            continue
        price = crop.price_som_t * cond.price_mult(crop_id) * noise.price[crop_id]
        total = vol.sum(axis=1)
        revenue, no_buyer = sell_with_channel(total, price, crop.max_volume_t, crop.distress_factor)
        share = np.divide(vol, total[:, None], out=np.zeros_like(vol), where=total[:, None] > 0)
        shipped += share * revenue[:, None]
        if crop.max_volume_t is not None:
            unsold[crop_id] = no_buyer
    received, receivable = delay_payments(
        shipped, farm.payment_delay_days + cond.payment_delay_days
    )

    # --- Корма: свой корм идёт скоту, недостача покупается, излишек продаётся ---
    balance = feed_balance(
        np.asarray(farm.feed_demand_dm_kg), harvest_feed_dm, farm.feed_opening_stock_dm_kg
    )
    buy_price = (
        farm.feed_price_som_t / (1000.0 * farm.feed_dm_share) * cond.feed_price_factor * noise.feed
    )
    feed_cost = balance.purchased_dm_kg * buy_price[:, None]
    if feed_sale_price is None:
        feed_sales = np.zeros((n, MONTHS))
        if balance.sold_dm_kg.any():
            unknown.append("price:feed_surplus")
    else:
        feed_sales = balance.sold_dm_kg * feed_sale_price * cond.price_factor

    milk = (
        np.asarray(farm.milk_income_by_month)[None, :]
        * cond.price_mult("milk")
        * noise.price["milk"][:, None]
    )
    water_fee = np.zeros((n, MONTHS))
    if farm.water_fee_som_m3:
        np.add.at(water_fee, (slice(None), DECADE_TO_MONTH), gross * farm.water_fee_som_m3)

    flows = {
        "crop_revenue": received,
        "feed_sales": feed_sales,
        "milk": milk,
        "var_cost": np.broadcast_to(var_cost, (n, MONTHS)),
        "water_fee": water_fee,
        "feed_purchase": feed_cost,
        "herd_cost": np.broadcast_to(np.asarray(farm.herd_cost_by_month), (n, MONTHS)),
        "capex": np.broadcast_to(capex, (n, MONTHS)),
        "debt": np.broadcast_to(np.asarray(farm.debt_by_month) * ones, (n, MONTHS)),
        "family": np.broadcast_to(np.asarray(farm.family_by_month) * ones, (n, MONTHS)),
    }
    inflow = flows["crop_revenue"] + flows["feed_sales"] + flows["milk"]
    operating = (
        flows["var_cost"] + flows["water_fee"] + flows["feed_purchase"] + flows["herd_cost"]
        + flows["capex"]
    )
    cash = cash_path(farm.opening_cash_som, inflow, operating + flows["debt"] + flows["family"])
    # доход — по отгрузке: задержка оплаты бьёт по остатку денег, а не по доходу года
    income = shipped.sum(axis=1) + (feed_sales + milk - operating).sum(axis=1)

    return PlanResult(
        cash=cash,
        income=income,
        flows=flows,
        receivable=receivable,
        gross_m3=gross,
        deficit_m3=deficit,
        yield_loss=yield_loss,
        feed=balance,
        unsold_t=unsold,
        capex_som=float(capex.sum()),
        var_cost_som=float(var_cost.sum()),
        unknown_inputs=tuple(unknown),
    )
