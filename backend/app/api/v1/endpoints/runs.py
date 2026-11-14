"""runs — заглушки по разделу 11.2 ТЗ. Реализация -> app/services + agroshift_core."""

from fastapi import APIRouter, Body

from app.core.errors import NotImplementedYetError
from app.schemas.strategies import (
    BreakpointsResponse,
    CashflowResponse,
    StressRequest,
    StressResponse,
)
from app.services import strategies as service

router = APIRouter(tags=["runs"])


@router.post("/runs", summary="Прогон стратегии через сценарий")
def runs_1() -> None:
    raise NotImplementedYetError("Прогон стратегии через сценарий", "М10")


@router.get("/runs/{run_id}/metrics", summary="Метрики P10/P50/P90")
def runs_2() -> None:
    raise NotImplementedYetError("Метрики P10/P50/P90", "М10")


@router.get(
    "/runs/{run_id}/cashflow",
    summary="Денежный поток по месяцам",
    response_model=CashflowResponse,
)
def get_cashflow(run_id: str) -> CashflowResponse:
    """Остаток по месяцам (P10/P50/P90), линия резерва, кассовый разрыв (М9)."""
    return service.get_cashflow(run_id)


@router.get("/runs/{run_id}/feed", summary="Кормовой баланс")
def runs_4() -> None:
    raise NotImplementedYetError("Кормовой баланс", "М8")


@router.post(
    "/runs/{run_id}/stress",
    summary="Стресс-тест по ползункам",
    response_model=StressResponse,
)
def stress_run(run_id: str, req: StressRequest | None = Body(default=None)) -> StressResponse:
    """Исходный план в новых условиях против исправленного, цена адаптации (М12)."""
    return service.stress(run_id, req or StressRequest())


@router.get(
    "/runs/{run_id}/breakpoints",
    summary="Точки поломки",
    response_model=BreakpointsResponse,
)
def get_breakpoints(run_id: str) -> BreakpointsResponse:
    """Минимальное отклонение каждого фактора, ломающее план, + «было в N из 30 лет» (М13)."""
    return service.get_breakpoints(run_id)
