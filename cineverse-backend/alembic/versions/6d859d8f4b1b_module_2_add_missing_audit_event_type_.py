"""module 2: add missing audit_event_type_enum values

Revision ID: 6d859d8f4b1b
Revises: 0b7d6d46e545
Create Date: 2026-07-15 14:53:51.437856

Module 2 added nine new AuditEventType members (invoice paid/failed,
proration applied, payment processed/succeeded/failed/refunded,
webhook received, refund created) which must be registered on the
existing `audit_event_type_enum` Postgres type. Postgres requires
`ALTER TYPE ... ADD VALUE` to run outside a transaction block, so
each addition uses `autocommit_block()`.

Note: PostgreSQL does not support removing individual enum values, so
`downgrade()` is intentionally a no-op here — the extra labels are
harmless if left in place, and a true rollback would require
recreating the type (a much larger, and here unnecessary, operation).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d859d8f4b1b'
down_revision: Union[str, None] = '0b7d6d46e545'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_AUDIT_EVENT_VALUES = [
    "INVOICE_PAID",
    "INVOICE_FAILED",
    "PRORATION_APPLIED",
    "PAYMENT_PROCESSED",
    "PAYMENT_SUCCEEDED",
    "PAYMENT_FAILED",
    "PAYMENT_REFUNDED",
    "WEBHOOK_RECEIVED",
    "REFUND_CREATED",
]


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for value in NEW_AUDIT_EVENT_VALUES:
            op.execute(
                f"ALTER TYPE audit_event_type_enum ADD VALUE IF NOT EXISTS '{value}'"
            )


def downgrade() -> None:
    # PostgreSQL cannot drop individual enum values; intentionally a
    # no-op (see module docstring above).
    pass
