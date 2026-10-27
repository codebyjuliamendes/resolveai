from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient

from tests.conftest import ClientFactory

TICKET = {
    "customer": "Ana Souza",
    "email": "ana@email.test",
    "subject": "Pedido atrasado",
    "message": "Meu pedido está atrasado.",
}


def test_security_headers_on_api_and_static(client: TestClient) -> None:
    for path in ("/api/health", "/"):
        headers = client.get(path).headers
        csp = headers["content-security-policy"]
        assert "script-src 'self'" in csp
        assert "unsafe-inline" not in csp
        assert "frame-ancestors 'none'" in csp
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"
        assert headers["referrer-policy"] == "no-referrer"
    assert client.get("/api/health").headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in client.get("/").headers


def test_hsts_when_enabled(client_factory: ClientFactory) -> None:
    client = client_factory(hsts_enabled=True)
    assert "max-age" in client.get("/").headers["strict-transport-security"]


def test_request_id_is_generated_or_propagated(client: TestClient) -> None:
    generated = client.get("/api/health").headers["x-request-id"]
    assert len(generated) == 32
    assert (
        client.get("/api/health", headers={"X-Request-ID": "proxy-id-123"}).headers["x-request-id"]
        == "proxy-id-123"
    )
    unsafe = client.get("/api/health", headers={"X-Request-ID": "<script>"}).headers
    assert unsafe["x-request-id"] != "<script>"


def test_errors_are_json_with_request_id(client: TestClient) -> None:
    response = client.get("/api/nao-existe")
    assert response.status_code == 404
    assert response.json()["error"] == "Rota da API não encontrada."
    assert response.json()["requestId"] == response.headers["x-request-id"]
    assert client.delete("/api/tickets").status_code == 404


def test_invalid_json(client: TestClient) -> None:
    response = client.post(
        "/api/tickets", content=b"{nope", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json()["error"] == "JSON inválido."


def test_body_size_limit(client: TestClient) -> None:
    big = {**TICKET, "message": "x" * 60_000}
    response = client.post("/api/tickets", json=big)
    assert response.status_code == 413
    assert response.json()["error"] == "O conteúdo enviado é grande demais."


def test_body_size_limit_without_content_length(client: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        yield b'{"message": "'
        for _ in range(10):
            yield b"x" * 10_000
        yield b'"}'

    response = client.post(
        "/api/tickets", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413


def test_rate_limit_on_writes(client_factory: ClientFactory) -> None:
    client = client_factory(rate_limit_enabled=True, rate_limit_writes_per_minute=2)
    assert client.post("/api/tickets", json=TICKET).status_code == 201
    assert client.post("/api/tickets", json=TICKET).status_code == 201
    blocked = client.post("/api/tickets", json=TICKET)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1
    assert "Aguarde" in blocked.json()["error"]
    # Leituras não são limitadas.
    assert client.get("/api/tickets").status_code == 200


def test_rate_limit_on_suggestions(client_factory: ClientFactory) -> None:
    client = client_factory(rate_limit_enabled=True, rate_limit_suggest_per_minute=1)
    assert client.post("/api/suggest", json={"ticketId": 1}).status_code == 200
    assert client.post("/api/suggest", json={"ticketId": 1}).status_code == 429


def test_openai_key_never_reaches_the_client(client_factory: ClientFactory) -> None:
    client = client_factory(openai_api_key="sk-super-secret", openai_model="modelo")
    health = client.get("/api/health")
    assert health.json()["suggestionMode"] == "openai"
    for path in ("/api/health", "/openapi.json", "/", "/app.js"):
        assert "sk-super-secret" not in client.get(path).text


def test_docs_have_hash_based_csp(client: TestClient) -> None:
    response = client.get("/docs")
    assert response.status_code == 200
    csp = response.headers["content-security-policy"]
    assert "'sha256-" in csp
    assert "unsafe-inline" not in csp


def test_docs_can_be_disabled(client_factory: ClientFactory) -> None:
    client = client_factory(docs_enabled=False)
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404
