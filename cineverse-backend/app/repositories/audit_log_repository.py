"""
Data access layer for the AuditLog entity.
"""
import uuid
from typing import List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.repositories.base_repository import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, db: Session):
        super().__init__(AuditLog, db)

    def list_for_entity(
        self, entity_type: str, entity_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> List[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id,
            )
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_all(
        self,
        entity_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        stmt = select(AuditLog)
        if entity_type is not None:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        stmt = stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count_all(self, entity_type: Optional[str] = None) -> int:
        stmt = select(func.count()).select_from(AuditLog)
        if entity_type is not None:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        return self.db.execute(stmt).scalar_one()

    def has_event(self, entity_type: str, entity_id: uuid.UUID, event_type) -> bool:
        """
        Phase 6B: used by the reminder scheduler to dedupe -- rather
        than adding a "last_reminded_at" column to Subscription or
        BillingCycle, a reminder is only sent if no audit log entry of
        that event type already exists for this entity.
        """
        stmt = (
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id,
                AuditLog.event_type == event_type,
            )
        )
        return self.db.execute(stmt).scalar_one() > 0

    def _account_filter(self, entity_pairs: List[tuple]):
        """
        `entity_pairs` is a list of (entity_type, entity_id) tuples --
        e.g. [("user", user.id), ("subscription", sub_1.id),
        ("subscription", sub_2.id), ("invoice", inv_1.id), ...].
        Matches any audit log entry belonging to any of them, via OR.
        """
        if not entity_pairs:
            # No entities to match (e.g. a user with no linked
            # customer yet) -- return a condition that matches
            # nothing, rather than an empty OR() which SQLAlchemy
            # would otherwise treat as "always true".
            return AuditLog.id.is_(None)
        return or_(
            *(
                and_(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
                for entity_type, entity_id in entity_pairs
            )
        )

    def list_for_account(
        self, entity_pairs: List[tuple], skip: int = 0, limit: int = 50
    ) -> List[AuditLog]:
        """Account-wide Activity Timeline: every event across every
        entity that belongs to one account (user + their customer +
        all of that customer's subscriptions/invoices/payments/
        refunds), chronological."""
        stmt = (
            select(AuditLog)
            .where(self._account_filter(entity_pairs))
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_for_account(self, entity_pairs: List[tuple]) -> int:
        stmt = (
            select(func.count())
            .select_from(AuditLog)
            .where(self._account_filter(entity_pairs))
        )
        return self.db.execute(stmt).scalar_one()
