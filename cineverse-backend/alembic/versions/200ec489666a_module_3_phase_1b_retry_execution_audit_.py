"""module 3 phase 1b: retry execution audit event types

Revision ID: 200ec489666a
Revises: 18238c924250
Create Date: 2026-08-02 02:36:18.066794

Adds the 5 new AuditEventType values needed for retry execution:
RETRY_SCHEDULED, RETRY_ATTEMPTED, RETRY_SUCCEEDED, RETRY_FAILED,
RETRY_CANCELLED. Same ALTER TYPE ... ADD VALUE pattern used for every
prior audit event type addition in this project.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '200ec489666a'
down_revision: Union[str, None] = '18238c924250'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_AUDIT_EVENT_VALUES = [
    "RETRY_SCHEDULED",
    "RETRY_ATTEMPTED",
    "RETRY_SUCCEEDED",
    "RETRY_FAILED",
    "RETRY_CANCELLED",
]


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for value in NEW_AUDIT_EVENT_VALUES:
            op.execute(
                f"ALTER TYPE audit_event_type_enum ADD VALUE IF NOT EXISTS '{value}'"
            )


def downgrade() -> None:
    # PostgreSQL cannot drop individual enum values; intentionally a
    # no-op (see every prior audit-event-type migration for the same
    # reasoning).
    pass
