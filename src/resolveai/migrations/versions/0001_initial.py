"""Schema inicial, compatível com bancos criados pela versão Node, e índice FTS5.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOW = sa.text("CURRENT_TIMESTAMP")

_FTS_SQL = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5("
    "title, category, body, content='articles', content_rowid='id', "
    "tokenize='unicode61 remove_diacritics 2')",
    "CREATE TRIGGER IF NOT EXISTS articles_fts_ai AFTER INSERT ON articles BEGIN "
    "INSERT INTO articles_fts(rowid, title, category, body) "
    "VALUES (new.id, new.title, new.category, new.body); END",
    "CREATE TRIGGER IF NOT EXISTS articles_fts_ad AFTER DELETE ON articles BEGIN "
    "INSERT INTO articles_fts(articles_fts, rowid, title, category, body) "
    "VALUES ('delete', old.id, old.title, old.category, old.body); END",
    "CREATE TRIGGER IF NOT EXISTS articles_fts_au AFTER UPDATE ON articles BEGIN "
    "INSERT INTO articles_fts(articles_fts, rowid, title, category, body) "
    "VALUES ('delete', old.id, old.title, old.category, old.body); "
    "INSERT INTO articles_fts(rowid, title, category, body) "
    "VALUES (new.id, new.title, new.category, new.body); END",
    # Indexa artigos que já existiam (banco legado).
    "INSERT INTO articles_fts(articles_fts) VALUES ('rebuild')",
)


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "articles" not in existing:
        op.create_table(
            "articles",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("title", sa.Text, nullable=False, unique=True),
            sa.Column("category", sa.Text, nullable=False),
            sa.Column("body", sa.Text, nullable=False),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=_NOW),
        )
    if "tickets" not in existing:
        op.create_table(
            "tickets",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("customer", sa.Text, nullable=False),
            sa.Column("email", sa.Text, nullable=False),
            sa.Column("subject", sa.Text, nullable=False),
            sa.Column("message", sa.Text, nullable=False),
            sa.Column("category", sa.Text, nullable=False),
            sa.Column("priority", sa.String(16), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=_NOW),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=_NOW),
            sa.CheckConstraint(
                "status IN ('novo','em_atendimento','resolvido')", name="ck_tickets_status"
            ),
        )
    if "replies" not in existing:
        op.create_table(
            "replies",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "ticket_id",
                sa.Integer,
                sa.ForeignKey("tickets.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("body", sa.Text, nullable=False),
            sa.Column("source_ids", sa.JSON, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=_NOW),
        )
    if "article_versions" not in existing:
        op.create_table(
            "article_versions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "article_id",
                sa.Integer,
                sa.ForeignKey("articles.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("version", sa.Integer, nullable=False),
            sa.Column("title", sa.Text, nullable=False),
            sa.Column("category", sa.Text, nullable=False),
            sa.Column("body", sa.Text, nullable=False),
            sa.Column("editor", sa.Text, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=_NOW),
            sa.UniqueConstraint("article_id", "version"),
        )

    op.execute("CREATE INDEX IF NOT EXISTS ix_tickets_status ON tickets (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_replies_ticket_id ON replies (ticket_id)")
    for statement in _FTS_SQL:
        op.execute(statement)


def downgrade() -> None:
    for trigger in ("articles_fts_ai", "articles_fts_ad", "articles_fts_au"):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    op.execute("DROP TABLE IF EXISTS articles_fts")
    op.execute("DROP INDEX IF EXISTS ix_replies_ticket_id")
    op.execute("DROP INDEX IF EXISTS ix_tickets_status")
    op.drop_table("article_versions")
    op.drop_table("replies")
    op.drop_table("tickets")
    op.drop_table("articles")
