"""Provedor determinístico: monta o rascunho com trechos das fontes, sem chamadas externas."""

from __future__ import annotations

import re

from resolveai.search import normalize, term_matches
from resolveai.suggestions.base import Source, SuggestionRequest

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
FULL_BODY_LIMIT = 600
MAX_PRIMARY_SENTENCES = 3
# Uma fonte secundária só entra no texto se for quase tão relevante quanto a principal.
SECONDARY_RATIO = 0.5


def _sentences(body: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(" ".join(body.split())) if s.strip()]


def _overlap(sentence: str, terms: tuple[str, ...]) -> int:
    normalized = normalize(sentence)
    return sum(1 for term in terms if term_matches(term, normalized))


def _primary_excerpt(source: Source, terms: tuple[str, ...]) -> str:
    body = " ".join(source.body.split())
    if len(body) <= FULL_BODY_LIMIT:
        return body
    sentences = _sentences(body)
    ranked = sorted(range(len(sentences)), key=lambda i: (-_overlap(sentences[i], terms), i))[
        :MAX_PRIMARY_SENTENCES
    ]
    return " ".join(sentences[i] for i in sorted(ranked))


def _best_sentence(source: Source, terms: tuple[str, ...]) -> str | None:
    best: tuple[int, int, str] | None = None
    for position, sentence in enumerate(_sentences(source.body)):
        score = _overlap(sentence, terms)
        if score and (best is None or (-score, position) < (-best[0], best[1])):
            best = (score, position, sentence)
    return best[2] if best else None


def _with_citation(excerpt: str, index: int) -> str:
    return f"{excerpt.rstrip()} [{index}]"


class TemplateSuggestionProvider:
    """Modo `base-local`: não é um modelo de linguagem; reaproveita o texto dos artigos."""

    @property
    def mode(self) -> str:
        return "base-local"

    async def generate(self, request: SuggestionRequest) -> str:
        if not request.sources:
            raise ValueError("O provedor de template exige ao menos uma fonte.")
        terms = request.query_terms
        first_name = (request.customer_name or "").split(" ")[0]
        greeting = f"Olá, {first_name}!" if first_name else "Olá!"
        primary = request.sources[0]
        paragraphs = [
            f"{greeting} Entendo sua dúvida e vou ajudar.",
            _with_citation(_primary_excerpt(primary, terms), primary.index),
        ]
        cited = [primary]
        for source in request.sources[1:]:
            if source.score < primary.score * SECONDARY_RATIO:
                continue
            sentence = _best_sentence(source, terms)
            if sentence and sentence not in paragraphs[1]:
                paragraphs.append(
                    _with_citation(f"Também vale considerar: {sentence}", source.index)
                )
                cited.append(source)
                break
        paragraphs.append(
            "Se precisar, podemos conferir os detalhes do seu caso com a equipe responsável."
        )
        references = "; ".join(f"[{s.index}] {s.title.rstrip('.')}" for s in cited)
        return "\n\n".join(paragraphs) + f"\n\nFontes: {references}."
