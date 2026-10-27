"""Sugestão de rascunho: recupera fontes, gera o texto e valida as citações."""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from resolveai.api.deps import AppState, StateDep, SuggestLimit
from resolveai.errors import ApiError
from resolveai.models import Ticket
from resolveai.schemas import SourceOut, SuggestIn, SuggestionOut
from resolveai.search import SearchHit, keep_relevant, query_terms, search_articles
from resolveai.suggestions import SuggestionProviderError, build_suggestion

router = APIRouter(prefix="/api", tags=["sugestões"])
log = structlog.get_logger(__name__)

MAX_SOURCES = 3
# Fontes com score BM25 abaixo de 30% da melhor não são enviadas como contexto.
RELEVANCE_RATIO = 0.3
MESSAGE_REQUIRED = "Informe a mensagem do cliente."
PROVIDER_FAILED = (
    "Não foi possível gerar a sugestão agora. Tente novamente ou escreva uma resposta manualmente."
)


@dataclass(frozen=True, slots=True)
class _Context:
    question: str
    subject: str | None
    customer: str | None
    hits: list[SearchHit]
    terms: list[str]


def _load_context(state: AppState, payload: SuggestIn) -> _Context:
    with state.session_factory() as session:
        ticket: Ticket | None = None
        if payload.ticket_id is not None:
            ticket = session.get(Ticket, payload.ticket_id)
            if ticket is None:
                raise ApiError(404, "Chamado não encontrado.")
        question = payload.message or (ticket.message if ticket else "")
        if not 4 <= len(question) <= 1200:
            raise ApiError(400, MESSAGE_REQUIRED)
        subject = ticket.subject if ticket else None
        query = f"{subject or ''} {question}"
        return _Context(
            question=question,
            subject=subject,
            customer=ticket.customer if ticket else None,
            hits=keep_relevant(search_articles(session, query, limit=MAX_SOURCES), RELEVANCE_RATIO),
            terms=query_terms(query),
        )


@router.post("/suggest", response_model=SuggestionOut, name="suggest", dependencies=[SuggestLimit])
async def suggest(payload: SuggestIn, state: StateDep) -> SuggestionOut:
    ctx = await run_in_threadpool(_load_context, state, payload)
    try:
        result = await build_suggestion(
            state.provider,
            question=ctx.question,
            subject=ctx.subject,
            customer_name=ctx.customer,
            hits=ctx.hits,
            terms=ctx.terms,
        )
    except SuggestionProviderError as exc:
        log.warning("suggestion_failed", mode=state.provider.mode, reason=str(exc))
        raise ApiError(502, PROVIDER_FAILED) from exc
    log.info(
        "suggestion_created",
        mode=result.mode,
        source_ids=[s.id for s in result.sources],
        cited_source_ids=list(result.cited_source_ids),
    )
    return SuggestionOut(
        draft=result.draft,
        sources=[SourceOut(id=s.id, title=s.title, category=s.category) for s in result.sources],
        cited_source_ids=list(result.cited_source_ids),
        mode=result.mode,
    )
