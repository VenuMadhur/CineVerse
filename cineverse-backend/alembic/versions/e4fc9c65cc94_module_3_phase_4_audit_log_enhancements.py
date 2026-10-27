"""module 3 phase 4: audit log enhancements

Revision ID: e4fc9c65cc94
Revises: 96229a49bf45
Create Date: 2026-08-02 18:39:18.162276

Module 3, Phase 4: adds 5 nullable columns to audit_logs
(ip_address, actor_role, old_value, new_value, remarks) and 5 new
AuditEventType values (TRIAL_STARTED, TRIAL_ENDED, INVOICE_UPDATED,
PDF_GENERATED, INVOICE_DOWNLOADED).

Purely additive: no existing column, table, or enum value is
modified. Every existing audit_logs row gets NULL for the 5 new
columns, and every existing AuditLogService.record() call site
continues to produce identical rows (the new columns are optional
kwargs defaulting to None).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4fc9c65cc94'
down_revision: Union[str, None] = '96229a49bf45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_AUDIT_EVENT_VALUES = [
    "TRIAL_STARTED",
    "TRIAL_ENDED",
    "INVOICE_UPDATED",
    "PDF_GENERATED",
    "INVOICE_DOWNLOADED",
]


def upgrade() -> None:
    op.add_column('audit_logs', sa.Column('ip_address', sa.String(length=45), nullable=True))
    op.add_column('audit_logs', sa.Column('actor_role', sa.String(length=50), nullable=True))
    op.add_column('audit_logs', sa.Column('old_value', sa.String(length=1000), nullable=True))
    op.add_column('audit_logs', sa.Column('new_value', sa.String(length=1000), nullable=True))
    op.add_column('audit_logs', sa.Column('remarks', sa.String(length=1000), nullable=True))

    with op.get_context().autocommit_block():
        for value in NEW_AUDIT_EVENT_VALUES:
            op.execute(
                f"ALTER TYPE audit_event_type_enum ADD VALUE IF NOT EXISTS '{value}'"
            )


def downgrade() -> None:
    op.drop_column('audit_logs', 'remarks')
    op.drop_column('audit_logs', 'new_value')
    op.drop_column('audit_logs', 'old_value')
    op.drop_column('audit_logs', 'actor_role')
    op.drop_column('audit_logs', 'ip_address')
    # PostgreSQL cannot drop individual enum values; intentionally a
    # no-op (see every prior audit-event-type migration for the same
    # reasoning).
