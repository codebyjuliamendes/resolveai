from __future__ import annotations

from fastapi.testclient import TestClient


def _ticket(client: TestClient, ticket_id: int) -> dict[str, object]:
    ticket: dict[str, object] = next(
        t for t in client.get("/api/tickets").json() if t["id"] == ticket_id
    )
    return ticket


def test_review_flow_suggest_edit_and_register(client: TestClient) -> None:
    suggestion = client.post("/api/suggest", json={"ticketId": 1}).json()
    edited = suggestion["draft"].replace("Entendo sua dúvida", "Sinto muito pelo transtorno")
    source_ids = [s["id"] for s in suggestion["sources"]]
    response = client.post(
        "/api/replies", json={"ticketId": 1, "body": edited, "sourceIds": source_ids}
    )
    assert response.status_code == 201
    assert response.json() == {"ok": True}
    ticket = _ticket(client, 1)
    assert ticket["status"] == "resolvido"
    replies = ticket["replies"]
    assert isinstance(replies, list)
    assert replies[0]["body"] == edited
    assert replies[0]["sourceIds"] == source_ids
    assert "\n\nFontes:" in replies[0]["body"]


def test_reply_without_sources(client: TestClient) -> None:
    response = client.post("/api/replies", json={"ticketId": 3, "body": "Vamos verificar."})
    assert response.status_code == 201
    replies = _ticket(client, 3)["replies"]
    assert isinstance(replies, list)
    assert replies[0]["sourceIds"] == []


def test_duplicate_source_ids_are_collapsed(client: TestClient) -> None:
    client.post("/api/replies", json={"ticketId": 3, "body": "Resposta.", "sourceIds": [4, 4, 1]})
    replies = _ticket(client, 3)["replies"]
    assert isinstance(replies, list)
    assert replies[0]["sourceIds"] == [4, 1]


def test_unknown_source_ids_are_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/replies", json={"ticketId": 1, "body": "Resposta válida.", "sourceIds": [1, 999]}
    )
    assert response.status_code == 400
    assert "999" in response.json()["error"]
    assert _ticket(client, 1)["status"] == "novo"


def test_resolved_ticket_cannot_receive_another_reply(client: TestClient) -> None:
    assert client.post("/api/replies", json={"ticketId": 3, "body": "Primeira."}).status_code == 201
    second = client.post("/api/replies", json={"ticketId": 3, "body": "Segunda."})
    assert second.status_code == 409


def test_reply_validation(client: TestClient) -> None:
    short = client.post("/api/replies", json={"ticketId": 1, "body": "  ok "})
    assert short.status_code == 400
    assert short.json()["error"] == "A resposta deve ter entre 4 e 1.600 caracteres."
    long = client.post("/api/replies", json={"ticketId": 1, "body": "x" * 1601})
    assert long.status_code == 400
    missing = client.post("/api/replies", json={"ticketId": 999, "body": "Resposta."})
    assert missing.status_code == 404
    too_many = client.post(
        "/api/replies", json={"ticketId": 1, "body": "Resposta.", "sourceIds": list(range(1, 12))}
    )
    assert too_many.status_code == 400
