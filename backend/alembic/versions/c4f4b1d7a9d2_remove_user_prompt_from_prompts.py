"""remove user_prompt from prompts

Revision ID: c4f4b1d7a9d2
Revises: a4fd6d53ce21
Create Date: 2026-07-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f4b1d7a9d2"
down_revision: Union[str, Sequence[str], None] = "b8d9a1f31e22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("prompts", "user_prompt")


def downgrade() -> None:
    op.add_column("prompts", sa.Column("user_prompt", sa.Text(), nullable=False, server_default=""))
    op.alter_column("prompts", "user_prompt", server_default=None)
