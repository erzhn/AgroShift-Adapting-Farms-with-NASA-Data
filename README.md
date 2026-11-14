# AgroShift — будущее твоего хозяйства

Система поддержки решений для хозяйств Кыргызстана: строит несколько вариантов развития
хозяйства и группы хозяйств на одном канале, проверяет каждый на нехватку **воды, денег и корма**
и показывает, в каком месяце и почему план ломается.

NASA Space Apps Challenge 2026 · челлендж **«Field Shift: Adapting Farms with NASA Data»** · Бишкек, 14–15 ноября 2026.

> **Статус:** реализованы хозяйства и справочники, главный экран, профиль и модуль
> стратегий/денег. Вода и климат пока используют демонстрационные оценки; часть
> остальных модулей остаётся каркасом. [Все 7 задач Баямана](docs/bayaman-complete.md).

---

## Стек

| Слой | Технологии |
|---|---|
| API | Python 3.12, FastAPI, Pydantic v2 |
| БД | PostgreSQL 16 + PostGIS 3.4, SQLAlchemy 2, Alembic |
| Расчётное ядро | NumPy, pandas (пакет `agroshift_core`) |
| Данные | NASA POWER (REST), снимки в Parquet |
| Сборка | Docker, Docker Compose |
| Интерфейс | Next.js, React, TypeScript, MapLibre, ECharts |

## Быстрый старт

Нужен только **Docker Desktop**.

```bash
git clone <repo-url> agroshift
cd agroshift
cp .env.example .env
docker compose up --build -d
docker compose exec -T api python -m scripts.seed
```

Проверка:

- Интерфейс хозяйства: http://localhost:3000
- Swagger (все эндпоинты): http://localhost:8000/docs
- Живость: http://localhost:8000/health
- БД + PostGIS: http://localhost:8000/health/db

При старте контейнер `api` сам применяет миграции (`alembic upgrade head`).
Код примонтирован в контейнер — правки в `backend/` подхватываются без пересборки.
Seed загружает Асана, 5 культур, 5 сценариев и экспериментальные севообороты;
повторный запуск сохраняет изменения пользователя. Для фронтенда без Docker
и подключения лент см. [frontend/README.md](frontend/README.md).

Postgres снаружи доступен на `localhost:5433` (логин/пароль/БД: `agroshift`).
Веб-интерфейс к БД: `docker compose --profile tools up adminer` → http://localhost:8080

### Частые команды

```bash
docker compose exec api pytest                     # тесты
docker compose exec api ruff check . --fix         # линтер
docker compose exec api alembic revision --autogenerate -m "что изменили"   # новая миграция
docker compose exec api alembic upgrade head       # применить миграции
docker compose down                                # остановить
docker compose down -v                             # остановить и удалить данные БД
```

## Структура

```
.
├── docker-compose.yml        db (PostGIS) + api + frontend (+ adminer в профиле tools)
├── .env.example              переменные окружения → скопировать в .env
├── docs/architecture.md      слои, потоки данных, договорённости
├── frontend/                 Next.js: хозяйство, профиль, справочники, стратегии
└── backend/
    ├── Dockerfile
    ├── requirements.txt / requirements-dev.txt
    ├── alembic/              миграции БД
    ├── app/                  API-шлюз FastAPI
    │   ├── main.py           точка входа, /health
    │   ├── api/v1/endpoints/ эндпоинты по разделу 11.2 ТЗ (сейчас заглушки 501)
    │   ├── core/             config, ошибки RFC 9457, JWT, матрица прав (4.3), i18n
    │   ├── db/               Base, сессия
    │   ├── models/           ORM — все сущности раздела 7.1 (35 таблиц)
    │   ├── schemas/          Pydantic-схемы запросов/ответов
    │   ├── services/         бизнес-логика: БД ↔ ядро
    │   ├── ai/               ИИ-помощник: адаптер LLM, инструменты, guard чисел
    │   └── i18n/             ru / ky / en
    ├── agroshift_core/       расчётное ядро М1–М17 (чистые функции, без БД и сети)
    ├── ingest/               загрузка NASA POWER и др. → снимки
    ├── scripts/seed.py       сид-данные (культуры, демо-хозяйство «Асан», демо-канал)
    ├── data/snapshots/       снимки NASA POWER (Parquet) для офлайн-демо
    └── tests/
```

