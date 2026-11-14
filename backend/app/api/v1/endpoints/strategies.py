"""strategies — заглушки по разделу 11.2 ТЗ. Реализация -> app/services + agroshift_core."""

from fastapi import APIRouter

from app.core.errors import NotImplementedYetError

router = APIRouter(tags=["strategies"])


@router.post("/scenarios", summary="Создать сценарий")
def strategies_1() -> None:
    raise NotImplementedYetError("Создать сценарий", "UC-3")


@router.post(
    "/farms/{farm_id}/strategies:generate",
    summary="Построить варианты будущего",
)
def strategies_2() -> None:
    raise NotImplementedYetError("Построить варианты будущего -> job_id", "М11, UC-2")


@router.get("/jobs/{job_id}", summary="Статус задачи")
def strategies_3() -> None:
    raise NotImplementedYetError("Статус задачи", "11.2")


@router.get("/strategies/{strategy_id}", summary="Стратегия")
def strategies_4() -> None:
    raise NotImplementedYetError("Стратегия", "UC-2")


@router.post("/strategies", summary="Мой вариант")
def strategies_5() -> None:
    raise NotImplementedYetError("Мой вариант", "FR-4.8")


@router.post("/goals", summary="План от цели")
def strategies_6() -> None:
    raise NotImplementedYetError("План от цели", "UC-6")


@router.get("/farms/{farm_id}/voi", summary="Самое полезное следующее измерение")
def strategies_7() -> None:
    raise NotImplementedYetError("Самое полезное следующее измерение", "М14")
