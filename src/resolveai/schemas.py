"""Schemas Pydantic da API (JSON em camelCase, igual ao contrato da versão Node)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field
from pydantic.alias_generators import to_camel

from resolveai.models import Priority, TicketStatus

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def collapse_whitespace(value: Any) -> Any:
    """Equivalente ao `clean()` original: trim e espaços colapsados."""
    return " ".join(value.split()) if isinstance(value, str) else value


def tidy_multiline(value: Any) -> Any:
    """Trim preservando quebras de linha; no máximo uma linha em branco seguida."""
    if not isinstance(value, str):
        return value
    lines = [" ".join(line.split()) for line in value.replace("\r\n", "\n").split("\n")]
    return _BLANK_LINES_RE.sub("\n\n", "\n".join(lines)).strip()


def _check_email(value: str) -> str:
    if not _EMAIL_RE.match(value):
        raise ValueError("E-mail inválido.")
    return value


def _priority(value: Any) -> Any:
    # A versão anterior tratava qualquer valor diferente de "Alta" como "Normal".
    return Priority.ALTA.value if value == Priority.ALTA.value else Priority.NORMAL.value


def _category_or_default(value: Any) -> Any:
    value = collapse_whitespace(value)
    return value or "Geral"


CleanStr = Annotated[str, BeforeValidator(collapse_whitespace)]
MultilineStr = Annotated[str, BeforeValidator(tidy_multiline)]


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        from_attributes=True,
    )


class InputModel(ApiModel):
    model_config = ConfigDict(extra="ignore", str_max_length=20_000)


# --- Entrada -----------------------------------------------------------------


class TicketCreate(InputModel):
    customer: Annotated[CleanStr, Field(min_length=4, max_length=120)]
    email: Annotated[CleanStr, Field(max_length=254), AfterValidator(_check_email)]
    subject: Annotated[CleanStr, Field(min_length=4, max_length=100)]
    message: Annotated[CleanStr, Field(min_length=4, max_length=1200)]
    category: Annotated[str, BeforeValidator(_category_or_default), Field(max_length=60)] = "Geral"
    priority: Annotated[Priority, BeforeValidator(_priority)] = Priority.NORMAL


class StatusUpdate(InputModel):
    status: Annotated[TicketStatus, BeforeValidator(collapse_whitespace)]


class ArticleIn(InputModel):
    title: Annotated[CleanStr, Field(min_length=4, max_length=120)]
    category: Annotated[CleanStr, Field(min_length=2, max_length=60)]
    body: Annotated[str, BeforeValidator(tidy_multiline), Field(min_length=20, max_length=12000)]
    editor: Annotated[CleanStr, Field(max_length=80)] | None = None


class SuggestIn(InputModel):
    ticket_id: Annotated[int, Field(gt=0)] | None = None
    message: Annotated[CleanStr, Field(max_length=1200)] | None = None


class ReplyIn(InputModel):
    ticket_id: Annotated[int, Field(gt=0)]
    body: Annotated[MultilineStr, Field(min_length=4, max_length=1600)]
    source_ids: Annotated[list[Annotated[int, Field(gt=0)]], Field(max_length=10)] = Field(
        default_factory=list
    )


# --- Saída -------------------------------------------------------------------


class ReplyOut(ApiModel):
    body: str
    source_ids: list[int]
    created_at: datetime


class TicketOut(ApiModel):
    id: int
    customer: str
    email: str
    subject: str
    message: str
    category: str
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime
    replies: list[ReplyOut]


class ArticleOut(ApiModel):
    id: int
    title: str
    category: str
    body: str
    updated_at: datetime


class ArticleVersionOut(ApiModel):
    version: int
    title: str
    category: str
    body: str
    editor: str
    created_at: datetime


class Created(ApiModel):
    id: int


class Ok(ApiModel):
    ok: Literal[True] = True


class ArticleSaved(Ok):
    version: int


class SourceOut(ApiModel):
    id: int
    title: str
    category: str


class SuggestionOut(ApiModel):
    draft: str
    sources: list[SourceOut]
    cited_source_ids: list[int]
    mode: str
    needs_review: Literal[True] = True


class SearchResult(SourceOut):
    score: float


class SearchOut(ApiModel):
    query: str
    terms: list[str]
    results: list[SearchResult]


class HealthOut(ApiModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "error"]
    suggestion_mode: str
    version: str


class ErrorOut(BaseModel):
    error: str
    request_id: str | None = Field(default=None, serialization_alias="requestId")
