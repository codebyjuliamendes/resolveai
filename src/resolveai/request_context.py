"""Request id compartilhado entre middleware, logs e respostas de erro."""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def new_request_id(incoming: str | None) -> str:
    """Aceita um X-Request-ID seguro vindo do proxy; caso contrário gera um UUID."""
    if incoming and _VALID_ID.match(incoming):
        return incoming
    return uuid.uuid4().hex


def set_request_id(value: str | None) -> None:
    _request_id.set(value)


def current_request_id() -> str | None:
    return _request_id.get()
