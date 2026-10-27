"""add user account activity audit event types

Revision ID: a8f8d4eb291a
Revises: 63d7fe7ece36
Create Date: 2026-07-26 07:42:32.078908

Adds the three new AuditEventType values needed for the account-wide
Activity Timeline: USER_REGISTERED, USER_LOGGED_IN, USER_LOGGED_OUT.
Same ALTER TYPE ... ADD VALUE pattern as the Module 2 and Phase 6B
audit-event migrations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8f8d4eb291a'
down_revision: Union[str, None] = '63d7fe7ece36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_AUDIT_EVENT_VALUES = [
    "USER_REGISTERED",
    "USER_LOGGED_IN",
    "USER_LOGGED_OUT",
]


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for value in NEW_AUDIT_EVENT_VALUES:
            op.execute(
                f"ALTER TYPE audit_event_type_enum ADD VALUE IF NOT EXISTS '{value}'"
            )


def downgrade() -> None:
    # PostgreSQL cannot drop individual enum values; intentionally a
    # no-op (see the Module 2 / Phase 6B equivalent migrations for the
    # same reasoning).
    pass
