"""Ponto de entrada ASGI: `uvicorn resolveai.main:app`."""

from resolveai.app import create_app
from resolveai.config import get_settings
from resolveai.log_config import configure_logging

_settings = get_settings()
configure_logging(_settings.log_level, _settings.log_format)
app = create_app(_settings)