## Где что делать

### Расчётное ядро — `backend/agroshift_core/`

| Модуль | Файл | ТЗ |
|---|---|---|
| Декады | `calendar.py` | 8 |
| М1 Подготовка климата | `climate.py` | 8.1 |
| М2 ET0 Penman–Monteith | `et0.py` | 8.2 |
| М3 Kc, ETc | `crop_et.py` | 8.3 |
| М4 Водный баланс | `water_balance.py` | 8.4 |
| М5 Брутто → нетто, очередь | `irrigation.py` | 8.5 |
| М6 Урожай при дефиците | `yield_model.py` | 8.6 |
| М7 Сад, NPV | `orchard.py` | 8.7 |
| М8 Корма | `feed.py` | 8.8 |
| М9 Денежный поток | `cashflow.py` | 8.9 |
| М10 Монте-Карло | `uncertainty.py` | 8.10 |
| М11 Стратегии | `optimizer.py` | 8.11 |
| М12 Стресс-тест | `stress.py` | 8.12 |
| М13 Точка поломки | `breakpoints.py` | 8.13 |
| М14 Ценность информации | `voi.py` | 8.14 |
| М15 План канала | `canal.py` | 8.15 |
| М16 План-факт | `calibration.py` | 8.16 |
| М17 Сравнение | `compare.py` | 8.17 |

Эталонные примеры для тестов — раздел 15 ТЗ (кладите в `backend/tests/core/`).

### API — `backend/app/api/v1/endpoints/`

Один файл на группу: `auth`, `farms`, `fields`, `catalog`, `strategies`, `runs`, `canals`,
`chat`, `data`. Чтобы реализовать эндпоинт:

1. Pydantic-схема в `app/schemas/<группа>.py`.
2. Логика в `app/services/<группа>.py` (ходит в БД и вызывает `agroshift_core`).
3. В эндпоинте заменить `raise NotImplementedYetError(...)` на вызов сервиса.

### Данные — `backend/ingest/`

`power.py` — загрузка NASA POWER (daily, community=AG) для точек Чуйской области
→ Parquet в `data/snapshots/` + sha256. Запрос — раздел 6.1 ТЗ.

## Договорённости

- **Ядро не знает про API и БД**: в `agroshift_core` нельзя импортировать `app`, ходить в сеть или файлы.
- **ИИ не считает**: все числа — из ядра; ИИ только вызывает инструменты и объясняет.
- **Деньги** — целые сомы. **Вода** — мм и м³ (1 мм × 1 га = 10 м³). **Даты** — Asia/Bishkek.
- **Пропуск ≠ ноль**: неизвестное значение — `None` + флаг `completeness = partial`.
- **Ошибки API** — `application/problem+json` (RFC 9457), бросать `ProblemError` из `app/core/errors.py`.
- **Изменили модель БД** → `alembic revision --autogenerate` → проверить файл миграции → закоммитить.
- **Секреты** — только в `.env`, в репозиторий не коммитим.
- **Ветки**: `main` — рабочая; задачи — в `feat/<что-делаем>`, слияние через PR.
- **Перед коммитом**: `ruff check . --fix` и `pytest`.

## Данные NASA

| Набор | Для чего | Статус |
|---|---|---|
| NASA POWER (daily, AG) | климат → ET0, GDD, заморозки, 30 лет истории | MVP |
| SRTM / NASADEM | высота и уклон поля | MVP |
| GPM IMERG | осадки в горном рельефе | MVP+ |
| MODIS MOD10A1 | снегозапас водосбора канала | MVP+ |
| HLS | NDVI полей | MVP+ |

Data provided by the **NASA Langley Research Center (LaRC) POWER Project**, funded through the NASA Earth Science/Applied Science Program.

## Лицензия

[MIT](LICENSE)
