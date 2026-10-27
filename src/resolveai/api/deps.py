"""Dependências compartilhadas pelas rotas."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from resolveai.config import Settings
from resolveai.errors import ApiError
from resolveai.ratelimit import SlidingWindowRateLimiter
from resolveai.suggestions import SuggestionProvider

RATE_LIMIT_MESSAGE = (
    "Muitas solicitações em pouco tempo. Aguarde alguns segundos e tente novamente."
)


@dataclass(slots=True)
class AppState:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    provider: SuggestionProvider
    write_limiter: SlidingWindowRateLimiter
    suggest_limiter: SlidingWindowRateLimiter


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.resolveai
    return state


StateDep = Annotated[AppState, Depends(get_state)]


def get_db(state: StateDep) -> Iterator[Session]:
    with state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]


def _client_key(request: Request) -> str:
    # Atrás de proxy, o Uvicorn resolve o IP real via --proxy-headers/FORWARDED_ALLOW_IPS.
    return request.client.host if request.client else "unknown"


def _enforce(limiter: SlidingWindowRateLimiter, state: AppState, request: Request) -> None:
    if not state.settings.rate_limit_enabled:
        return
    retry_after = limiter.hit(_client_key(request))
    if retry_after is not None:
        raise ApiError(429, RATE_LIMIT_MESSAGE, headers={"Retry-After": str(retry_after)})


def limit_writes(request: Request, state: StateDep) -> None:
    _enforce(state.write_limiter, state, request)


def limit_suggestions(request: Request, state: StateDep) -> None:
    _enforce(state.suggest_limiter, state, request)


WriteLimit = Depends(limit_writes)
SuggestLimit = Depends(limit_suggestions)
