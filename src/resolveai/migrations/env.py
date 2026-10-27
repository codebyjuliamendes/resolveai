"""Ambiente do Alembic: usa a conexão recebida programaticamente ou a URL das settings."""

from __future__ import annotations

from alembic import context
from sqlalchemy import Connection

import resolveai.models  # noqa: F401 - registra as tabelas no metadata
from resolveai.config import get_settings
from resolveai.db import Base, create_db_engine

config = context.config
target_metadata = Base.metadata


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url") or get_settings().database_url
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if isinstance(connection, Connection):
        _run(connection)
        return
    url = config.get_main_option("sqlalchemy.url") or get_settings().database_url
    engine = create_db_engine(url)
    try:
        with engine.connect() as conn:
            _run(conn)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
