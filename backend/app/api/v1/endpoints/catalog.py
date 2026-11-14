"""catalog — заглушки по разделу 11.2 ТЗ. Реализация -> app/services + agroshift_core."""

from fastapi import APIRouter

from app.core.errors import NotImplementedYetError

router = APIRouter(tags=["catalog"])


@router.get("/catalog/crops", summary="Справочник культур")
def catalog_1() -> None:
    raise NotImplementedYetError("Справочник культур", "7.1")


@router.get("/catalog/rotations", summary="Схемы севооборота зоны")
def catalog_2() -> None:
    raise NotImplementedYetError("Схемы севооборота зоны", "7.1")
