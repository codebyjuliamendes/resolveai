"""Fixtures: app com banco temporário e provedor de sugestão falso (sem rede)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from resolveai.app import create_app
from resolveai.config import Settings
from resolveai.db import create_db_engine, make_session_factory
from resolveai.migrate import run_migrations
from resolveai.suggestions import SuggestionProviderError, SuggestionRequest


class FakeProvider:
    """Devolve um texto fixo (ou falha) e guarda as requisições recebidas."""

    def __init__(self, reply: str = "Rascunho de teste [1].", *, fail: bool = False) -> None:
        self.reply = reply
        self.fail = fail
        self.requests: list[SuggestionRequest] = []

    @property
    def mode(self) -> str:
        return "fake"

    async def generate(self, request: SuggestionRequest) -> str:
        self.requests.append(request)
        if self.fail:
            raise SuggestionProviderError("falha simulada")
        return self.reply


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "test",
        "database_url": f"sqlite:///{tmp_path / 'test.sqlite'}",
        "rate_limit_enabled": False,
        "openai_api_key": None,
        "openai_model": None,
        "seed_demo_data": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


ClientFactory = Callable[..., TestClient]


@pytest.fixture
def client_factory(tmp_path: Path) -> Iterator[ClientFactory]:
    clients: list[TestClient] = []

    def factory(provider: Any = None, **overrides: Any) -> TestClient:
        app = create_app(make_settings(tmp_path, **overrides), provider=provider)
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(client_factory: ClientFactory) -> TestClient:
    """App com o provedor determinístico padrão (modo base-local)."""
    return client_factory()


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def fake_client(client_factory: ClientFactory, fake_provider: FakeProvider) -> TestClient:
    return client_factory(provider=fake_provider)


@pytest.fixture
def empty_session(tmp_path: Path) -> Iterator[Session]:
    """Sessão em banco migrado e sem dados de demonstração."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'search.sqlite'}")
    run_migrations(engine)
    with make_session_factory(engine)() as session:
        yield session
    engine.dispose()
