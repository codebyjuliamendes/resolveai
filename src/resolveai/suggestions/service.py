"""Orquestra recuperação, geração e validação de citações."""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from resolveai.search import SearchHit
from resolveai.suggestions.base import (
    Source,
    SuggestionProvider,
    SuggestionProviderError,
    SuggestionRequest,
)
from resolveai.suggestions.citations import validate_citations

log = structlog.get_logger(__name__)

NO_SOURCE_MODE = "sem-fonte"
NO_SOURCE_DRAFT = (
    "Não encontrei um artigo da base que responda com segurança. Consulte a loja ou "
    "encaminhe o caso para uma pessoa responsável."
)


@dataclass(frozen=True, slots=True)
class SuggestionResult:
    draft: str
    sources: tuple[Source, ...]
    cited_source_ids: tuple[int, ...]
    mode: str


async def build_suggestion(
    provider: SuggestionProvider,
    *,
    question: str,
    subject: str | None,
    customer_name: str | None,
    hits: list[SearchHit],
    terms: list[str],
) -> SuggestionResult:
    if not hits:
        return SuggestionResult(
            draft=NO_SOURCE_DRAFT, sources=(), cited_source_ids=(), mode=NO_SOURCE_MODE
        )
    sources = tuple(
        Source(index=i, id=h.id, title=h.title, category=h.category, body=h.body, score=h.score)
        for i, h in enumerate(hits, start=1)
    )
    request = SuggestionRequest(
        question=question,
        subject=subject,
        customer_name=customer_name,
        sources=sources,
        query_terms=tuple(terms),
    )
    raw = await provider.generate(request)
    check = validate_citations(raw, len(sources))
    if not check.text:
        raise SuggestionProviderError("O rascunho ficou vazio após a validação.")
    if check.removed:
        log.warning("suggestion_invalid_citations", removed=list(check.removed), mode=provider.mode)
    by_index = {s.index: s.id for s in sources}
    return SuggestionResult(
        draft=check.text,
        sources=sources,
        cited_source_ids=tuple(by_index[i] for i in check.cited_indices),
        mode=provider.mode,
    )
