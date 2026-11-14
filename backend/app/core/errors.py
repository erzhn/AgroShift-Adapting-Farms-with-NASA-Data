"""Ошибки API в формате RFC 9457 (application/problem+json) — раздел 11.2 ТЗ."""

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"


class ProblemError(Exception):
    """Бросайте из сервисов и эндпоинтов вместо HTTPException."""

    def __init__(
        self,
        status: int,
        title: str,
        detail: str | None = None,
        type_: str = "about:blank",
        **extra: Any,
    ) -> None:
        self.status = status
        self.title = title
        self.detail = detail
        self.type = type_
        self.extra = extra


class NotFoundError(ProblemError):
    def __init__(self, entity: str, entity_id: Any) -> None:
        super().__init__(404, "Not Found", f"{entity} {entity_id} не найден")


class NotImplementedYetError(ProblemError):
    """Заглушка: эндпоинт описан в ТЗ, но ещё не реализован.

    Возвращает 501 с указанием раздела ТЗ и модуля ядра, чтобы фронтенд видел контракт.
    """

    def __init__(self, feature: str, tz_section: str, core_module: str | None = None) -> None:
        super().__init__(
            501,
            "Not Implemented",
            f"{feature} — ещё не реализовано (ТЗ, раздел {tz_section})",
            type_="https://agroshift.app/problems/not-implemented",
            tz_section=tz_section,
            core_module=core_module,
        )


def _problem(status: int, title: str, detail: Any = None, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {"type": extra.pop("type", "about:blank"), "title": title,
                            "status": status}
    if detail is not None:
        body["detail"] = detail
    body.update({k: v for k, v in extra.items() if v is not None})
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def _problem_handler(_: Request, exc: ProblemError) -> JSONResponse:
        return _problem(exc.status, exc.title, exc.detail, type=exc.type, **exc.extra)

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = HTTPStatus(exc.status_code).phrase
        return _problem(exc.status_code, title, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic v2 includes the originating ValueError under ``ctx.error``.
        # That object is not JSON serializable; expose stable, client-safe fields.
        errors = [
            {
                "loc": error.get("loc", ()),
                "msg": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
        return _problem(422, "Unprocessable Entity", "Ошибка валидации входных данных",
                        errors=errors)
