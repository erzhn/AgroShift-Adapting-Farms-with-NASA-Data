"""strategies — заглушки по разделу 11.2 ТЗ. Реализация -> app/services + agroshift_core."""

from fastapi import APIRouter, Body

from app.core.errors import NotImplementedYetError
from app.schemas.strategies import GenerateRequest, GenerateResponse, StrategyOut
from app.services import strategies as service

router = APIRouter(tags=["strategies"])


@router.post("/scenarios", summary="Создать сценарий")
def strategies_1() -> None:
    raise NotImplementedYetError("Создать сценарий", "UC-3")


@router.post(
    "/farms/{farm_id}/strategies:generate",
    summary="Построить варианты будущего",
    response_model=GenerateResponse,
)
def generate_strategies(
    farm_id: str, req: GenerateRequest | None = Body(default=None)
) -> GenerateResponse:
    """Перебор утверждённых схем (≤ 500) на 30 годах NASA; до четырёх стратегий (М11).

    Считается синхронно. Повторный вызов с теми же входами отдаёт тот же результат и те же id.
    """
    return service.generate(farm_id, req or GenerateRequest())


@router.get("/jobs/{job_id}", summary="Статус задачи")
def strategies_3() -> None:
    raise NotImplementedYetError("Статус задачи", "11.2")


@router.get("/strategies/{strategy_id}", summary="Стратегия", response_model=StrategyOut)
def get_strategy(strategy_id: str) -> StrategyOut:
    return service.get_strategy(strategy_id)


@router.post("/strategies", summary="Мой вариант")
def strategies_5() -> None:
    raise NotImplementedYetError("Мой вариант", "FR-4.8")


@router.post("/goals", summary="План от цели")
def strategies_6() -> None:
    raise NotImplementedYetError("План от цели", "UC-6")


@router.get("/farms/{farm_id}/voi", summary="Самое полезное следующее измерение")
def strategies_7() -> None:
    raise NotImplementedYetError("Самое полезное следующее измерение", "М14")
