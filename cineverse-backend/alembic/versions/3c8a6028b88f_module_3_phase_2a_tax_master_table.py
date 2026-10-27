"""module 3 phase 2a: tax master table

Revision ID: 3c8a6028b88f
Revises: 200ec489666a
Create Date: 2026-08-02 03:16:09.052812

Module 3, Phase 2a: the Tax Master table, replacing the Module 2
approach of tax rates living only in settings.TAX_RATES. Adds:
  - tax_rates: admin-manageable rates with effective-date ranges.
  - TAX_RATE_CREATED / TAX_RATE_UPDATED audit event types.

Seeds the table with the exact values previously hardcoded in
settings.TAX_RATES, so invoice tax calculations produce identical
results immediately after this migration as before it -- countries
not in this seed list still fall back to settings.DEFAULT_TAX_RATE via
TaxService, exactly as before Phase 2a.

Postgres requires `ALTER TYPE ... ADD VALUE` to run outside a
transaction block (autocommit_block()), same as every prior
audit-event-type migration; table creation and the seed inserts run
in the normal transactional part of this same migration.
"""
from datetime import date, datetime, timezone
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '3c8a6028b88f'
down_revision: Union[str, None] = '200ec489666a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_AUDIT_EVENT_VALUES = [
    "TAX_RATE_CREATED",
    "TAX_RATE_UPDATED",
]

# Matches settings.TAX_RATES exactly, as of this migration.
SEED_TAX_RATES = [
    ("US", "Sales Tax", "8.00"),
    ("IN", "GST", "18.00"),
    ("GB", "VAT", "20.00"),
    ("DE", "VAT", "19.00"),
    ("FR", "VAT", "20.00"),
    ("CA", "GST", "5.00"),
    ("AU", "GST", "10.00"),
]


def upgrade() -> None:
    op.create_table('tax_rates',
    sa.Column('country', sa.String(length=2), nullable=False),
    sa.Column('state', sa.String(length=100), nullable=True),
    sa.Column('tax_name', sa.String(length=100), nullable=False),
    sa.Column('tax_percentage', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('effective_from', sa.Date(), nullable=False),
    sa.Column('effective_to', sa.Date(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id')
    )
    op.create_index(op.f('ix_tax_rates_country'), 'tax_rates', ['country'], unique=False)

    with op.get_context().autocommit_block():
        for value in NEW_AUDIT_EVENT_VALUES:
            op.execute(
                f"ALTER TYPE audit_event_type_enum ADD VALUE IF NOT EXISTS '{value}'"
            )

    tax_rates_table = sa.table(
        "tax_rates",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("country", sa.String),
        sa.column("tax_name", sa.String),
        sa.column("tax_percentage", sa.Numeric),
        sa.column("effective_from", sa.Date),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    today = date.today()
    op.bulk_insert(
        tax_rates_table,
        [
            {
                "id": uuid.uuid4(),
                "country": country,
                "tax_name": tax_name,
                "tax_percentage": percentage,
                "effective_from": today,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            for country, tax_name, percentage in SEED_TAX_RATES
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_tax_rates_country'), table_name='tax_rates')
    op.drop_table('tax_rates')
    # PostgreSQL cannot drop individual enum values; intentionally a
    # no-op (see every prior audit-event-type migration for the same
    # reasoning).
