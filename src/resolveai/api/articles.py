"""Base de conhecimento: artigos, edição versionada e busca."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from resolveai.api.deps import SessionDep, WriteLimit
from resolveai.db import utcnow
from resolveai.errors import ApiError
from resolveai.models import Article, ArticleVersion
from resolveai.schemas import (
    ArticleIn,
    ArticleOut,
    ArticleSaved,
    ArticleVersionOut,
    Created,
    SearchOut,
    SearchResult,
)
from resolveai.search import query_terms, search_articles

router = APIRouter(prefix="/api", tags=["base de conhecimento"])

ARTICLE_NOT_FOUND = "Artigo não encontrado."
DUPLICATE_TITLE = "Já existe um artigo com esse título."
DEFAULT_EDITOR = "equipe de suporte"


@router.get("/articles", response_model=list[ArticleOut], name="list_articles")
def list_articles(session: SessionDep) -> list[Article]:
    return list(session.scalars(select(Article).order_by(Article.category, Article.title)))


@router.get(
    "/articles/{article_id}/history",
    response_model=list[ArticleVersionOut],
    name="article_history",
)
def article_history(article_id: int, session: SessionDep) -> list[ArticleVersion]:
    if session.get(Article, article_id) is None:
        raise ApiError(404, ARTICLE_NOT_FOUND)
    stmt = (
        select(ArticleVersion)
        .where(ArticleVersion.article_id == article_id)
        .order_by(ArticleVersion.version.desc())
    )
    return list(session.scalars(stmt))


def _title_taken(session: SessionDep, title: str, exclude_id: int | None = None) -> bool:
    stmt = select(Article.id).where(Article.title == title)
    if exclude_id is not None:
        stmt = stmt.where(Article.id != exclude_id)
    return session.scalar(stmt) is not None


@router.post(
    "/articles",
    status_code=201,
    response_model=Created,
    name="create_article",
    dependencies=[WriteLimit],
)
def create_article(payload: ArticleIn, session: SessionDep) -> Created:
    if _title_taken(session, payload.title):
        raise ApiError(409, DUPLICATE_TITLE)
    article = Article(title=payload.title, category=payload.category, body=payload.body)
    session.add(article)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ApiError(409, DUPLICATE_TITLE) from exc
    return Created(id=article.id)


@router.put(
    "/articles/{article_id}",
    response_model=ArticleSaved,
    name="update_article",
    dependencies=[WriteLimit],
)
def update_article(article_id: int, payload: ArticleIn, session: SessionDep) -> ArticleSaved:
    article = session.get(Article, article_id)
    if article is None:
        raise ApiError(404, ARTICLE_NOT_FOUND)
    if _title_taken(session, payload.title, exclude_id=article_id):
        raise ApiError(409, DUPLICATE_TITLE)
    version = (
        session.scalar(
            select(func.coalesce(func.max(ArticleVersion.version), 0)).where(
                ArticleVersion.article_id == article_id
            )
        )
        or 0
    ) + 1
    # A versão guarda o conteúdo anterior; o artigo passa a ter o novo conteúdo.
    session.add(
        ArticleVersion(
            article_id=article_id,
            version=version,
            title=article.title,
            category=article.category,
            body=article.body,
            editor=payload.editor or DEFAULT_EDITOR,
        )
    )
    article.title = payload.title
    article.category = payload.category
    article.body = payload.body
    article.updated_at = utcnow()
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ApiError(409, "O artigo foi alterado ao mesmo tempo. Tente novamente.") from exc
    return ArticleSaved(version=version)


@router.get("/search", response_model=SearchOut, name="search")
def search(
    session: SessionDep,
    q: Annotated[str, Query(max_length=200)] = "",
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> SearchOut:
    hits = search_articles(session, q, limit=limit)
    return SearchOut(
        query=q,
        terms=query_terms(q),
        results=[
            SearchResult(id=h.id, title=h.title, category=h.category, score=h.score) for h in hits
        ],
    )
