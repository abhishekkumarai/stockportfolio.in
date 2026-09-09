"""Initial schema — accounts, holdings, snapshots, alerts, paper trading, chunks.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-06

Created from `Base.metadata` rather than hand-written DDL, so the migration and
the models cannot disagree on this first revision. Subsequent revisions come
from `alembic revision --autogenerate`.
"""

from typing import Sequence, Union

from alembic import op

from app.db.models import Base

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    # pgvector is a Postgres-only concern. `document_chunks.embedding` is a
    # JSON array in the models so the schema also creates on SQLite; on
    # Postgres the extension is enabled here so a later revision can convert
    # the column to a native `vector` and add an ivfflat index.
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
