from __future__ import annotations

import pytest

from resolveai.suggestions.base import Source, SuggestionRequest
from resolveai.suggestions.template import TemplateSuggestionProvider


def _source(index: int, body: str, score: float = 1.0, title: str | None = None) -> Source:
    return Source(
        index=index,
        id=100 + index,
        title=title or f"Artigo {index}",
        category="Geral",
        body=body,
        score=score,
    )


def _request(*sources: Source, terms: tuple[str, ...] = ("estorno",)) -> SuggestionRequest:
    return SuggestionRequest(
        question="Quando cai o estorno?",
        subject=None,
        customer_name="Pedro Alves",
        sources=sources,
        query_terms=terms,
    )


async def test_cites_primary_source_and_greets_by_first_name() -> None:
    draft = await TemplateSuggestionProvider().generate(
        _request(_source(1, "O estorno volta ao cartão original.", title="Prazo de estorno."))
    )
    assert draft.startswith("Olá, Pedro!")
    assert "O estorno volta ao cartão original. [1]" in draft
    assert draft.endswith("Fontes: [1] Prazo de estorno.")


async def test_is_deterministic() -> None:
    request = _request(_source(1, "O estorno volta ao cartão."), _source(2, "Estorno em dias."))
    provider = TemplateSuggestionProvider()
    assert await provider.generate(request) == await provider.generate(request)


async def test_adds_relevant_secondary_excerpt() -> None:
    draft = await TemplateSuggestionProvider().generate(
        _request(
            _source(1, "O estorno volta ao cartão.", score=2.0),
            _source(2, "Texto genérico. O estorno pode levar dias úteis.", score=1.5),
        )
    )
    assert "Também vale considerar: O estorno pode levar dias úteis. [2]" in draft
    assert "Fontes: [1] Artigo 1; [2] Artigo 2." in draft


async def test_skips_weak_secondary_sources() -> None:
    draft = await TemplateSuggestionProvider().generate(
        _request(
            _source(1, "O estorno volta ao cartão.", score=4.0),
            _source(2, "O estorno pode levar dias.", score=1.0),
        )
    )
    assert "[2]" not in draft


async def test_long_articles_are_excerpted_by_relevance() -> None:
    filler = " ".join(f"Frase de contexto número {i}." for i in range(60))
    body = f"{filler} O estorno aparece em até duas faturas. {filler}"
    draft = await TemplateSuggestionProvider().generate(_request(_source(1, body)))
    assert "O estorno aparece em até duas faturas." in draft
    assert len(draft) < 800


async def test_requires_sources() -> None:
    with pytest.raises(ValueError, match="fonte"):
        await TemplateSuggestionProvider().generate(_request())
