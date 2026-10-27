"""Recuperação de artigos com SQLite FTS5 (BM25) e normalização pt-BR."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

MIN_TERM_LENGTH = 3
MAX_QUERY_TERMS = 24
# Pesos BM25 por coluna: título, categoria, corpo.
BM25_WEIGHTS = (4.0, 1.5, 1.0)

# Palavras frequentes que não ajudam a escolher um artigo (já normalizadas).
STOPWORDS: frozenset[str] = frozenset(
    """
    about agora ainda ali and aos apenas aquela aquele aqui are assim ate boa bom but cada
    can coisa com como contra could das dela dele depois desde dia did does dos ela elas ele
    eles entao entre era essa esse esta estao estava este estou favor foi for from gostaria
    had has have hello help hey hoje how isso isto mais mas mesmo meu meus minha minhas
    muito nada nao nas nem noite nos nossa nosso not nunca obrigada obrigado ola onde ontem
    outra outro para pela pelas pelo pelos please pois por porque preciso quais qual quando
    que quem queria quero sao sem sempre seu seus should sim sobre sua suas tambem tarde tem
    ter thanks that the their there they this tinha toda todas todo todos tudo uma umas uns
    vai vez voce voces was what when where which who why will with would you your
    """.split()
)

_TERM_RE = re.compile(r"[a-z0-9]+")
_STEM_MIN = 5


def normalize(value: str) -> str:
    """Minúsculas e sem acentos: 'Devolução' -> 'devolucao'."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def query_terms(value: str) -> list[str]:
    """Termos relevantes, sem repetição e na ordem em que aparecem."""
    seen: dict[str, None] = {}
    for term in _TERM_RE.findall(normalize(value)):
        if len(term) >= MIN_TERM_LENGTH and term not in STOPWORDS:
            seen.setdefault(term, None)
    return list(seen)[:MAX_QUERY_TERMS]


def stem(term: str) -> str:
    """Radical simples para flexões (entregue/entrega, pedido/pedidos)."""
    if len(term) <= _STEM_MIN or term.isdigit():
        return term
    return term[: max(_STEM_MIN, len(term) - 2)]


def build_match_expression(terms: list[str]) -> str:
    # Os termos contêm apenas [a-z0-9]; as aspas evitam operadores do FTS5.
    return " OR ".join(f'"{stem(term)}"*' for term in terms)


def term_matches(term: str, normalized_text: str) -> bool:
    return re.search(rf"\b{re.escape(stem(term))}", normalized_text) is not None


@dataclass(frozen=True, slots=True)
class SearchHit:
    id: int
    title: str
    category: str
    body: str
    score: float


_SEARCH_SQL = text(
    f"""
    SELECT a.id, a.title, a.category, a.body,
           bm25(articles_fts, {BM25_WEIGHTS[0]}, {BM25_WEIGHTS[1]}, {BM25_WEIGHTS[2]}) AS rank
    FROM articles_fts
    JOIN articles AS a ON a.id = articles_fts.rowid
    WHERE articles_fts MATCH :expr
    ORDER BY rank ASC, a.id ASC
    LIMIT :limit
    """  # noqa: S608 - apenas constantes numéricas são interpoladas
)


def keep_relevant(hits: list[SearchHit], ratio: float) -> list[SearchHit]:
    """Descarta resultados muito abaixo do melhor (correspondências incidentais)."""
    if not hits:
        return hits
    floor = hits[0].score * ratio
    return [h for h in hits if h.score >= floor]


def search_articles(session: Session, query: str, limit: int = 3) -> list[SearchHit]:
    """Artigos mais relevantes para `query`; lista vazia se não houver termos úteis."""
    terms = query_terms(query)
    if not terms or limit < 1:
        return []
    rows = session.execute(
        _SEARCH_SQL, {"expr": build_match_expression(terms), "limit": limit}
    ).all()
    # bm25() é negativo (menor = melhor); expomos um score positivo e estável.
    return [
        SearchHit(
            id=row.id,
            title=row.title,
            category=row.category,
            body=row.body,
            score=round(-float(row.rank), 6),
        )
        for row in rows
    ]
