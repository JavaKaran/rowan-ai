"""create database connections table

Revision ID: e5a3dff45c79
Revises: d014821337b9
Create Date: 2026-07-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5a3dff45c79"
down_revision: Union[str, Sequence[str], None] = "d014821337b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "database_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("database_type", sa.String(length=32), nullable=False),
        sa.Column("host", sa.String(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("database_name", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("encrypted_password", sa.Text(), nullable=False),
        sa.Column("ssl_mode", sa.String(length=32), nullable=True),
        sa.Column("is_connected", sa.Boolean(), nullable=False),
        sa.Column("status_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_database_connections_id"),
        "database_connections",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_database_connections_session_id"),
        "database_connections",
        ["session_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_database_connections_session_id"), table_name="database_connections")
    op.drop_index(op.f("ix_database_connections_id"), table_name="database_connections")
    op.drop_table("database_connections")
