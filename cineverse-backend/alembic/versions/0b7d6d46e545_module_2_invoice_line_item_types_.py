"""module 2: invoice line item types, payment gateway fields, refunds table

Revision ID: 0b7d6d46e545
Revises: 49675b65879a
Create Date: 2026-07-15 14:42:04.012499

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0b7d6d46e545'
down_revision: Union[str, None] = '49675b65879a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- New table: refunds (Module 2) ---
    op.create_table('refunds',
    sa.Column('invoice_id', sa.UUID(), nullable=False),
    sa.Column('customer_id', sa.UUID(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('reason', sa.String(length=500), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'COMPLETED', 'FAILED', name='refund_status_enum'), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_refunds_customer_id'), 'refunds', ['customer_id'], unique=False)
    op.create_index(op.f('ix_refunds_invoice_id'), 'refunds', ['invoice_id'], unique=False)
    op.create_index(op.f('ix_refunds_status'), 'refunds', ['status'], unique=False)

    # --- invoice_line_items.item_type (Module 2) ---
    # server_default backfills any pre-existing rows (e.g. Module 1
    # invoices already in the database) as PLAN_FEE, then the default
    # is dropped since new rows always specify item_type explicitly
    # via the ORM model.
    invoice_line_item_type_enum = postgresql.ENUM(
        'PLAN_FEE', 'PRORATION_CREDIT', 'PRORATION_DEBIT', 'USAGE_CHARGE', 'TAX', 'DISCOUNT', 'REFUND',
        name='invoice_line_item_type_enum',
    )
    invoice_line_item_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'invoice_line_items',
        sa.Column(
            'item_type',
            invoice_line_item_type_enum,
            nullable=False,
            server_default='PLAN_FEE',
        ),
    )
    op.alter_column('invoice_line_items', 'item_type', server_default=None)

    # --- payments.payment_method / payments.gateway_response (Module 2) ---
    op.add_column(
        'payments',
        sa.Column('payment_method', sa.String(length=50), nullable=False, server_default='mock_gateway'),
    )
    op.alter_column('payments', 'payment_method', server_default=None)
    op.add_column(
        'payments',
        sa.Column(
            'gateway_response',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='{}',
        ),
    )
    op.alter_column('payments', 'gateway_response', server_default=None)
    op.create_index(op.f('ix_payments_gateway_reference'), 'payments', ['gateway_reference'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_payments_gateway_reference'), table_name='payments')
    op.drop_column('payments', 'gateway_response')
    op.drop_column('payments', 'payment_method')
    op.drop_column('invoice_line_items', 'item_type')
    postgresql.ENUM(name='invoice_line_item_type_enum').drop(op.get_bind(), checkfirst=True)
    op.drop_index(op.f('ix_refunds_status'), table_name='refunds')
    op.drop_index(op.f('ix_refunds_invoice_id'), table_name='refunds')
    op.drop_index(op.f('ix_refunds_customer_id'), table_name='refunds')
    op.drop_table('refunds')
    postgresql.ENUM(name='refund_status_enum').drop(op.get_bind(), checkfirst=True)
