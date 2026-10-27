"""CLI: `resolveai serve` (migra, popula a demo e sobe o servidor) e `resolveai migrate`."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import uvicorn

from resolveai.config import get_settings
from resolveai.db import create_db_engine
from resolveai.log_config import configure_logging
from resolveai.migrate import run_migrations


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="resolveai")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Inicia o servidor HTTP.")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--reload", action="store_true", help="Recarrega ao editar (dev).")
    sub.add_parser("migrate", help="Aplica as migrações do banco.")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)

    if args.command == "migrate":
        engine = create_db_engine(settings.database_url)
        try:
            run_migrations(engine)
        finally:
            engine.dispose()
        return

    uvicorn.run(
        "resolveai.main:app",
        host=args.host or settings.host,
        port=args.port or settings.port,
        reload=args.reload,
        proxy_headers=True,
        server_header=False,
        access_log=False,
        log_config=None,
    )
