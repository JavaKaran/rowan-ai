"""add status and error to queries

Revision ID: b8d9a1f31e22
Revises: a4fd6d53ce21
Create Date: 2026-07-26 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8d9a1f31e22"
down_revision: Union[str, Sequence[str], None] = "a4fd6d53ce21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "queries",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
    )
    op.add_column(
        "queries",
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.alter_column("queries", "status", server_default=None)


def downgrade() -> None:
    op.drop_column("queries", "error_message")
    op.drop_column("queries", "status")
