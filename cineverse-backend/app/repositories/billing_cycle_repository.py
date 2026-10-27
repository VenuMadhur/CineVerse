"""
Data access layer for the BillingCycle entity.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.billing_cycle import BillingCycle
from app.models.customer import Customer
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.repositories.base_repository import BaseRepository


class BillingCycleRepository(BaseRepository[BillingCycle]):
    def __init__(self, db: Session):
        super().__init__(BillingCycle, db)

    def get_current_for_subscription(
        self, subscription_id: uuid.UUID
    ) -> Optional[BillingCycle]:
        stmt = (
            select(BillingCycle)
            .where(
                BillingCycle.subscription_id == subscription_id,
                BillingCycle.is_billed.is_(False),
            )
            .order_by(BillingCycle.cycle_start_date.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_subscription(
        self, subscription_id: uuid.UUID
    ) -> List[BillingCycle]:
        stmt = (
            select(BillingCycle)
            .where(BillingCycle.subscription_id == subscription_id)
            .order_by(BillingCycle.cycle_start_date.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_due(self, as_of: datetime) -> List[BillingCycle]:
        stmt = select(BillingCycle).where(
            BillingCycle.next_billing_date <= as_of,
            BillingCycle.is_billed.is_(False),
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_upcoming_within(self, as_of: datetime, until: datetime) -> List[BillingCycle]:
        """
        Unbilled cycles whose renewal is coming up between `as_of` and
        `until` -- the candidate set for the renewal reminder (Phase
        6B). Distinct from `list_due`, which finds cycles that are
        *already* due (used by the actual billing scheduler); this
        finds ones approaching, before they're due.
        """
        stmt = select(BillingCycle).where(
            BillingCycle.next_billing_date > as_of,
            BillingCycle.next_billing_date <= until,
            BillingCycle.is_billed.is_(False),
        )
        return list(self.db.execute(stmt).scalars().all())

    def customers_near_renewal(self, as_of: datetime, until: datetime) -> List[tuple]:
        """
        Returns (customer_id, customer_name, customer_email, plan_name,
        renewal_date) rows for Module 3, Phase 3c's "Customers Near
        Renewal" report -- same underlying due-window as
        list_upcoming_within (Phase 6B's reminder), joined through to
        full customer/plan detail for row-level reporting rather than
        just the BillingCycle objects.
        """
        stmt = (
            select(
                Customer.id,
                Customer.name,
                Customer.email,
                Plan.name,
                BillingCycle.next_billing_date,
            )
            .join(Subscription, Subscription.id == BillingCycle.subscription_id)
            .join(Customer, Customer.id == Subscription.customer_id)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(
                BillingCycle.next_billing_date > as_of,
                BillingCycle.next_billing_date <= until,
                BillingCycle.is_billed.is_(False),
            )
            .order_by(BillingCycle.next_billing_date.asc())
        )
        return list(self.db.execute(stmt).all())
