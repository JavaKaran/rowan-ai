"""create prompts table

Revision ID: a4fd6d53ce21
Revises: 9b3b7e2f4c10
Create Date: 2026-07-26 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4fd6d53ce21"
down_revision: Union[str, Sequence[str], None] = "9b3b7e2f4c10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prompts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assistant_message_id", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("metadata_text", sa.Text(), nullable=False),
        sa.Column("user_question", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assistant_message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assistant_message_id"),
    )
    op.create_index(op.f("ix_prompts_assistant_message_id"), "prompts", ["assistant_message_id"], unique=False)
    op.create_index(op.f("ix_prompts_id"), "prompts", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_prompts_id"), table_name="prompts")
    op.drop_index(op.f("ix_prompts_assistant_message_id"), table_name="prompts")
    op.drop_table("prompts")
