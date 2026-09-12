"""Add password_hash column to accounts table.

Revision ID: 0002_password_hash
Revises: 0001_initial
Create Date: 2026-09-12
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0002_password_hash"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("accounts")]
    if "password_hash" not in columns:
        op.add_column("accounts", sa.Column("password_hash", sa.String(length=256), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("accounts")]
    if "password_hash" in columns:
        op.drop_column("accounts", "password_hash")
