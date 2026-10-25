"""demo accounts: users.is_demo

Marks the throwaway accounts that "Try the demo" creates (see demo.py), so they can be
cleaned up after a week. Every existing user is a real one: is_demo = false.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-24 16:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        # server_default: the database fills in "false" for the users who already exist.
        batch.add_column(sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_demo")
