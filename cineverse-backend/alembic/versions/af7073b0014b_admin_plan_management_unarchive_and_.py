"""admin plan management: unarchive and delete audit events

Revision ID: af7073b0014b
Revises: 7240517bda16
Create Date: 2026-08-05 04:47:46.153447

Adds PLAN_UNARCHIVED and PLAN_DELETED, needed by the new
PlanService.unarchive_plan() and delete_plan() methods. Same
ALTER TYPE ... ADD VALUE pattern used for every prior audit event
type addition in this project.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af7073b0014b'
down_revision: Union[str, None] = '7240517bda16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE audit_event_type_enum ADD VALUE IF NOT EXISTS 'PLAN_UNARCHIVED'")
        op.execute("ALTER TYPE audit_event_type_enum ADD VALUE IF NOT EXISTS 'PLAN_DELETED'")


def downgrade() -> None:
    # PostgreSQL cannot drop individual enum values; intentionally a
    # no-op (see every prior audit-event-type migration for the same
    # reasoning).
    pass
