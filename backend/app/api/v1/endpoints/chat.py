"""chat — заглушки по разделу 11.2 ТЗ. Реализация -> app/services + agroshift_core."""

from fastapi import APIRouter

from app.core.errors import NotImplementedYetError

router = APIRouter(tags=["chat"])


@router.post("/chat/sessions", summary="Новый диалог с ИИ")
def chat_1() -> None:
    raise NotImplementedYetError("Новый диалог с ИИ", "10")


@router.post("/chat/sessions/{session_id}/messages", summary="Сообщение ИИ-помощнику")
def chat_2() -> None:
    raise NotImplementedYetError("Сообщение ИИ-помощнику", "10")
