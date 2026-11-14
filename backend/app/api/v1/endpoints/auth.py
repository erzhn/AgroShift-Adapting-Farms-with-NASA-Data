"""auth — заглушки по разделу 11.2 ТЗ. Реализация -> app/services + agroshift_core."""

from fastapi import APIRouter

from app.core.errors import NotImplementedYetError

router = APIRouter(tags=["auth"])


@router.post("/auth/otp", summary="Запросить SMS-код")
def auth_1() -> None:
    raise NotImplementedYetError("Запросить SMS-код", "9.1, FR-1.1")


@router.post("/auth/verify", summary="Подтвердить SMS-код, получить JWT")
def auth_2() -> None:
    raise NotImplementedYetError("Подтвердить SMS-код, получить JWT", "9.1, FR-1.1")
