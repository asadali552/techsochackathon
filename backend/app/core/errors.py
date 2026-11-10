import logging

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(status, message, {"WWW-Authenticate": "Bearer"} if status == 401 else None)
        self.code = code


def error_response(status: int, code: str, message: str, *, details=None, headers=None) -> JSONResponse:
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status, content={"data": None, "error": error}, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        codes = {404: "not_found", 405: "method_not_allowed"}
        code = exc.code if isinstance(exc, ApiError) else codes.get(exc.status_code, "request_failed")
        return error_response(exc.status_code, code, str(exc.detail), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(map(str, error["loc"])), "message": error["msg"]}
            for error in exc.errors()
        ]
        return error_response(422, "validation_error", "Invalid request", details=details)

    @app.exception_handler(psycopg.Error)
    async def database_error(_request: Request, exc: psycopg.Error) -> JSONResponse:
        # Avoid logging query values, private coordinates, descriptions, or the DSN.
        logger.error("Database operation failed (%s, SQLSTATE %s)", type(exc).__name__, exc.sqlstate)
        if isinstance(exc, (psycopg.OperationalError, psycopg.errors.QueryCanceled)):
            return error_response(503, "database_unavailable", "Database temporarily unavailable")
        return error_response(500, "database_error", "Database operation failed")
