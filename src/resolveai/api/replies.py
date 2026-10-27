"""Registro da resposta revisada pelo agente."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from resolveai.api.deps import SessionDep, WriteLimit
from resolveai.db import utcnow
from resolveai.errors import ApiError
from resolveai.models import Article, Reply, Ticket, TicketStatus
from resolveai.schemas import Ok, ReplyIn

router = APIRouter(prefix="/api", tags=["respostas"])


@router.post(
    "/replies", status_code=201, response_model=Ok, name="create_reply", dependencies=[WriteLimit]
)
def create_reply(payload: ReplyIn, session: SessionDep) -> Ok:
    ticket = session.get(Ticket, payload.ticket_id)
    if ticket is None:
        raise ApiError(404, "Chamado não encontrado.")
    if ticket.status == TicketStatus.RESOLVIDO.value:
        raise ApiError(409, "Este chamado já foi resolvido.")
    source_ids = list(dict.fromkeys(payload.source_ids))
    if source_ids:
        found = set(session.scalars(select(Article.id).where(Article.id.in_(source_ids))))
        if missing := [i for i in source_ids if i not in found]:
            raise ApiError(400, f"Fonte inválida: artigo {missing[0]} não existe.")
    now = utcnow()
    session.add(
        Reply(ticket_id=ticket.id, body=payload.body, source_ids=source_ids, created_at=now)
    )
    ticket.status = TicketStatus.RESOLVIDO.value
    ticket.updated_at = now
    session.commit()
    return Ok()
