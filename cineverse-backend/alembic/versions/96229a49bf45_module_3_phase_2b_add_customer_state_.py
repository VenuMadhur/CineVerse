"""module 3 phase 2b: add customer state field

Revision ID: 96229a49bf45
Revises: 3c8a6028b88f
Create Date: 2026-08-02 07:59:47.948970

Module 3, Phase 2b: adds a single nullable `state` column to
`customers`, needed for the State-wise Tax report. Nullable with no
default -- no existing customer row requires backfilling, and the
column is entirely optional going forward (CustomerCreate/Update both
treat it as optional). Purely additive; no other column or table
touched.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96229a49bf45'
down_revision: Union[str, None] = '3c8a6028b88f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('customers', sa.Column('state', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('customers', 'state')
