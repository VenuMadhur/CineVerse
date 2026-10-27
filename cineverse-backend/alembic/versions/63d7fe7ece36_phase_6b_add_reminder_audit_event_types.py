"""phase 6b: add reminder audit event types

Revision ID: 63d7fe7ece36
Revises: bd0578485c27
Create Date: 2026-07-25 14:31:05.872894

Phase 6B's trial-ending/renewal reminder scheduler dedupes by checking
the audit log for an existing reminder event before sending another
one (rather than adding a new "last_reminded_at" column to
Subscription/BillingCycle) -- this migration just registers the two
new AuditEventType values Postgres needs to accept them.

Postgres requires `ALTER TYPE ... ADD VALUE` to run outside a
transaction block, so this uses `autocommit_block()`, same as the
Module 2 audit-event-type migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '63d7fe7ece36'
down_revision: Union[str, None] = 'bd0578485c27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_AUDIT_EVENT_VALUES = [
    "TRIAL_ENDING_REMINDER_SENT",
    "RENEWAL_REMINDER_SENT",
]


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for value in NEW_AUDIT_EVENT_VALUES:
            op.execute(
                f"ALTER TYPE audit_event_type_enum ADD VALUE IF NOT EXISTS '{value}'"
            )


def downgrade() -> None:
    # PostgreSQL cannot drop individual enum values; intentionally a
    # no-op (see Module 2's equivalent migration for the same reasoning).
    pass
