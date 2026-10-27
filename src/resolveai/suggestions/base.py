"""Contratos da camada de sugestões."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Source:
    """Artigo recuperado; `index` é o número usado na citação ([1], [2]...)."""

    index: int
    id: int
    title: str
    category: str
    body: str
    score: float = 0.0


@dataclass(frozen=True, slots=True)
class SuggestionRequest:
    question: str
    subject: str | None
    customer_name: str | None
    sources: tuple[Source, ...]
    query_terms: tuple[str, ...] = ()


class SuggestionProviderError(Exception):
    """Falha do provedor; a mensagem é técnica e não deve ir ao cliente final."""


@runtime_checkable
class SuggestionProvider(Protocol):
    """Gera o texto do rascunho a partir das fontes já recuperadas."""

    @property
    def mode(self) -> str: ...

    async def generate(self, request: SuggestionRequest) -> str: ...
