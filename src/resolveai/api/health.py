"""Health check e documentação interativa com CSP própria."""

from __future__ import annotations

import base64
import hashlib
import re
from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text

from resolveai.api.deps import StateDep
from resolveai.schemas import HealthOut

router = APIRouter(tags=["operação"])

try:
    APP_VERSION = version("resolveai")
except PackageNotFoundError:  # pragma: no cover - execução sem instalação
    APP_VERSION = "0.0.0"


@router.get("/api/health", response_model=HealthOut, name="health")
def health(state: StateDep) -> JSONResponse:
    database: str = "ok"
    try:
        with state.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        database = "error"
    body = HealthOut(
        status="ok" if database == "ok" else "degraded",
        database="ok" if database == "ok" else "error",
        suggestion_mode=state.provider.mode,
        version=APP_VERSION,
    )
    return JSONResponse(
        body.model_dump(by_alias=True), status_code=200 if database == "ok" else 503
    )


_INLINE_SCRIPT_RE = re.compile(r"<script>(.*?)</script>", re.DOTALL)


def docs_response(openapi_url: str, title: str) -> HTMLResponse:
    """Swagger UI com CSP baseada em hash do script inline (sem 'unsafe-inline')."""
    html = get_swagger_ui_html(openapi_url=openapi_url, title=title)
    body = bytes(html.body).decode()
    hashes = " ".join(
        "'sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode() + "'"
        for s in _INLINE_SCRIPT_RE.findall(body)
    )
    csp = "; ".join(
        (
            "default-src 'self'",
            f"script-src 'self' https://cdn.jsdelivr.net {hashes}",
            "style-src 'self' https://cdn.jsdelivr.net",
            "img-src 'self' data: https://fastapi.tiangolo.com",
            "connect-src 'self'",
            "object-src 'none'",
            "base-uri 'none'",
            "frame-ancestors 'none'",
        )
    )
    return HTMLResponse(body, headers={"Content-Security-Policy": csp})
