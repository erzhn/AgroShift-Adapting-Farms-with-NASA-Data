"""fields — заглушки по разделу 11.2 ТЗ. Реализация -> app/services + agroshift_core."""

from fastapi import APIRouter

from app.core.errors import NotImplementedYetError

router = APIRouter(tags=["fields"])


@router.get("/fields/{field_id}/climate", summary="Климат поля из снимка + ET0")
def fields_1() -> None:
    raise NotImplementedYetError("Климат поля из снимка + ET0", "М1–М2")


@router.get("/fields/{field_id}/water-balance", summary="Водный баланс по декадам")
def fields_2() -> None:
    raise NotImplementedYetError("Водный баланс по декадам", "М4–М5")
