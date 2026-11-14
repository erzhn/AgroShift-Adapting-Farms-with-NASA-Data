"""М4–М6: эталонные примеры 15.1 и 15.2 ТЗ, сходимость баланса, свойства."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agroshift_core import irrigation as m5
from agroshift_core import water_balance as m4
from agroshift_core import yield_model as m6

# ------------------------------------------------- пример 15.1: декада кукурузы в июле
# Поле 2 га, Kc_mid = 1,20, 11 дней, ET0 = 6,5 мм/сут, дождь 4 мм на 3-й день (сток 0).
# TAW = 1000·0,14·1,2 = 168 мм, p = 0,55 -> RAW = 92,4 мм. Начальное Dr = 60 мм.
# Очередь на 5-й день, расход 60 л/с, η_field = 0,55, Ky стадии = 1,5.

AREA_HA, FLOW_L_S, ETA_FIELD, KY = 2.0, 60.0, 0.55, 1.5
TAW = float(m4.total_available_water(140.0, 1.2))
ETC = np.full(11, 1.20 * 6.5)
RAIN = np.zeros(11)
RAIN[2] = 4.0


@pytest.mark.parametrize(
    ("hours", "volume_m3", "i_net", "eta_sum", "ratio", "dr_end", "multiplier"),
    [
        (8.0, 1728.0, 47.5, 85.8, 1.000, 94.3, 1.000),   # полная очередь
        (4.0, 864.0, 23.8, 82.8, 0.966, 115.1, 0.948),   # сокращённая
        (0.0, 0.0, 0.0, 74.0, 0.863, 130.0, 0.794),      # очередь сорвана
    ],
)
def test_example_15_1(hours, volume_m3, i_net, eta_sum, ratio, dr_end, multiplier):
    assert TAW == pytest.approx(168.0)
    volume = m5.turn_volume_m3(hours, FLOW_L_S)
    assert volume == pytest.approx(volume_m3)
    net = float(m5.net_irrigation_mm(volume, ETA_FIELD, AREA_HA))
    assert net == pytest.approx(i_net, abs=0.05)

    irrigation = np.zeros(11)
    irrigation[4] = net                                    # 5-й день
    result = m4.simulate_root_zone(ETC, RAIN, TAW, 0.55, 60.0, irrigation_net=irrigation)

    assert float(ETC.sum()) == pytest.approx(85.8)
    assert float(result.raw[0]) == pytest.approx(92.4)
    assert float(result.eta.sum()) == pytest.approx(eta_sum, abs=0.1)
    assert float(result.eta.sum() / ETC.sum()) == pytest.approx(ratio, abs=0.001)
    assert float(result.dr[-1]) == pytest.approx(dr_end, abs=0.1)
    assert m6.stage_factor(result.eta.sum(), ETC.sum(), KY) == pytest.approx(multiplier,
                                                                             abs=0.001)
    assert abs(result.closure_error(RAIN)) < 1e-9


def test_example_15_1_full_turn_still_ends_above_raw():
    """Вывод примера: даже при полной очереди декада кончается с Dr > RAW —
    следующая декада начнётся со стресса. Система обязана это показать."""
    irrigation = np.zeros(11)
    irrigation[4] = float(m5.net_irrigation_mm(m5.turn_volume_m3(8, FLOW_L_S), ETA_FIELD,
                                               AREA_HA))
    result = m4.simulate_root_zone(ETC, RAIN, TAW, 0.55, 60.0, irrigation_net=irrigation)
    assert result.dr[-1] > result.raw[-1]
    assert (result.ks == 1.0).all()


# ------------------------------------------------- пример 15.2: нетто и брутто


def test_example_15_2_net_vs_gross():
    need_net_mm = 300.0
    area_ha = 1.0
    allotted_m3 = 3000.0                                   # 300 мм на водовыпуске
    net = float(m5.net_irrigation_mm(allotted_m3, 0.5, area_ha))
    assert net == pytest.approx(150.0)                     # до корней доходит половина
    assert need_net_mm - net == pytest.approx(150.0)       # дефицит 150 мм, а не 0
    assert (need_net_mm - net) / need_net_mm == pytest.approx(0.5)

    # тот же лимит, но на голове канала при η_conv = 0,35
    at_farm = float(m5.farm_volume_from_head(allotted_m3, 0.35))
    assert float(m5.net_irrigation_mm(at_farm, 0.5, area_ha)) == pytest.approx(52.5)


def test_gross_net_roundtrip_and_head():
    gross = float(m5.gross_volume_m3(47.52, 0.55, 2.0))
    assert gross == pytest.approx(1728.0)
    assert float(m5.net_irrigation_mm(gross, 0.55, 2.0)) == pytest.approx(47.52)
    assert float(m5.head_volume_from_farm(1728.0, 0.5)) == pytest.approx(3456.0)


def test_default_field_efficiency_ranges():
    assert m5.field_efficiency_range("furrow") == (0.45, 0.60)
    assert m5.field_efficiency_range("sprinkler") == (0.70, 0.80)
    assert m5.field_efficiency_range("drip") == (0.85, 0.95)
    assert m5.default_field_efficiency("drip") > m5.default_field_efficiency("furrow")


def test_failed_turns_are_reproducible():
    a = m5.failed_turns(40, 0.5, seed=42, year=2023)
    b = m5.failed_turns(40, 0.5, seed=42, year=2023)
    assert (a == b).all()                                  # тот же seed и год — те же срывы
    assert (a != m5.failed_turns(40, 0.5, seed=42, year=2024)).any()
    assert not m5.failed_turns(40, 1.0, 42, 2023).any()    # надёжность 1 — без срывов
    assert m5.failed_turns(40, 0.0, 42, 2023).all()


# ------------------------------------------------- сходимость и свойства баланса


def _season(seed=1, n=120):
    rng = np.random.default_rng(seed)
    etc = rng.uniform(1.0, 9.0, n)
    rain = np.where(rng.random(n) < 0.15, rng.uniform(1.0, 40.0, n), 0.0)
    taw = np.concatenate([np.full(20, 21.0), np.linspace(21.0, 168.0, 40), np.full(60, 168.0)])
    return etc, rain, taw


def test_water_balance_closes():
    """Приёмка ТЗ: P + I − ETa − RO − DP − Δзапаса = 0 ± 0,5 мм за сезон."""
    etc, rain, taw = _season()
    runoff = m4.scs_runoff(rain, 78.0)
    available = np.zeros(etc.size)
    available[::8] = 45.0
    result = m4.simulate_root_zone(etc, rain, taw, 0.55, 0.5 * taw[0], runoff=runoff,
                                   irrigation_available=available, new_soil_depletion=0.5)
    assert abs(result.closure_error(rain)) < 0.5
    assert abs(result.closure_error(rain)) < 1e-6
    assert (result.dr >= 0).all() and (result.dr <= result.taw + 1e-9).all()
    assert (result.irrigation <= available + 1e-12).all()


def test_sufficient_water_means_no_stress_and_full_yield():
    """Вариант с достаточной водой: Ks = 1 всегда, Ya/Ym = 1."""
    etc, rain, taw = _season()
    available = np.full(etc.size, 1000.0)                  # воды сколько угодно каждый день
    result = m4.simulate_root_zone(etc, rain, taw, 0.55, 0.0, irrigation_available=available)
    assert (result.ks == 1.0).all()
    assert float(result.eta.sum()) == pytest.approx(float(etc.sum()))
    stage = np.repeat(np.arange(4), 30)
    f_water, _ = m6.water_factor_by_stage(result.eta, etc, stage, (0.4, 0.4, 1.5, 0.5))
    assert f_water == pytest.approx(1.0)
    assert m6.relative_yield(f_water) == pytest.approx(1.0)


def test_irrigation_never_overfills_the_soil():
    etc, rain, taw = _season()
    available = np.full(etc.size, 500.0)
    result = m4.simulate_root_zone(etc, np.zeros_like(rain), taw, 0.55, 10.0,
                                   irrigation_available=available)
    assert float(result.dp.sum()) == pytest.approx(0.0)    # полив только до Dr = 0


def test_scs_runoff():
    assert float(m4.scs_runoff(10.0, 78.0)) == 0.0         # P <= 0,2·S — стока нет
    s = 25400 / 78 - 254
    assert float(m4.scs_runoff(50.0, 78.0)) == pytest.approx((50 - 0.2 * s) ** 2
                                                             / (50 + 0.8 * s))
    assert m4.curve_number("loam", 10.0) > m4.curve_number("loam", 1.0)
    assert m4.curve_number(None) == m4.CURVE_NUMBER_DEFAULT


def test_supply_shifted_after_flowering_lowers_yield():
    """Сроки подачи: та же сезонная сумма, но после цветения — урожай ниже."""
    lengths = (20, 30, 40, 30)
    stage = np.repeat(np.arange(4), lengths)
    etc = np.repeat([2.0, 5.0, 8.0, 5.0], lengths).astype(float)
    rain = np.zeros(etc.size)
    ky = (0.4, 0.4, 1.5, 0.5)

    on_time = np.zeros(etc.size)
    on_time[[50, 60, 70, 80]] = 60.0                       # в середину сезона (цветение)
    late = np.zeros(etc.size)
    late[[95, 100, 105, 110]] = 60.0                       # та же вода, но в конце
    assert on_time.sum() == late.sum()

    def relative_yield(irrigation):
        result = m4.simulate_root_zone(etc, rain, 168.0, 0.55, 30.0,
                                       irrigation_net=irrigation)
        return m6.water_factor_by_stage(result.eta, etc, stage, ky)[0]

    assert relative_yield(late) < relative_yield(on_time)


@settings(max_examples=300, deadline=None)
@given(seed=st.integers(0, 1_000_000), cut=st.floats(0.0, 1.0),
       taw_max=st.floats(60.0, 260.0), dr0_share=st.floats(0.0, 1.0))
def test_less_water_never_raises_yield(seed, cut, taw_max, dr0_share):
    """Монотонность (приёмка ТЗ): уменьшение подачи не увеличивает урожай.

    Входы нарочно жёсткие: корневая зона растёт с 1/8 глубины, потребность до 11 мм/сут
    (больше зоны стресса мелких корней), дожди со стоком, случайные очереди.
    """
    rng = np.random.default_rng(seed)
    n = 120
    etc = rng.uniform(0.5, 11.0, n)
    rain = np.where(rng.random(n) < 0.12, rng.uniform(1.0, 40.0, n), 0.0)
    available = np.zeros(n)
    step = int(rng.integers(5, 12))
    available[::step] = rng.uniform(5.0, 120.0, n)[::step]
    taw = np.concatenate([np.full(20, taw_max / 8), np.linspace(taw_max / 8, taw_max, 40),
                          np.full(60, taw_max)])
    runoff = m4.scs_runoff(rain, 78.0)
    stage = np.repeat(np.arange(4), 30)
    ky = (0.4, 0.4, 1.5, 0.5)

    def run(avail):
        result = m4.simulate_root_zone(etc, rain, taw, 0.55, dr0_share * taw[0],
                                       runoff=runoff, irrigation_available=avail,
                                       new_soil_depletion=dr0_share)
        return m6.water_factor_by_stage(result.eta, etc, stage, ky)[0], result

    full, full_result = run(available)
    less, less_result = run(available * cut)
    assert less <= full + 1e-9
    # механизм монотонности: при меньшей подаче почва не влажнее ни в один день,
    # значит и испарение культуры не больше ни в один день
    assert (less_result.dr >= full_result.dr - 1e-9).all()
    assert (less_result.eta <= full_result.eta + 1e-9).all()
    for result in (full_result, less_result):
        assert abs(result.closure_error(rain)) < 1e-6          # баланс сходится всегда
        assert (result.dr >= -1e-9).all() and (result.dr <= result.taw + 1e-9).all()
        assert (result.eta >= 0).all() and (result.eta <= etc + 1e-9).all()


def test_shallow_roots_with_high_demand_keep_the_balance_closed():
    """Зона стресса тоньше суточной потребности: культура берёт только то, что осталось,
    истощение не уходит за TAW и вода не «теряется»."""
    etc = np.full(10, 9.0)
    rain = np.zeros(10)
    rain[4] = 6.0
    result = m4.simulate_root_zone(etc, rain, 10.0, 0.55, 2.0)   # TAW − RAW = 4,5 < ETc
    assert float(result.eta[0]) == pytest.approx(8.0)            # взято всё, что было: 10 − 2
    assert float(result.dr[0]) == pytest.approx(10.0)
    assert float(result.eta[4]) == pytest.approx(6.0)            # только дождь этого дня
    assert (result.dr <= 10.0 + 1e-12).all()
    assert abs(result.closure_error(rain)) < 1e-9


# ------------------------------------------------- М6


def test_yield_factors():
    assert m6.stage_factor(74.0, 85.8, 1.5) == pytest.approx(0.794, abs=0.001)
    assert m6.stage_factor(0.0, 0.0, 1.5) == 1.0           # стадии нет — потери нет
    assert m6.stage_factor(0.0, 100.0, 1.5) == 0.0         # не ниже нуля
    assert m6.heat_factor(5, 0.02) == pytest.approx(0.9)
    assert m6.heat_factor(5, None) == 1.0
    assert m6.frost_factor(2, 0.25) == pytest.approx(0.5)
    assert m6.relative_yield(0.8, 0.9, 0.5) == pytest.approx(0.36)
    assert m6.round_yield(7.4499) == 7.4                   # не точнее 0,1 т/га
    assert m6.round_yield(None) is None
