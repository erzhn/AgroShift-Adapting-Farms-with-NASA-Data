# Модуль «Вода и климат» (владелец — Ислам)

Загрузка NASA POWER, расчёт М1–М6 (ET0 → ETc → суточный баланс → очередь полива → урожай),
три эндпоинта и два внутренних контракта для модулей стратегий и канала.

## API (`/api/v1`)

| Метод | Что отдаёт |
|---|---|
| `GET /fields/{id}/climate?from&to` | суточный климат поля из снимка NASA + ET0, нормы по декадам P10/P50/P90, заморозки, ячейка сетки |
| `GET /fields/{id}/water-balance?strategy&scenario&year&daily` | `season` — вода по декадам и урожай в выбранном году; `ensemble` — то же на 30 годах NASA |
| `GET /data-sources?lang` | наборы NASA, снимки (дата, sha256), атрибуция, ограничения разрешения |

`year` не задан → «типичный год» (медианный по урожаю). `daily=true` → суточные ряды истощения почвы.
`{id}` — id поля из базы (модуль farms). Если базы или такого поля нет, работают
демо-поля модуля воды: `asan-maize`, `asan-alfalfa`, `asan-orchard`.

## Внутренние контракты

```python
from app.modules.water import service

season = service.simulate_field(field, crop, sowing_date, scenario, year)  # -> FieldSeason
years = service.history_years()                                           # -> 30 лет: 1996…2025
```

- `field`, `crop`, `scenario` — **любые объекты** (Pydantic, ORM, dict): атрибуты читаются по именам из раздела 7.1 ТЗ.
- `sowing_date` — дата сева (у многолетних — начало вегетации); берутся месяц и день.
- `scenario=None` — базовые условия. `year` — год погоды из `history_years()`.
- Доп. именованные аргументы: `water=` (очередь полива), `daily=True`.
- Очередь: если её нет ни в `water=`, ни в самом поле, берутся водные права хозяйства поля
  через `farms.get_farm(field.farm_id)`; поле получает долю очереди по площади.
- Результат детерминирован и кэшируется: 3 поля × 30 лет в новом сценарии ≈ 0,3 с.

`FieldSeason` (`schemas.py`): `decades[]` — по декадам `need_net_mm`, `need_gross_m3`,
`gross_mm` (то же слоем на 1 га), `need_head_m3`, `received_m3`, `deficit_mm` (нетто),
`deficit_m3`, `deficit_pct`, `ks_avg`, `status`;
`yield_multiplier` (Ya/Ym, 0..1), `yield_t_ha`, `totals`, `alerts`, `unknown_inputs`.

**Важно для стратегий:** `yield_multiplier` учитывает только воду, жару и заморозки.
Сценарный `yield_factor` и цены сюда не входят — их применяет модуль стратегий.

**Важно для канала:** спрос хозяйства на голове канала по декаде — `need_head_m3`
(уже разделён на η_conv); на водовыпуске — `need_gross_m3`.

### Какие атрибуты читаются

| Объект | Обязательные | Необязательные (иначе — справочное значение с пометкой) |
|---|---|---|
| field | `id`, `area_ha` | `lat`/`lon` или `geometry` (GeoJSON), `elevation_m`, `soil_type`, `taw_mm_per_m`, `irrigation_method`, `eta_field`, `slope_deg`, `water` |
| field.water | — | `turn_interval_days`, `turn_hours`, `flow_l_s`, `share`, `limit_m3`, `reliability`, `failure_months`, `conveyance_efficiency`, `season_start`, `season_end` |
| crop | `kc_ini`, `kc_mid`, `kc_end`, `stage_days[4]`, `root_depth_m`, `p_depletion`, `ky` | `ky_stages[4]`, `t_base`, `t_min_kill`, `gdd_required`, `t_crit_heat`, `k_heat`, `height_m`, `is_perennial`, `yield_potential_t_ha` (или `variants[].yield_potential_t_ha`) |
| scenario | — | `water_supply_factor`, `water_supply_months` (или `water_months`), `supply_shift_days`, `temp_delta_c`, `precip_factor`, `climate_params.year`, `seed` |

Необязательного нет — не подставляется нулём: берётся справочное значение, имя входа
попадает в `unknown_inputs`, `completeness = "partial"`. Нет обязательного параметра
культуры — `ValueError` с именем параметра (тихой подстановки нет).

### Стык с модулем farms

Единственное место стыка — `sources.py`. Используются контракты модуля farms:

- `get_farm(farm_id)` — поля с сезонами и водные права (очередь) хозяйства;
- `get_crop(crop_id)` — культура; урожайность и стадии берутся из варианта, посеянного на поле;
- `list_scenario_presets()` — параметр `scenario` принимает id или код пресета
  (`like_2023`, `low_snow`, `water_minus_20`, …).

