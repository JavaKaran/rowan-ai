"""create database metadata table

Revision ID: 42f2b7c0d8a1
Revises: e5a3dff45c79
Create Date: 2026-07-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "42f2b7c0d8a1"
down_revision: Union[str, Sequence[str], None] = "e5a3dff45c79"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "database_metadata",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("database_connection_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress_current", sa.Integer(), nullable=False),
        sa.Column("progress_total", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["database_connection_id"], ["database_connections.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("database_connection_id"),
    )
    op.create_index(
        op.f("ix_database_metadata_database_connection_id"),
        "database_metadata",
        ["database_connection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_database_metadata_id"),
        "database_metadata",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_database_metadata_id"), table_name="database_metadata")
    op.drop_index(
        op.f("ix_database_metadata_database_connection_id"),
        table_name="database_metadata",
    )
    op.drop_table("database_metadata")
