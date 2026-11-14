"""farms — заглушки по разделу 11.2 ТЗ. Реализация -> app/services + agroshift_core."""

from fastapi import APIRouter

from app.core.errors import NotImplementedYetError

router = APIRouter(tags=["farms"])


@router.get("/farms", summary="Список хозяйств")
def farms_1() -> None:
    raise NotImplementedYetError("Список хозяйств", "7.1")


@router.post("/farms", summary="Создать хозяйство")
def farms_2() -> None:
    raise NotImplementedYetError("Создать хозяйство", "UC-1")


@router.get("/farms/{farm_id}", summary="Хозяйство")
def farms_3() -> None:
    raise NotImplementedYetError("Хозяйство", "7.1")


@router.patch("/farms/{farm_id}", summary="Изменить хозяйство")
def farms_4() -> None:
    raise NotImplementedYetError("Изменить хозяйство", "7.1")


@router.get("/farms/{farm_id}/fields", summary="Поля хозяйства (GeoJSON)")
def farms_5() -> None:
    raise NotImplementedYetError("Поля хозяйства (GeoJSON)", "FR-1.4")


@router.post("/farms/{farm_id}/fields", summary="Добавить поле")
def farms_6() -> None:
    raise NotImplementedYetError("Добавить поле", "FR-1.4")


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
