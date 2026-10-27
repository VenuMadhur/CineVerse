"""
Data access layer for the Customer entity.
"""
import uuid
from typing import List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.enums import SubscriptionStatus
from app.models.subscription import Subscription
from app.repositories.base_repository import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, db: Session):
        super().__init__(Customer, db)

    def get_by_email(self, email: str) -> Optional[Customer]:
        stmt = select(Customer).where(Customer.email == email)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_user_id(self, user_id: uuid.UUID) -> Optional[Customer]:
        stmt = select(Customer).where(Customer.user_id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(self, skip: int = 0, limit: int = 100, search: Optional[str] = None) -> List[Customer]:
        stmt = select(Customer).order_by(Customer.created_at.desc())
        if search:
            like = f"%{search}%"
            stmt = stmt.where(
                or_(Customer.name.ilike(like), Customer.email.ilike(like))
            )
        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count_search(self, search: Optional[str] = None) -> int:
        """
        Same filter as list_all()'s `search` -- kept as a separate
        method (rather than overloading count()) so the unfiltered
        count() used elsewhere (e.g. dashboard totals) is untouched.
        """
        stmt = select(func.count()).select_from(Customer)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(
                or_(Customer.name.ilike(like), Customer.email.ilike(like))
            )
        return self.db.execute(stmt).scalar_one()

    # ------------------------------------------------------------------
    # Analytics (Phase 2)
    # ------------------------------------------------------------------
    def count_active(self) -> int:
        """
        A customer is "active" if they have at least one subscription
        currently in `active` status (distinct customers, so a
        customer with multiple active subscriptions is only counted
        once).
        """
        return self.count_by_subscription_status(SubscriptionStatus.ACTIVE)

    def count_by_subscription_status(self, status: SubscriptionStatus) -> int:
        """
        Generalization of count_active() to any status -- e.g.
        SubscriptionStatus.TRIAL for "trial customers" or
        SubscriptionStatus.CANCELLED for "cancelled customers" on the
        dashboard (Phase 6A). Counts distinct customers with at least
        one subscription in the given status; a customer with two
        cancelled subscriptions is only counted once.
        """
        subquery = (
            select(Subscription.customer_id)
            .where(Subscription.status == status)
            .distinct()
            .subquery()
        )
        stmt = select(func.count()).select_from(subquery)
        return self.db.execute(stmt).scalar_one()

    def registration_trend_by_month(self, date_from=None, date_to=None) -> List[tuple]:
        """
        Returns (month, new_customers) rows, ordered chronologically.
        Mirrors InvoiceRepository.revenue_by_month's exact
        func.date_trunc grouping pattern. Unlike revenue/refund
        trends, there's no status filter here -- Customer.created_at
        is set exactly once, at registration, and never changes, so
        every customer row genuinely represents a real historical
        registration event.
        """
        month_expr = func.date_trunc("month", Customer.created_at)
        stmt = (
            select(month_expr.label("month"), func.count(Customer.id))
            .group_by(month_expr)
            .order_by(month_expr)
        )
        if date_from is not None:
            stmt = stmt.where(Customer.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Customer.created_at <= date_to)
        return list(self.db.execute(stmt).all())
