"""phase 1a: add customer.user_id ownership foundation

Revision ID: bd0578485c27
Revises: 6d859d8f4b1b
Create Date: 2026-07-23 16:46:12.121503

Adds `customers.user_id` (nullable, unique, FK to users.id,
ON DELETE SET NULL) -- the ownership foundation linking a Customer
billing record to the User account that owns it. No authorization
logic reads this column yet; that is a separate, later step.

Backfills existing rows by matching Customer.email to User.email
(safe as a one-time backfill: both columns are independently unique,
so the match can never fan out to more than one row either way).
Rows with no matching User email are left with user_id = NULL rather
than guessed at.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd0578485c27'
down_revision: Union[str, None] = '6d859d8f4b1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('customers', sa.Column('user_id', sa.UUID(), nullable=True))

    # Backfill: match by email, one time, under this migration's
    # transaction. Both customers.email and users.email are
    # independently UNIQUE, so this join can never produce ambiguous
    # (fan-out) matches.
    op.execute(
        """
        UPDATE customers
        SET user_id = users.id
        FROM users
        WHERE customers.email = users.email
          AND customers.user_id IS NULL
        """
    )

    op.create_index(op.f('ix_customers_user_id'), 'customers', ['user_id'], unique=True)
    op.create_foreign_key(
        'fk_customers_user_id_users', 'customers', 'users',
        ['user_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_customers_user_id_users', 'customers', type_='foreignkey')
    op.drop_index(op.f('ix_customers_user_id'), table_name='customers')
    op.drop_column('customers', 'user_id')
