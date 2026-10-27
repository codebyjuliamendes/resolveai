"""Validação de citações: o rascunho só pode citar fontes efetivamente recuperadas."""

from __future__ import annotations

import re
from dataclasses import dataclass

_CITATION_RE = re.compile(r"\[(\d{1,3})\]")
_SPACES_BEFORE_PUNCT_RE = re.compile(r"[ \t]+([.,;:!?])")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")


@dataclass(frozen=True, slots=True)
class CitationCheck:
    text: str
    cited_indices: tuple[int, ...]
    removed: tuple[int, ...]


def validate_citations(draft: str, source_count: int) -> CitationCheck:
    """Remove marcadores [n] fora de 1..source_count e lista os índices válidos citados."""
    cited: dict[int, None] = {}
    removed: list[int] = []

    def _replace(match: re.Match[str]) -> str:
        index = int(match.group(1))
        if 1 <= index <= source_count:
            cited.setdefault(index, None)
            return match.group(0)
        removed.append(index)
        return ""

    cleaned = _CITATION_RE.sub(_replace, draft)
    if removed:
        cleaned = _SPACES_BEFORE_PUNCT_RE.sub(r"\1", cleaned)
        cleaned = _MULTI_SPACE_RE.sub(" ", cleaned)
    return CitationCheck(text=cleaned.strip(), cited_indices=tuple(cited), removed=tuple(removed))
