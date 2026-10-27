from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

ARTICLE = {
    "title": "Reset a forgotten password",
    "category": "Account",
    "body": "Open account settings, choose password reset, and follow the verified reset link "
    "sent to your registered email.",
}


def test_lists_articles_ordered_by_category_and_title(client: TestClient) -> None:
    articles = client.get("/api/articles").json()
    assert len(articles) == 5
    keys = [(a["category"], a["title"]) for a in articles]
    assert keys == sorted(keys)
    assert set(articles[0]) == {"id", "title", "category", "body", "updatedAt"}


def test_edits_retain_prior_versions(client: TestClient) -> None:
    """Cenário portado do teste Node original."""
    created = client.post("/api/articles", json=ARTICLE)
    assert created.status_code == 201
    article_id = created.json()["id"]
    updated = client.put(
        f"/api/articles/{article_id}",
        json={
            **ARTICLE,
            "body": "Use the account recovery screen and verify identity before changing "
            "credentials. Support agents should never ask customers to share passwords.",
            "editor": "qa reviewer",
        },
    )
    assert updated.status_code == 200
    assert updated.json() == {"ok": True, "version": 1}
    history = client.get(f"/api/articles/{article_id}/history").json()
    assert len(history) == 1
    assert "verified reset link" in history[0]["body"]
    assert history[0]["editor"] == "qa reviewer"

    second = client.put(f"/api/articles/{article_id}", json={**ARTICLE, "title": "Reset password"})
    assert second.json()["version"] == 2
    history = client.get(f"/api/articles/{article_id}/history").json()
    assert [v["version"] for v in history] == [2, 1]
    assert history[0]["editor"] == "equipe de suporte"
    assert "recovery screen" in history[0]["body"]


def test_body_keeps_line_breaks(client: TestClient) -> None:
    body = "Passo 1: confirme o pedido.\n\n\n\nPasso 2: fale com a loja responsável."
    article_id = client.post("/api/articles", json={**ARTICLE, "body": body}).json()["id"]
    saved = next(a for a in client.get("/api/articles").json() if a["id"] == article_id)
    assert saved["body"] == "Passo 1: confirme o pedido.\n\nPasso 2: fale com a loja responsável."


def test_duplicate_titles_conflict(client: TestClient) -> None:
    assert client.post("/api/articles", json=ARTICLE).status_code == 201
    duplicate = client.post("/api/articles", json=ARTICLE)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"] == "Já existe um artigo com esse título."
    other = next(a for a in client.get("/api/articles").json() if a["title"] != ARTICLE["title"])
    conflict = client.put(f"/api/articles/{other['id']}", json=ARTICLE)
    assert conflict.status_code == 409


@pytest.mark.parametrize(
    "override", [{"title": "abc"}, {"category": "x"}, {"body": "curto"}, {"body": "x" * 12001}]
)
def test_rejects_invalid_articles(client: TestClient, override: dict[str, str]) -> None:
    response = client.post("/api/articles", json={**ARTICLE, **override})
    assert response.status_code == 400
    assert response.json()["error"] == "Confira título, categoria e conteúdo do artigo."


def test_missing_article(client: TestClient) -> None:
    assert client.put("/api/articles/999", json=ARTICLE).status_code == 404
    response = client.get("/api/articles/999/history")
    assert response.status_code == 404
    assert response.json()["error"] == "Artigo não encontrado."


def test_search_endpoint_uses_ranking(client: TestClient) -> None:
    body = client.get("/api/search", params={"q": "Estorno no CARTÃO"}).json()
    assert body["terms"] == ["estorno", "cartao"]
    assert body["results"][0]["title"] == "Como consultar o prazo de estorno"
    assert client.get("/api/search", params={"q": "de"}).json()["results"] == []
    assert client.get("/api/search", params={"q": "x" * 201}).status_code == 400


def test_edited_article_is_searchable_immediately(client: TestClient) -> None:
    article = client.get("/api/articles").json()[0]
    client.put(
        f"/api/articles/{article['id']}",
        json={
            **ARTICLE,
            "title": "Cupom expirado",
            "body": "Cupons expirados não podem ser reativados.",
        },
    )
    results = client.get("/api/search", params={"q": "cupom expirado"}).json()["results"]
    assert results[0]["id"] == article["id"]
