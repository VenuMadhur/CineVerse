"""module 3 phase 1a: add retry configuration audit event types

Revision ID: 18238c924250
Revises: 93bcf5e3e434
Create Date: 2026-08-01 18:14:25.467324

Adds the two new AuditEventType values needed by the Retry
Configuration CRUD API added in this same phase:
RETRY_CONFIGURATION_CREATED, RETRY_CONFIGURATION_UPDATED. Same
ALTER TYPE ... ADD VALUE pattern used for every prior audit event
type addition in this project.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18238c924250'
down_revision: Union[str, None] = '93bcf5e3e434'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_AUDIT_EVENT_VALUES = [
    "RETRY_CONFIGURATION_CREATED",
    "RETRY_CONFIGURATION_UPDATED",
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
