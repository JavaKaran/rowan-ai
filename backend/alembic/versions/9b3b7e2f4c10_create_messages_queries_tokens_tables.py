"""create messages queries tokens tables

Revision ID: 9b3b7e2f4c10
Revises: 42f2b7c0d8a1
Create Date: 2026-07-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b3b7e2f4c10"
down_revision: Union[str, Sequence[str], None] = "42f2b7c0d8a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("message_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_id"), "messages", ["id"], unique=False)
    op.create_index(op.f("ix_messages_session_id"), "messages", ["session_id"], unique=False)
    op.create_index(op.f("ix_messages_workspace_id"), "messages", ["workspace_id"], unique=False)

    op.create_table(
        "queries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assistant_message_id", sa.Integer(), nullable=False),
        sa.Column("database_connection_id", sa.Integer(), nullable=False),
        sa.Column("sql_query", sa.Text(), nullable=False),
        sa.Column("response_columns", sa.JSON(), nullable=False),
        sa.Column("response_rows", sa.JSON(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("execution_time_ms", sa.Integer(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assistant_message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["database_connection_id"], ["database_connections.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assistant_message_id"),
    )
    op.create_index(op.f("ix_queries_assistant_message_id"), "queries", ["assistant_message_id"], unique=False)
    op.create_index(op.f("ix_queries_database_connection_id"), "queries", ["database_connection_id"], unique=False)
    op.create_index(op.f("ix_queries_id"), "queries", ["id"], unique=False)

    op.create_table(
        "tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tokens_id"), "tokens", ["id"], unique=False)
    op.create_index(op.f("ix_tokens_message_id"), "tokens", ["message_id"], unique=False)
    op.create_index(op.f("ix_tokens_session_id"), "tokens", ["session_id"], unique=False)
    op.create_index(op.f("ix_tokens_workspace_id"), "tokens", ["workspace_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tokens_workspace_id"), table_name="tokens")
    op.drop_index(op.f("ix_tokens_session_id"), table_name="tokens")
    op.drop_index(op.f("ix_tokens_message_id"), table_name="tokens")
    op.drop_index(op.f("ix_tokens_id"), table_name="tokens")
    op.drop_table("tokens")

    op.drop_index(op.f("ix_queries_id"), table_name="queries")
    op.drop_index(op.f("ix_queries_database_connection_id"), table_name="queries")
    op.drop_index(op.f("ix_queries_assistant_message_id"), table_name="queries")
    op.drop_table("queries")

    op.drop_index(op.f("ix_messages_workspace_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_session_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_id"), table_name="messages")
    op.drop_table("messages")
