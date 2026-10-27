"""Erros da API sempre em JSON: {"error": "...", "requestId": "..."}."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from resolveai.request_context import current_request_id

log = structlog.get_logger(__name__)

GENERIC_VALIDATION = "Confira os dados enviados."
# Mensagens por rota, preservando as da versão anterior.
VALIDATION_MESSAGES: dict[str, str] = {
    "create_ticket": "Confira nome, e-mail, assunto e mensagem do chamado.",
    "update_ticket_status": "Status inválido.",
    "create_article": "Confira título, categoria e conteúdo do artigo.",
    "update_article": "Confira título, categoria e conteúdo do artigo.",
    "suggest": "Informe a mensagem do cliente.",
    "create_reply": "A resposta deve ter entre 4 e 1.600 caracteres.",
    "search": "Informe um termo de busca de até 200 caracteres.",
}
HTTP_MESSAGES: dict[int, str] = {
    404: "Recurso não encontrado.",
    405: "Método não permitido.",
    413: "O conteúdo enviado é grande demais.",
}


class ApiError(Exception):
    def __init__(
        self, status_code: int, message: str, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.headers = headers


def error_response(
    status_code: int, message: str, headers: dict[str, str] | None = None, **extra: Any
) -> JSONResponse:
    content: dict[str, Any] = {"error": message, **extra}
    request_id = current_request_id()
    if request_id:
        content["requestId"] = request_id
    return JSONResponse(content, status_code=status_code, headers=headers)


def _validation_details(exc: RequestValidationError) -> list[dict[str, str]]:
    details = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", ()) if part not in ("body", "query", "path")]
        details.append({"field": ".".join(loc) or "body", "message": str(err.get("msg", ""))})
    return details


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status_code, exc.message, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        route = request.scope.get("route")
        name = getattr(route, "name", "")
        details = _validation_details(exc)
        errors = exc.errors()
        if any(err.get("loc", ("",))[0] == "path" for err in errors):
            # IDs malformados equivalem a recurso inexistente.
            return error_response(404, "Recurso não encontrado.")
        if any(err.get("type") == "json_invalid" for err in errors):
            message = "JSON inválido."
        else:
            message = VALIDATION_MESSAGES.get(name, GENERIC_VALIDATION)
        return error_response(400, message, details=details)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = HTTP_MESSAGES.get(exc.status_code, str(exc.detail))
        return error_response(exc.status_code, message, getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", error=type(exc).__name__)
        return error_response(500, "Erro interno. Tente novamente em instantes.")
