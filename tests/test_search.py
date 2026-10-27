from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from resolveai.models import Article
from resolveai.search import (
    build_match_expression,
    keep_relevant,
    normalize,
    query_terms,
    search_articles,
    stem,
)


def _add(session: Session, title: str, body: str, category: str = "Geral") -> int:
    article = Article(title=title, category=category, body=body)
    session.add(article)
    session.commit()
    return article.id


def test_normalize_removes_accents_and_case() -> None:
    assert normalize("DEVOLUÇÃO Não Alergênicos") == "devolucao nao alergenicos"


def test_query_terms_drop_stopwords_short_words_and_duplicates() -> None:
    assert query_terms("Olá, como eu faço o ESTORNO do estorno no cartão?") == [
        "faco",
        "estorno",
        "cartao",
    ]


@pytest.mark.parametrize("query", ["", "   ", "a e o", "como para que", "?!?"])
def test_empty_or_meaningless_query_returns_nothing(empty_session: Session, query: str) -> None:
    _add(empty_session, "Como consultar o prazo de estorno", "Texto sobre estorno e prazos.")
    assert search_articles(empty_session, query) == []


def test_accent_insensitive_in_both_directions(empty_session: Session) -> None:
    accented = _add(empty_session, "Devolução no cartão", "O estorno volta para o cartão original.")
    plain = _add(empty_session, "Alergenicos", "Consulte a ficha tecnica do produto.")
    assert [h.id for h in search_articles(empty_session, "devolucao cartao")] == [accented]
    assert [h.id for h in search_articles(empty_session, "ALERGÊNICOS")] == [plain]
    assert [h.id for h in search_articles(empty_session, "ficha técnica")] == [plain]


def test_prefix_stem_matches_inflections(empty_session: Session) -> None:
    article = _add(
        empty_session, "Pedido não chegou", "Fale com o entregador e confirme a entrega."
    )
    assert stem("entregue") == "entreg"
    assert [h.id for h in search_articles(empty_session, "foi entregue?")] == [article]
    assert [h.id for h in search_articles(empty_session, "pedidos")] == [article]


def test_title_matches_rank_above_body_matches(empty_session: Session) -> None:
    in_body = _add(
        empty_session, "Política geral", "Informações sobre estorno aparecem aqui também."
    )
    in_title = _add(empty_session, "Prazo de estorno", "Consulte a transação no painel.")
    hits = search_articles(empty_session, "estorno")
    assert [h.id for h in hits] == [in_title, in_body]
    assert hits[0].score > hits[1].score > 0


def test_more_matching_terms_rank_higher(empty_session: Session) -> None:
    one = _add(empty_session, "Cartão recusado", "Verifique o limite com o banco emissor.")
    two = _add(empty_session, "Estorno no cartão", "O estorno volta para o cartão em alguns dias.")
    assert [h.id for h in search_articles(empty_session, "estorno cartão")] == [two, one]


def test_ties_are_broken_by_id(empty_session: Session) -> None:
    first = _add(empty_session, "Endereço A", "Alterar endereço do pedido.")
    second = _add(empty_session, "Endereço B", "Alterar endereço do pedido.")
    hits = search_articles(empty_session, "endereço")
    assert [h.id for h in hits] == [first, second]
    assert hits[0].score == hits[1].score


def test_limit_and_no_match(empty_session: Session) -> None:
    for i in range(5):
        _add(empty_session, f"Entrega {i}", "Texto sobre entrega de pedidos.")
    assert len(search_articles(empty_session, "entrega", limit=3)) == 3
    assert search_articles(empty_session, "quantum entanglement") == []


@pytest.mark.parametrize(
    "query",
    [
        '"estorno',
        "estorno AND OR NOT",
        "estorno*",
        "NEAR(estorno cartao)",
        "col:estorno",
        "^estorno",
    ],
)
def test_fts_operators_in_user_text_are_neutralized(empty_session: Session, query: str) -> None:
    article = _add(empty_session, "Estorno", "Informações sobre estorno no cartão.")
    assert [h.id for h in search_articles(empty_session, query)] == [article]


def test_match_expression_only_contains_safe_tokens() -> None:
    expression = build_match_expression(query_terms('x" OR body:* estorno'))
    assert expression == '"body"* OR "estor"*'


def test_index_follows_updates_and_deletes(empty_session: Session) -> None:
    article_id = _add(empty_session, "Senha", "Recuperação de acesso pela tela de login.")
    article = empty_session.get(Article, article_id)
    assert article is not None
    article.body = "Use a recuperação de conta com verificação de identidade."
    empty_session.commit()
    assert search_articles(empty_session, "login") == []
    assert [h.id for h in search_articles(empty_session, "identidade")] == [article_id]
    empty_session.delete(article)
    empty_session.commit()
    assert search_articles(empty_session, "identidade") == []


def test_keep_relevant_drops_incidental_matches(empty_session: Session) -> None:
    strong = _add(empty_session, "Estorno no cartão", "Estorno do cartão e prazo do estorno.")
    _add(empty_session, "Outro assunto", "Texto longo " * 30 + "cartão.")
    hits = keep_relevant(search_articles(empty_session, "estorno cartão prazo"), 0.3)
    assert [h.id for h in hits] == [strong]
    assert keep_relevant([], 0.3) == []
