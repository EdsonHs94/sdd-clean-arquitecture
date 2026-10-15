"""Translate application failures into safe HTTP responses."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.application.errors import (
    DependencyUnavailable,
    EmailAlreadyRegistered,
    FileNotFound,
    InvalidCredentials,
    NotAuthenticated,
    NoteNotFound,
)
from app.domain.errors import FileTooLarge, InvalidFileData, InvalidNoteData, InvalidUserData


async def application_error(request: Request, error: Exception) -> JSONResponse:
    statuses = {
        EmailAlreadyRegistered: 409,
        InvalidCredentials: 401,
        NotAuthenticated: 401,
        DependencyUnavailable: 503,
        FileTooLarge: 413,
        FileNotFound: 404,
        NoteNotFound: 404,
    }
    status = statuses[type(error)]
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(status_code=status, content={"detail": str(error)}, headers=headers)


async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    detail = []
    for item in error.errors():
        location = item["loc"]
        if item["type"] == "extra_forbidden":
            # Unknown keys are client input too and can contain credential values.
            location = location[:-1]
        detail.append({"loc": location, "msg": item["msg"], "type": item["type"]})
    return JSONResponse(status_code=422, content={"detail": detail})


async def domain_validation_error(
    request: Request, error: InvalidUserData | InvalidFileData | InvalidNoteData
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": [{"loc": ["body"], "msg": str(error), "type": "value_error"}]},
    )


async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


class SanitizedServerErrors:
    """Keep unhandled HTTP exception details inside the presentation boundary."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        response_started = False

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, tracked_send)
        except Exception:
            if response_started:
                # A second response is invalid; the server may log only this message.
                raise RuntimeError("Response processing failed") from None
            response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
            await response(scope, receive, send)


def install_error_handlers(app: FastAPI) -> None:
    app.add_middleware(SanitizedServerErrors)
    for exception in (
        EmailAlreadyRegistered,
        InvalidCredentials,
        NotAuthenticated,
        DependencyUnavailable,
        FileTooLarge,
        FileNotFound,
        NoteNotFound,
    ):
        app.add_exception_handler(exception, application_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(InvalidUserData, domain_validation_error)
    app.add_exception_handler(InvalidFileData, domain_validation_error)
    app.add_exception_handler(InvalidNoteData, domain_validation_error)
    app.add_exception_handler(Exception, unexpected_error)
