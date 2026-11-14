"""canals — заглушки по разделу 11.2 ТЗ. Реализация -> app/services + agroshift_core."""

from fastapi import APIRouter

from app.core.errors import NotImplementedYetError

router = APIRouter(tags=["canals"])


@router.get("/canals", summary="Список каналов")
def canals_1() -> None:
    raise NotImplementedYetError("Список каналов", "UC-5")


@router.post("/canals", summary="Создать канал")
def canals_2() -> None:
    raise NotImplementedYetError("Создать канал", "FR-8.1")


@router.get("/canals/{canal_id}/supply", summary="Подача по декадам")
def canals_3() -> None:
    raise NotImplementedYetError("Подача по декадам", "FR-8.2")


@router.post("/canals/{canal_id}/supply", summary="Ввести подачу по декадам")
def canals_4() -> None:
    raise NotImplementedYetError("Ввести подачу по декадам", "FR-8.2")


@router.post("/canals/{canal_id}/plans:coordinate", summary="Запустить согласование")
def canals_5() -> None:
    raise NotImplementedYetError("Запустить согласование", "М15")


@router.get("/canal-plans/{plan_id}", summary="План канала")
def canals_6() -> None:
    raise NotImplementedYetError("План канала", "М15")


@router.post("/canal-proposals/{proposal_id}:respond", summary="Ответ хозяйства на предложение")
def canals_7() -> None:
    raise NotImplementedYetError("Ответ хозяйства на предложение", "FR-8.6")
