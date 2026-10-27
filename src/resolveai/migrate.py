"""Execução programática das migrações Alembic."""

from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine


def alembic_config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", "resolveai:migrations")
    cfg.set_main_option("path_separator", "os")
    return cfg


def run_migrations(engine: Engine) -> None:
    cfg = alembic_config()
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
