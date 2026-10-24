"""users: logins, and every row belongs to one user

Adds the users and login_session tables, and a user_id column to the six tables that
hold your data. Rows that existed before this (your data so far) are given to one
user called "owner" with no password yet. Run  python users.py claim  to pick your own
username and password for it.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-24 10:30:00
"""
import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

TIMESTAMP = getattr(sqlmodel.sql.sqltypes, "UTCDateTime", sa.DateTime)
TEXT = sqlmodel.sql.sqltypes.AutoString

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The tables that hold someone's data. Each gets a user_id.
OWNED = ["account", "category", "category_rule", "budget", "statement_import", "transactions"]
PLACEHOLDER = "owner"  # users.py claim renames it and sets its password

# Gives unnamed constraints a name we can refer to (SQLite doesn't name them).
NAMING = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def keyword_constraint_name(bind) -> str:
    """The old one-keyword-for-everyone rule. Postgres named it itself; SQLite didn't."""
    for constraint in sa.inspect(bind).get_unique_constraints("category_rule"):
        if constraint["column_names"] == ["keyword"] and constraint["name"]:
            return constraint["name"]
    return "uq_category_rule_keyword"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", TEXT(), nullable=False),
        sa.Column("password_hash", TEXT(), nullable=False),
        sa.Column("created_at", TIMESTAMP(), nullable=False),
        sa.Column("failed_logins", sa.Integer(), nullable=False),
        sa.Column("locked_until", TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "login_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", TEXT(), nullable=False),
        sa.Column("created_at", TIMESTAMP(), nullable=False),
        sa.Column("expires_at", TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_login_session_user_id", "login_session", ["user_id"])

    # Data from before logins existed needs an owner, or it would belong to nobody.
    bind = op.get_bind()
    has_data = any(bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first() for table in OWNED)
    owner_id = None
    if has_data:
        users = sa.table(
            "users",
            sa.column("username", TEXT()),
            sa.column("password_hash", TEXT()),
            sa.column("created_at", TIMESTAMP()),
            sa.column("failed_logins", sa.Integer()),
        )
        bind.execute(users.insert().values(
            username=PLACEHOLDER,
            password_hash="",  # no password: nobody can log in as "owner" until it's claimed
            created_at=datetime.datetime.now(datetime.timezone.utc),
            failed_logins=0,
        ))
        owner_id = bind.execute(
            sa.text("SELECT id FROM users WHERE username = :name"), {"name": PLACEHOLDER}
        ).scalar_one()

    old_keyword_rule = keyword_constraint_name(bind)
    for table in OWNED:
        # 1. Add the column (empty for now), 2. fill it in, 3. make it required.
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        if owner_id is not None:
            bind.execute(sa.text(f"UPDATE {table} SET user_id = :owner"), {"owner": owner_id})
        with op.batch_alter_table(table, naming_convention=NAMING) as batch:
            batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
            batch.create_index(f"ix_{table}_user_id", ["user_id"])
            batch.create_foreign_key(f"fk_{table}_user_id_users", "users", ["user_id"], ["id"])
            if table == "category_rule":
                # A keyword used to be unique across everyone; now it's unique per person.
                batch.drop_constraint(old_keyword_rule, type_="unique")
                batch.create_unique_constraint("uq_category_rule_user_keyword", ["user_id", "keyword"])


def downgrade() -> None:
    """Back to one shared set of data. Everyone's rows stay, but all of them are visible
    to everyone again, so only use this on a database with a single user."""
    for table in reversed(OWNED):
        with op.batch_alter_table(table) as batch:
            if table == "category_rule":
                batch.drop_constraint("uq_category_rule_user_keyword", type_="unique")
                batch.create_unique_constraint("uq_category_rule_keyword", ["keyword"])
            batch.drop_constraint(f"fk_{table}_user_id_users", type_="foreignkey")
            batch.drop_index(f"ix_{table}_user_id")
            batch.drop_column("user_id")
    op.drop_index("ix_login_session_user_id", table_name="login_session")
    op.drop_table("login_session")
    op.drop_table("users")
