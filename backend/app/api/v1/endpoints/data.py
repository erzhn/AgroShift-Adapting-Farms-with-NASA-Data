"""data — заглушки по разделу 11.2 ТЗ. Реализация -> app/services + agroshift_core."""

from fastapi import APIRouter

from app.core.errors import NotImplementedYetError

router = APIRouter(tags=["data"])


@router.get("/provenance/{metric_ref}", summary="Откуда это число")
def data_1() -> None:
    raise NotImplementedYetError("Откуда это число", "FR-11.1")



@router.post("/admin/snapshots:refresh", summary="Обновить снимки данных")
def data_3() -> None:
    raise NotImplementedYetError("Обновить снимки данных", "6.3")


@router.get("/analytics/district/{district_id}", summary="Агрегаты по району (k >= 10)")
def data_4() -> None:
    raise NotImplementedYetError("Агрегаты по району (k >= 10)", "FR-11.4")


@router.get("/reports/farm/{farm_id}.pdf", summary="Печатный отчёт")
def data_5() -> None:
    raise NotImplementedYetError("Печатный отчёт", "FR-9.4")
