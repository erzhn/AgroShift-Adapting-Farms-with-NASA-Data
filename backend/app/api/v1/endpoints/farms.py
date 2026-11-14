"""Farm CRUD is owned by modules.farms; remaining full-product assets are separate."""

from app.core.errors import NotImplementedYetError
from app.modules.farms.router import router


@router.get("/farms/{farm_id}/orchards", summary="Сады")
def farms_7() -> None:
    raise NotImplementedYetError("Сады", "7.1")


@router.get("/farms/{farm_id}/herds", summary="Животные")
def farms_8() -> None:
    raise NotImplementedYetError("Животные", "7.1")


@router.get("/farms/{farm_id}/equipment", summary="Техника")
def farms_9() -> None:
    raise NotImplementedYetError("Техника", "7.1")


@router.get("/farms/{farm_id}/obligations", summary="Обязательства")
def farms_10() -> None:
    raise NotImplementedYetError("Обязательства", "7.1")


@router.post("/farms/{farm_id}/events", summary="Факт: полив, расход, уборка, продажа")
def farms_11() -> None:
    raise NotImplementedYetError("Факт: полив, расход, уборка, продажа", "UC-8")


@router.get("/farms/{farm_id}/plan-fact", summary="План-факт за сезон")
def farms_12() -> None:
    raise NotImplementedYetError("План-факт за сезон", "М16")
