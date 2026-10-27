"""Chamados: listagem, criação e status."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import case, select
from sqlalchemy.orm import selectinload

from resolveai.api.deps import SessionDep, WriteLimit
from resolveai.db import utcnow
from resolveai.errors import ApiError
from resolveai.models import Priority, Ticket, TicketStatus
from resolveai.schemas import Created, Ok, StatusUpdate, TicketCreate, TicketOut

router = APIRouter(prefix="/api/tickets", tags=["chamados"])

TICKET_NOT_FOUND = "Chamado não encontrado."


@router.get("", response_model=list[TicketOut], name="list_tickets")
def list_tickets(
    session: SessionDep,
    status: Annotated[str | None, Query(max_length=32)] = None,
) -> list[Ticket]:
    stmt = (
        select(Ticket)
        .options(selectinload(Ticket.replies))
        .order_by(case((Ticket.priority == Priority.ALTA.value, 0), else_=1), Ticket.id.desc())
    )
    # Status desconhecido é ignorado (lista tudo), como na versão anterior.
    if status and status.strip() in {s.value for s in TicketStatus}:
        stmt = stmt.where(Ticket.status == status.strip())
    return list(session.scalars(stmt))


@router.post(
    "", status_code=201, response_model=Created, name="create_ticket", dependencies=[WriteLimit]
)
def create_ticket(payload: TicketCreate, session: SessionDep) -> Created:
    ticket = Ticket(
        customer=payload.customer,
        email=payload.email,
        subject=payload.subject,
        message=payload.message,
        category=payload.category,
        priority=payload.priority.value,
        status=TicketStatus.NOVO.value,
    )
    session.add(ticket)
    session.commit()
    return Created(id=ticket.id)


@router.patch(
    "/{ticket_id}/status",
    response_model=Ok,
    name="update_ticket_status",
    dependencies=[WriteLimit],
)
def update_ticket_status(ticket_id: int, payload: StatusUpdate, session: SessionDep) -> Ok:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise ApiError(404, TICKET_NOT_FOUND)
    ticket.status = payload.status.value
    ticket.updated_at = utcnow()
    session.commit()
    return Ok()
