"""Fábrica da aplicação FastAPI."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from resolveai.api import articles, health, replies, suggest, tickets
from resolveai.api.deps import AppState
from resolveai.config import Settings, get_settings
from resolveai.db import create_db_engine, make_session_factory
from resolveai.errors import ApiError, install_error_handlers
from resolveai.middleware import (
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from resolveai.migrate import run_migrations
from resolveai.ratelimit import SlidingWindowRateLimiter
from resolveai.seed import seed_demo_data
from resolveai.suggestions import SuggestionProvider
from resolveai.suggestions.openai import OpenAISuggestionProvider
from resolveai.suggestions.template import TemplateSuggestionProvider

log = structlog.get_logger(__name__)


def build_provider(settings: Settings, client: httpx.AsyncClient) -> SuggestionProvider:
    if settings.openai_api_key is not None and settings.openai_model:
        return OpenAISuggestionProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            client=client,
            base_url=settings.openai_base_url,
            max_retries=settings.openai_max_retries,
            max_output_tokens=settings.openai_max_output_tokens,
        )
    return TemplateSuggestionProvider()


def create_app(
    settings: Settings | None = None, provider: SuggestionProvider | None = None
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_db_engine(settings.database_url)
        if settings.auto_migrate:
            run_migrations(engine)
        factory = make_session_factory(engine)
        if settings.seed_demo_data:
            with factory() as session:
                if seed_demo_data(session):
                    log.info("demo_data_seeded")
        timeout = httpx.Timeout(settings.openai_timeout_seconds, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            active = provider or build_provider(settings, client)
            app.state.resolveai = AppState(
                settings=settings,
                engine=engine,
                session_factory=factory,
                provider=active,
                write_limiter=SlidingWindowRateLimiter(settings.rate_limit_writes_per_minute),
                suggest_limiter=SlidingWindowRateLimiter(settings.rate_limit_suggest_per_minute),
            )
            log.info("startup", suggestion_mode=active.mode, environment=settings.environment)
            try:
                yield
            finally:
                engine.dispose()

    app = FastAPI(
        title="ResolveAI",
        summary="Central de atendimento com sugestões de resposta ligadas às fontes consultadas.",
        version=health.APP_VERSION,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    install_error_handlers(app)

    for module in (tickets, articles, suggest, replies, health):
        app.include_router(module.router)

    if settings.docs_enabled:

        @app.get("/docs", include_in_schema=False)
        def docs() -> HTMLResponse:
            return health.docs_response("/openapi.json", "ResolveAI — API")

    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    def api_not_found(path: str) -> None:
        raise ApiError(404, "Rota da API não encontrada.")

    if settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="static")
    else:
        log.warning("static_dir_missing", path=str(settings.static_dir))

    # Ordem: o último adicionado é o mais externo.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.hsts_enabled)
    app.add_middleware(RequestContextMiddleware)
    return app
