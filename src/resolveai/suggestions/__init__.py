"""Camada de sugestões de resposta."""

from resolveai.suggestions.base import (
    Source,
    SuggestionProvider,
    SuggestionProviderError,
    SuggestionRequest,
)
from resolveai.suggestions.service import SuggestionResult, build_suggestion

__all__ = [
    "Source",
    "SuggestionProvider",
    "SuggestionProviderError",
    "SuggestionRequest",
    "SuggestionResult",
    "build_suggestion",
]
