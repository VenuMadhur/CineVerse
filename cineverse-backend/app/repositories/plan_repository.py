"""
Data access layer for the Plan entity.
"""
import uuid
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import PlanStatus, SubscriptionStatus
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.repositories.base_repository import BaseRepository


class PlanRepository(BaseRepository[Plan]):
    def __init__(self, db: Session):
        super().__init__(Plan, db)

    def get_by_id(self, plan_id: uuid.UUID) -> Optional[Plan]:
        return super().get_by_id(plan_id)

    def list_by_status(
        self, status: Optional[PlanStatus] = None, skip: int = 0, limit: int = 100
    ) -> List[Plan]:
        stmt = select(Plan)
        if status is not None:
            stmt = stmt.where(Plan.status == status)
        stmt = stmt.order_by(Plan.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count_by_status(self, status: Optional[PlanStatus] = None) -> int:
        stmt = select(Plan)
        if status is not None:
            stmt = stmt.where(Plan.status == status)
        return len(list(self.db.execute(stmt).scalars().all()))

    def get_by_name(self, name: str) -> Optional[Plan]:
        stmt = select(Plan).where(Plan.name == name)
        return self.db.execute(stmt).scalar_one_or_none()

    def count_subscriptions_for_plan(self, plan_id: uuid.UUID) -> int:
        """
        Counts ALL subscriptions ever created against this plan,
        regardless of status (active, paused, cancelled, ...) -- the
        safety gate for deletion. Subscription.plan_id already has an
        ondelete="RESTRICT" foreign key, so the database itself would
        refuse this at the SQL level; this method exists to give a
        clear, friendly error *before* attempting the delete, rather
        than surfacing a raw IntegrityError. Any invoice/payment/
        refund tied to this plan is necessarily tied to one of these
        subscriptions, so this single check transitively covers all
        of them too.
        """
        stmt = select(func.count()).select_from(Subscription).where(Subscription.plan_id == plan_id)
        return self.db.execute(stmt).scalar_one()

    def subscriber_counts_by_plan(self) -> List[tuple]:
        """
        Exact database-level count of currently-ACTIVE subscriptions
        per plan -- reuses the exact same "active" definition as
        DashboardSummaryResponse.active_subscriptions and
        SubscriptionAnalyticsResponse.active_subscriptions
        (status == SubscriptionStatus.ACTIVE specifically). A LEFT
        JOIN from Plan (not an inner join starting from Subscription)
        so a plan with zero active subscribers still appears with
        count 0, rather than being silently omitted from a
        distribution report. Both Plan.id (via the join) and
        Subscription.status/.plan_id are already indexed (see
        app/models/subscription.py), so this aggregates entirely in
        the database and scales with subscription volume, not with
        how many rows get pulled into Python.
        """
        active_subs = (
            select(Subscription.plan_id, Subscription.id)
            .where(Subscription.status == SubscriptionStatus.ACTIVE)
            .subquery()
        )
        stmt = (
            select(Plan.id, Plan.name, func.count(active_subs.c.id))
            .select_from(Plan)
            .outerjoin(active_subs, active_subs.c.plan_id == Plan.id)
            .group_by(Plan.id, Plan.name)
            .order_by(func.count(active_subs.c.id).desc())
        )
        return list(self.db.execute(stmt).all())