Текущий план поля — основная культура его последнего сезона. По id поля хозяйство
находится одной выборкой из таблицы `fields`. Проверено на сиде `python -m scripts.seed`.

Модуль стратегий вызывает `simulate_field` через свой адаптер (`strategy_inputs.py`) и
читает из декады `gross_mm`, `deficit_mm`, `decade`, из сезона — `yield_multiplier`.

## Где что лежит

```
backend/agroshift_core/   формулы М1–М6 (чистые функции): calendar, climate, et0, crop_et,
                          water_balance, irrigation, yield_model
backend/ingest/           power.py — загрузка NASA POWER; snapshots.py — хранилище снимков
backend/data/snapshots/   снимки 1995–2025: Сокулук, Кант, Кара-Балта (Parquet + json с sha256)
backend/app/modules/water/
    service.py            сборка сезона, simulate_field, history_years, логика эндпоинтов
    router.py schemas.py  API и схемы (FieldSeason)
    inputs.py sources.py  чтение чужих объектов; стык с модулями farms / strategies
    climate_store.py      климат из снимка: контроль качества, поправка на высоту, ET0
    catalog.py            каталог наборов NASA для /data-sources
    tests/                60 тестов
```

Обновить снимки: `docker compose exec api python -m ingest.power --force`
(снимки неизменяемы — создаются новые файлы с датой в имени).

## Тесты

`docker compose exec api pytest app/modules/water`

- ET0: пример 18 FAO-56 (3,88 мм/сут при эталоне 3,9), Hargreaves — пример 20.
- Пример 15.1 ТЗ: все три строки таблицы (ETa, D_r, множитель урожая).
- Пример 15.2 ТЗ: 300 мм на водовыпуске при η = 0,5 → дефицит 150 мм; на голове канала → 52,5 мм.
- Баланс сходится (невязка < 0,5 мм), при достаточной воде K_s = 1 и Ya/Ym = 1.
- Монотонность: меньше подача — урожай не растёт, почва не влажнее ни в один день
  (Hypothesis на жёстких входах + 30 лет × 3 культуры на реальных данных).
- Сроки подачи: та же вода после цветения — урожай ниже. Воспроизводимость. Пропуск ≠ ноль.
- Стык с farms: объекты его офлайн-сида (Farm, Field, Crop, Scenario) проходят через
  `simulate_field` как есть.

## Упрощения относительно ТЗ

- **Вода между полями** делится долей `share` (по умолчанию очередь целиком на поле),
  а не жадным правилом М5 по «убытку на 1 м³» (функция приоритета `irrigation.loss_per_m3` есть).
- **Срывы очереди** — детерминированный жребий по `(seed, год)`: одно хозяйство в один год
  теряет одни и те же очереди при любой культуре (общие случайные числа, М10).
- **Полив в день очереди** — до полной влагоёмкости к концу суток (с учётом расхода за
  этот день); лишняя вода не берётся. Если зона стресса тоньше суточной потребности
  (очень мелкие корни), культура берёт только оставшуюся влагу — баланс сходится всегда.
- **Статус декады** (`ok` / `deficit_lt20` / `deficit_ge20`): тревога, когда культура уже
  недобрала воду либо подано меньше потребности и легкодоступный запас почвы исчерпан.
- **Фаза цветения** для F_heat — первая треть середины сезона; для F_frost сада —
  конец начальной стадии + 14 дней. `k_frost` по умолчанию 0,25 (экспертная оценка).
- Не сделано: quantile mapping по наземной станции, Kc по NDVI, начальная влажность из SMAP,
  сверка ET0 с пакетом pyet.

## Фронтенд

```
frontend/lib/api/water.ts            клиент API и типы
frontend/components/water/           WaterLane, FieldWaterCard, SeasonChart, SoilChart,
                                     YieldCard, Provenance, NasaData, GridCellMap
frontend/app/field/[id]/page.tsx     карточка поля        →  /field/asan-maize
frontend/app/nasa/page.tsx           «Данные NASA»        →  /nasa
```

Нужны пакеты: `npm i echarts maplibre-gl`. Адрес API — `NEXT_PUBLIC_API_URL`
(по умолчанию `http://localhost:8000`). Tailwind и UI-кит не требуются: стили в CSS-модуле.

Лента воды на главном экране:

```tsx
import WaterLane from "@/components/water/WaterLane";

<WaterLane fieldIds={farm.fields.map((f) => f.id)} strategy={strategyId} scenario={scenarioId}
           selectedDecade={decade} onSelectDecade={setDecade} />
```
