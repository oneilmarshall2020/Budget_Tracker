"""baseline: the tables as they were when migrations were added

A database made before migrations existed already looks like this, so migrate.py
marks it as "at 0001" instead of running this file on it.

Revision ID: 0001
Revises: 
Create Date: 2026-10-15 19:38:09.304962

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # SQLModel's text columns show up as sqlmodel.sql.sqltypes.AutoString


# Newer SQLModel versions store timestamps with a special UTC type; older ones use a
# plain DateTime. Both are a DATETIME column in SQLite, so use whichever exists.
TIMESTAMP = getattr(sqlmodel.sql.sqltypes, "UTCDateTime", sa.DateTime)

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('account',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nickname', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('bank_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('account_type', sa.Enum('savings', 'chequing', 'credit_card', name='accounttype'), nullable=False),
    sa.Column('last_four', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('currency', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('category',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('kind', sa.Enum('income', 'expense', name='categorykind'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('budget',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('month', sa.Integer(), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['category.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('category_rule',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('keyword', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['category.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('keyword')
    )
    op.create_table('statement_import',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=True),
    sa.Column('file_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('imported_at', TIMESTAMP(), nullable=False),
    sa.Column('first_date', sa.Date(), nullable=False),
    sa.Column('last_date', sa.Date(), nullable=False),
    sa.Column('row_count', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['account.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('transactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('type', sa.Enum('income', 'expense', 'transfer', 'refund', name='transactiontype'), nullable=False),
    sa.Column('source', sa.Enum('manual', 'statement', name='transactionsource'), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('account_id', sa.Integer(), nullable=True),
    sa.Column('import_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['account.id'], ),
    sa.ForeignKeyConstraint(['category_id'], ['category.id'], ),
    sa.ForeignKeyConstraint(['import_id'], ['statement_import.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('transactions')
    op.drop_table('statement_import')
    op.drop_table('category_rule')
    op.drop_table('budget')
    op.drop_table('category')
    op.drop_table('account')
