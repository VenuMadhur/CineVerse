"""qa fix: subscription cancellation undone audit event type

Revision ID: 7240517bda16
Revises: e4fc9c65cc94
Create Date: 2026-08-03 15:25:54.472671

QA-confirmed fix (Finding #8): adds SUBSCRIPTION_CANCELLATION_UNDONE,
needed by the new SubscriptionService.undo_scheduled_cancellation()
method. Same ALTER TYPE ... ADD VALUE pattern used for every prior
audit event type addition in this project.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7240517bda16'
down_revision: Union[str, None] = 'e4fc9c65cc94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE audit_event_type_enum ADD VALUE IF NOT EXISTS "
            "'SUBSCRIPTION_CANCELLATION_UNDONE'"
        )


def downgrade() -> None:
    # PostgreSQL cannot drop individual enum values; intentionally a
    # no-op (see every prior audit-event-type migration for the same
    # reasoning).
    pass
