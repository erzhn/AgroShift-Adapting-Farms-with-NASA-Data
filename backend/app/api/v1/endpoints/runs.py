"""runs — заглушки по разделу 11.2 ТЗ. Реализация -> app/services + agroshift_core."""

from fastapi import APIRouter

from app.core.errors import NotImplementedYetError

router = APIRouter(tags=["runs"])


@router.post("/runs", summary="Прогон стратегии через сценарий")
def runs_1() -> None:
    raise NotImplementedYetError("Прогон стратегии через сценарий", "М10")


@router.get("/runs/{run_id}/metrics", summary="Метрики P10/P50/P90")
def runs_2() -> None:
    raise NotImplementedYetError("Метрики P10/P50/P90", "М10")


@router.get("/runs/{run_id}/cashflow", summary="Денежный поток по месяцам")
def runs_3() -> None:
    raise NotImplementedYetError("Денежный поток по месяцам", "М9")


@router.get("/runs/{run_id}/feed", summary="Кормовой баланс")
def runs_4() -> None:
    raise NotImplementedYetError("Кормовой баланс", "М8")


@router.post("/runs/{run_id}/stress", summary="Стресс-тест по ползункам")
def runs_5() -> None:
    raise NotImplementedYetError("Стресс-тест по ползункам", "М12")


@router.get("/runs/{run_id}/breakpoints", summary="Точки поломки")
def runs_6() -> None:
    raise NotImplementedYetError("Точки поломки", "М13")
