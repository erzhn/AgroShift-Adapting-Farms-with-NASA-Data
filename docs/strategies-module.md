# Модуль «Стратегии и деньги» (Абдулазис)

М8 корма, М9 деньги по месяцам, М11 перебор схем, М12 стресс-тест, М13 точка поломки.

## Где что лежит

| Что | Где |
|---|---|
| Формулы (чистые функции) | `backend/agroshift_core/`: `cashflow.py`, `feed.py`, `plan_eval.py`, `optimizer.py`, `stress.py`, `breakpoints.py`, `uncertainty.py` |
| Сборка входов, хранение прогонов | `backend/app/services/strategies.py` |
| Связь с чужими модулями + заглушка | `backend/app/services/strategy_inputs.py` |
| Схемы ответов | `backend/app/schemas/strategies.py` |
| Тесты | `backend/tests/core/`, `backend/tests/test_strategies_api.py` |
| Экран | `frontend/app/strategies/`, `frontend/components/strategies/`, `frontend/lib/api/strategies.ts` |

## API (`/api/v1`)

| Метод | Что делает |
|---|---|
| `POST /farms/{id}/strategies:generate` | Перебор схем, до четырёх стратегий. Синхронно; те же входы → те же id |
| `GET /strategies/{id}` | Стратегия с метриками |
| `GET /runs/{id}/cashflow` | Остаток по месяцам P10/P50/P90, резерв, кассовый разрыв |
| `POST /runs/{id}/stress` | Тело — ползунки UC-3. Ответ: A, B, C, пять ответов, цена адаптации |
| `GET /runs/{id}/breakpoints` | Точки поломки с «было в N из 30 лет» |

Для ИИ-помощника: `app.services.strategies.get_run_summary(run_id) -> RunSummary`.

## Что модуль ждёт от других

Функции ищутся в `app.services.farms` / `app.services.water` (или `app.modules.<...>.service`).
Пока их нет или они падают, расчёт идёт на встроенной заглушке — демо-хозяйство «Асан» и
синтетические 30 лет. Ответы помечают это в `provenance.inputs_status` (`stub` / `service`),
экран показывает жёлтую плашку. **Заглушка — не данные NASA.**

**`get_farm(farm_id)`** — читаются поля (любое из имён):

- `name`; `fields[]`: `id`, `name`, `area_ha`, `crop_id` (текущая культура);
- `cash_som`, `family_reserve_som`, `family_expense_by_month` (12 чисел или одно),
  `debt_by_month`, `payment_delay_days`, `feed_price_som_t`, `water_fee_som_m3`;
- `herd` или `herds[]`: `head_count`, `dmi_kg_day`; `milk_income_by_month`, `herd_cost_by_month`.

Чего нет — берётся демо-оценка, а в `provenance.warnings` появляется строка об этом.

**`get_crop(crop_id)`**: `id`, `name_ru`, `name_en`, `yield_t_ha`, `price_som_t`
(`null` → расчёт помечается неполным, выручка не подставляется нулём),
`cost_som_ha_by_month` или `cost_som_ha`, `harvest_shares` (12 долей), `is_feed`, `dm_share`,
`max_volume_t` (ёмкость канала сбыта), `perennial`, `repeat_allowed`, `plantable`,
`uproot_cost_som_ha`, `sowing_date`, `agro_status`.

**`simulate_field(field, crop, sowing_date, scenario, year)`** — в `scenario` приходит объект
с полями `water_supply_factor`, `supply_shift_days`, `temp_delta_c`, `precip_factor`,
`water_months`. Из ответа читаются `yield_multiplier` и `decades[]`: `decade` (1–36),
`gross_mm` (потребность брутто) или `gross_m3`, `deficit_mm` или `deficit_m3`.

**`history_years()`** — список лет; каждый год = одна выборка.

Для частоты «было в N из 30 лет» по температуре и осадкам нужны аномалии по годам — в
контрактах их нет, поэтому с настоящей моделью воды частота считается только для подачи воды.

## Упрощения (раздел 14.1 ТЗ)

- Горизонт — один год; сад: оставить или выкорчевать 1 га.
- Выборки — исторические годы + шум цен (σ = 0,15; молоко 0,05), seed фиксирован.
- Исправленный план в стресс-тесте — лучшая схема, отличающаяся не более чем двумя полями.
- Прогоны хранятся в `backend/data/runs/*.json` (в git не попадают), не в БД.

## Лента денег на главном экране

```tsx
import MoneyLane from "../components/strategies/MoneyLane";

<MoneyLane farmId={farm.id} month={month} onMonthChange={setMonth} compact />
```

Показывает стратегию, выбранную на экране «Варианты будущего», иначе — «Мой вариант».
Нужен пакет `echarts`.
