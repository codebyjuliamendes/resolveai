from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from resolveai.config import Settings
from resolveai.ratelimit import SlidingWindowRateLimiter
from tests.conftest import ClientFactory

PUBLIC = Path(__file__).resolve().parents[1] / "public"


def test_health(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["suggestionMode"] == "base-local"


def test_serves_frontend(client: TestClient) -> None:
    index = client.get("/")
    assert index.status_code == 200
    assert "ResolveAI" in index.text
    for asset in ("/app.js", "/theme.js", "/styles.css", "/mark-ra.svg"):
        assert client.get(asset).status_code == 200, asset


def test_frontend_has_no_inline_scripts_or_styles() -> None:
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")
    assert "style=" not in html
    assert "<style" not in html
    assert "<script>" not in html
    assert "onclick=" not in html
    js = (PUBLIC / "app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in js
    assert ".style." not in js


def test_seed_runs_once(client_factory: ClientFactory) -> None:
    first = client_factory()
    first.post(
        "/api/tickets",
        json={"customer": "Ana Souza", "email": "a@b.cd", "subject": "Teste", "message": "Teste"},
    )
    second = client_factory()
    assert len(second.get("/api/tickets").json()) == 4
    assert len(second.get("/api/articles").json()) == 5


def test_no_seed_when_disabled(client_factory: ClientFactory) -> None:
    client = client_factory(seed_demo_data=False)
    assert client.get("/api/articles").json() == []


def test_upgrades_a_legacy_node_database(tmp_path: Path, client_factory: ClientFactory) -> None:
    """Banco criado pela versão Node: o Alembic adota as tabelas e indexa os artigos."""
    db = tmp_path / "test.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE articles(id INTEGER PRIMARY KEY,title TEXT NOT NULL UNIQUE,
          category TEXT NOT NULL,body TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE tickets(id INTEGER PRIMARY KEY,customer TEXT NOT NULL,email TEXT NOT NULL,
          subject TEXT NOT NULL,message TEXT NOT NULL,category TEXT NOT NULL,priority TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('novo','em_atendimento','resolvido')),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE replies(id INTEGER PRIMARY KEY,
          ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
          body TEXT NOT NULL,source_ids TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE article_versions(id INTEGER PRIMARY KEY,
          article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
          version INTEGER NOT NULL,title TEXT NOT NULL,category TEXT NOT NULL,body TEXT NOT NULL,
          editor TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(article_id,version));
        INSERT INTO articles(title,category,body,updated_at)
          VALUES('Troca de senha','Conta','Use a tela de recuperação de conta.',
          '2025-01-02 10:00:00');
        INSERT INTO tickets(customer,email,subject,message,category,priority,status,created_at)
          VALUES('Rita Lee','r@l.test','Senha','Esqueci minha senha.','Conta','Normal','resolvido',
          '2025-01-02 11:00:00');
        INSERT INTO replies(ticket_id,body,source_ids,created_at)
          VALUES(1,'Use a recuperação.','[1]','2025-01-02 12:00:00');
        """
    )
    conn.commit()
    conn.close()

    client = client_factory()
    tickets = client.get("/api/tickets").json()
    assert tickets[0]["createdAt"] == "2025-01-02T11:00:00Z"
    assert tickets[0]["replies"][0]["sourceIds"] == [1]
    assert len(client.get("/api/articles").json()) == 1  # sem seed: já havia artigos
    results = client.get("/api/search", params={"q": "recuperacao"}).json()["results"]
    assert [r["title"] for r in results] == ["Troca de senha"]


def test_settings_treat_empty_openai_vars_as_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_MODEL", " ")
    settings = Settings(_env_file=None)
    assert settings.openai_enabled is False


def test_settings_keep_secret_out_of_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-hidden")
    monkeypatch.setenv("OPENAI_MODEL", "modelo")
    settings = Settings(_env_file=None)
    assert settings.openai_enabled is True
    assert isinstance(settings.openai_api_key, SecretStr)
    assert "sk-hidden" not in repr(settings)


def test_settings_accept_legacy_database_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "legado.sqlite"))
    assert Settings(_env_file=None).database_url == f"sqlite:///{tmp_path / 'legado.sqlite'}"


def test_rate_limiter_window() -> None:
    now = [0.0]
    limiter = SlidingWindowRateLimiter(2, window_seconds=10, clock=lambda: now[0])
    assert limiter.hit("a") is None
    assert limiter.hit("a") is None
    assert limiter.hit("a") == 10
    assert limiter.hit("b") is None
    now[0] = 10.5
    assert limiter.hit("a") is None
