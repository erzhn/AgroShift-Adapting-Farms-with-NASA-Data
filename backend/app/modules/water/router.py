"""API модуля «Вода и климат» (раздел 11.2 ТЗ). Префикс /api/v1 добавляет общий роутер."""

from datetime import date

from fastapi import APIRouter, Query

from app.core.errors import ProblemError
from app.modules.water import service
from app.modules.water.climate_store import NoSnapshotError
from app.modules.water.schemas import ClimateResponse, DataSourcesResponse, WaterBalanceResponse

router = APIRouter(tags=["water"])


def _guard(call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except NoSnapshotError as exc:
        raise ProblemError(503, "Service Unavailable", str(exc)) from exc
    except ValueError as exc:
        raise ProblemError(422, "Unprocessable Entity", str(exc)) from exc


@router.get("/fields/{field_id}/climate", response_model=ClimateResponse,
            summary="Климат поля из снимка NASA POWER + ET0")
def field_climate(
    field_id: str,
    date_from: date | None = Query(None, alias="from", description="начало периода, ISO"),
    date_to: date | None = Query(None, alias="to", description="конец периода, ISO"),
) -> ClimateResponse:
    """Суточные ряды и ET0 (М1–М2) за период; по умолчанию — последний полный год.

    Плюс нормы по декадам (P10/P50/P90 за 30 лет), даты заморозков и ячейка сетки NASA.
    """
    return _guard(service.get_field_climate, field_id, date_from, date_to)


@router.get("/fields/{field_id}/water-balance", response_model=WaterBalanceResponse,
            summary="Водный баланс поля по декадам")
def field_water_balance(
    field_id: str,
    strategy: str | None = Query(None, description="id стратегии; пусто — текущий план"),
    scenario: str | None = Query(None, description="id или код сценария; пусто — базовый"),
    year: int | None = Query(None, description="исторический год погоды; пусто — типичный"),
    daily: bool = Query(False, description="приложить суточные ряды истощения почвы"),
) -> WaterBalanceResponse:
    """Потребность нетто/брутто, подача по очереди, дефицит и урожай (М3–М6).

    `season` — выбранный год; `ensemble` — тот же расчёт на 30 годах NASA (P10/P50/P90).
    """
    return _guard(service.get_field_water_balance, field_id, strategy, scenario, year, daily)


@router.get("/data-sources", response_model=DataSourcesResponse,
            summary="Данные NASA: наборы, снимки, атрибуция")
def data_sources(lang: str = Query("ru", pattern="^(ru|en|ky)$")) -> DataSourcesResponse:
    return _guard(service.get_data_sources, lang)
