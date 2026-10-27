from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

VALID = {
    "customer": "Ana Souza",
    "email": "ana@email.test",
    "subject": "Pedido atrasado",
    "message": "Meu pedido está atrasado há uma hora.",
    "category": "Entrega",
    "priority": "Alta",
}


def test_lists_seeded_tickets_with_high_priority_first(client: TestClient) -> None:
    tickets = client.get("/api/tickets").json()
    assert [t["customer"] for t in tickets] == ["Camila Rocha", "Lia Costa", "Pedro Alves"]
    first = tickets[0]
    assert set(first) == {
        "id", "customer", "email", "subject", "message", "category", "priority", "status",
        "createdAt", "updatedAt", "replies",
    }  # fmt: skip
    assert datetime.fromisoformat(first["createdAt"]).tzinfo is not None
    assert first["replies"] == []


def test_filters_by_status_and_ignores_unknown_status(client: TestClient) -> None:
    assert {t["status"] for t in client.get("/api/tickets?status=novo").json()} == {"novo"}
    assert len(client.get("/api/tickets?status=qualquer").json()) == 3


def test_creates_ticket_with_cleaned_fields(client: TestClient) -> None:
    created = client.post(
        "/api/tickets", json={**VALID, "customer": "  Ana   Souza ", "category": "  "}
    )
    assert created.status_code == 201
    ticket = next(t for t in client.get("/api/tickets").json() if t["id"] == created.json()["id"])
    assert ticket["customer"] == "Ana Souza"
    assert ticket["category"] == "Geral"
    assert ticket["status"] == "novo"


def test_unknown_priority_falls_back_to_normal(client: TestClient) -> None:
    created = client.post("/api/tickets", json={**VALID, "priority": "Urgentíssima"})
    ticket = next(t for t in client.get("/api/tickets").json() if t["id"] == created.json()["id"])
    assert ticket["priority"] == "Normal"


@pytest.mark.parametrize(
    "override",
    [
        {"email": "sem-arroba"},
        {"email": "a b@c.d"},
        {"customer": "Al"},
        {"subject": "x" * 101},
        {"message": "x" * 1201},
        {"message": "   "},
        {"category": "x" * 61},
    ],
)
def test_rejects_invalid_ticket(client: TestClient, override: dict[str, str]) -> None:
    response = client.post("/api/tickets", json={**VALID, **override})
    assert response.status_code == 400
    assert response.json()["error"] == "Confira nome, e-mail, assunto e mensagem do chamado."
    assert response.json()["details"]


def test_updates_status(client: TestClient) -> None:
    assert client.patch("/api/tickets/1/status", json={"status": "em_atendimento"}).json() == {
        "ok": True
    }
    ticket = next(t for t in client.get("/api/tickets").json() if t["id"] == 1)
    assert ticket["status"] == "em_atendimento"


def test_status_errors(client: TestClient) -> None:
    bad = client.patch("/api/tickets/1/status", json={"status": "fechado"})
    assert bad.status_code == 400
    assert bad.json()["error"] == "Status inválido."
    missing = client.patch("/api/tickets/999/status", json={"status": "novo"})
    assert missing.status_code == 404
    assert missing.json()["error"] == "Chamado não encontrado."
    assert client.patch("/api/tickets/abc/status", json={"status": "novo"}).status_code == 404
