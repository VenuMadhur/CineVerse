"""
Data access layer for the Subscription entity and its status history.
"""
import uuid
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.customer import Customer
from app.models.enums import BillingInterval, SubscriptionStatus
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatusHistory
from app.repositories.base_repository import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    def __init__(self, db: Session):
        super().__init__(Subscription, db)

    def get_by_id(self, subscription_id: uuid.UUID) -> Optional[Subscription]:
        stmt = (
            select(Subscription)
            .where(Subscription.id == subscription_id)
            .options(selectinload(Subscription.status_history))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_id_for_update(self, subscription_id: uuid.UUID) -> Optional[Subscription]:
        """
        Same as get_by_id(), but takes a row-level lock (SELECT ...
        FOR UPDATE) so a second concurrent call for the same
        subscription blocks until this transaction commits, instead of
        both reading the same pre-transition status and both
        proceeding. Confirmed fix for a real, reproduced bug: firing
        concurrent immediate-cancel requests (e.g. an accidental
        double-click landing as two near-simultaneous requests) could
        let both read status=ACTIVE before either committed, both
        pass the state machine check, and both issue a refund for the
        same cancellation event.

        Deliberately a separate method from get_by_id() rather than
        adding a flag to every existing call site -- only the specific
        state-mutating operations that need this protection use it.
        """
        stmt = (
            select(Subscription)
            .where(Subscription.id == subscription_id)
            .options(selectinload(Subscription.status_history))
            .with_for_update()
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def _filtered_query(
        self,
        status: Optional[SubscriptionStatus] = None,
        customer_id: Optional[uuid.UUID] = None,
    ):
        stmt = select(Subscription)
        if status is not None:
            stmt = stmt.where(Subscription.status == status)
        if customer_id is not None:
            stmt = stmt.where(Subscription.customer_id == customer_id)
        return stmt

    def list_all(
        self,
        status: Optional[SubscriptionStatus] = None,
        customer_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Subscription]:
        stmt = (
            self._filtered_query(status, customer_id)
            .order_by(Subscription.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_all(
        self,
        status: Optional[SubscriptionStatus] = None,
        customer_id: Optional[uuid.UUID] = None,
    ) -> int:
        stmt = select(func.count()).select_from(
            self._filtered_query(status, customer_id).subquery()
        )
        return self.db.execute(stmt).scalar_one()

    def list_due_for_renewal(self, as_of) -> List[Subscription]:
        """Used by the Celery Beat billing scheduler."""
        from app.models.billing_cycle import BillingCycle

        stmt = (
            select(Subscription)
            .join(BillingCycle, BillingCycle.subscription_id == Subscription.id)
            .where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                BillingCycle.next_billing_date <= as_of,
                BillingCycle.is_billed.is_(False),
            )
        )
        return list(self.db.execute(stmt).scalars().unique().all())

    def add_status_history(
        self, history: SubscriptionStatusHistory
    ) -> SubscriptionStatusHistory:
        self.db.add(history)
        self.db.flush()
        return history

    # ------------------------------------------------------------------
    # Analytics (Phase 6A: MRR / ARR)
    # ------------------------------------------------------------------
    def monthly_recurring_revenue(self) -> Decimal:
        """
        MRR: the sum of each currently-`active` subscription's plan
        price, normalized to a monthly figure (an annual plan's price
        is divided by 12). ARR is simply this value x 12 -- computed
        in AnalyticsService, not duplicated here.

        Deliberately based on `active` subscriptions only -- `trial`
        subscriptions aren't yet paying, so they don't contribute to
        *recurring revenue* (a forward-looking metric), even though
        they do count toward `trial_customers` on the dashboard.
        """
        monthly_price = case(
            (Plan.billing_interval == BillingInterval.ANNUAL, Plan.price / 12),
            else_=Plan.price,
        )
        stmt = (
            select(func.coalesce(func.sum(monthly_price), 0))
            .select_from(Subscription)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(Subscription.status == SubscriptionStatus.ACTIVE)
        )
        return self.db.execute(stmt).scalar_one()

    def monthly_recurring_revenue_by_currency(self) -> List[tuple]:
        """
        Same figure as monthly_recurring_revenue(), broken out by
        Plan.currency instead of blindly summed across all of them --
        currency is unconstrained per-plan, so a single blended MRR
        number is potentially meaningless the moment more than one
        currency is genuinely in use.
        """
        monthly_price = case(
            (Plan.billing_interval == BillingInterval.ANNUAL, Plan.price / 12),
            else_=Plan.price,
        )
        stmt = (
            select(Plan.currency, func.sum(monthly_price))
            .select_from(Subscription)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(Subscription.status == SubscriptionStatus.ACTIVE)
            .group_by(Plan.currency)
            .order_by(func.sum(monthly_price).desc())
        )
        return list(self.db.execute(stmt).all())

    def monthly_recurring_revenue_by_plan(self) -> List[tuple]:
        """
        Same figure as monthly_recurring_revenue(), broken out by
        which plan contributes it -- the exact same billing-interval
        normalization (annual price / 12) as monthly_recurring_revenue
        and monthly_recurring_revenue_by_currency, just grouped by
        Plan instead. This is a CURRENT-STATE composition (today's
        active subscriptions x today's plan prices), not a historical
        trend -- there is no plan-price history table anywhere in this
        schema, so no month-over-month MRR figure could be honestly
        reconstructed (see the Admin Dashboard's own module docstring
        for the full reasoning).
        """
        monthly_price = case(
            (Plan.billing_interval == BillingInterval.ANNUAL, Plan.price / 12),
            else_=Plan.price,
        )
        stmt = (
            select(Plan.id, Plan.name, Plan.currency, func.sum(monthly_price))
            .select_from(Subscription)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(Subscription.status == SubscriptionStatus.ACTIVE)
            .group_by(Plan.id, Plan.name, Plan.currency)
            .order_by(func.sum(monthly_price).desc())
        )
        return list(self.db.execute(stmt).all())

    def list_trial_ending_within(self, as_of, until) -> List[Subscription]:
        """
        Subscriptions still in `trial` whose trial ends between `as_of`
        and `until` -- the candidate set for the trial-ending reminder
        (Phase 6B). Deduping against already-sent reminders happens in
        the scheduler service via the audit log, not here.
        """
        stmt = select(Subscription).where(
            Subscription.status == SubscriptionStatus.TRIAL,
            Subscription.trial_ends_at >= as_of,
            Subscription.trial_ends_at <= until,
        )
        return list(self.db.execute(stmt).scalars().all())

    # ------------------------------------------------------------------
    # Analytics (Module 3, Phase 3a)
    #
    # Pure querying/aggregation only -- every ratio/rate calculation
    # (trial conversion %, churn %, ARPU, CLV, growth net) is computed
    # in AnalyticsService from the raw counts these methods return.
    # ------------------------------------------------------------------
    def trial_exit_counts(self) -> dict:
        """
        For every subscription that has ever left TRIAL (its first and
        only transition with from_status=TRIAL -- a subscription can
        only be in TRIAL once, as the initial state, per the state
        machine), returns {to_status: count}. A subscription later
        cancelled *after* converting (TRIAL->ACTIVE->CANCELLED) is
        correctly counted as "converted", not "cancelled from trial" --
        only the transition *out of* TRIAL itself is counted, not any
        later transition.
        """
        stmt = (
            select(SubscriptionStatusHistory.to_status, func.count())
            .where(SubscriptionStatusHistory.from_status == SubscriptionStatus.TRIAL)
            .group_by(SubscriptionStatusHistory.to_status)
        )
        return dict(self.db.execute(stmt).all())

    def count_active_as_of(self, as_of) -> int:
        """
        Point-in-time count: subscriptions whose most recent status
        transition at or before `as_of` moved them to ACTIVE. Needed
        for churn rate's denominator ("active at the start of the
        period"), which count_all(status=ACTIVE) cannot answer -- that
        only reflects *current* status, not status as of a past date.
        """
        latest_per_subscription = (
            select(
                SubscriptionStatusHistory.subscription_id,
                SubscriptionStatusHistory.to_status,
                func.row_number()
                .over(
                    partition_by=SubscriptionStatusHistory.subscription_id,
                    order_by=SubscriptionStatusHistory.created_at.desc(),
                )
                .label("rn"),
            )
            .where(SubscriptionStatusHistory.created_at <= as_of)
            .subquery()
        )
        stmt = select(func.count()).select_from(latest_per_subscription).where(
            latest_per_subscription.c.rn == 1,
            latest_per_subscription.c.to_status == SubscriptionStatus.ACTIVE,
        )
        return self.db.execute(stmt).scalar_one()

    def count_cancelled_between(self, date_from, date_to) -> int:
        """Subscriptions with a CANCELLED status_history entry within [date_from, date_to]."""
        stmt = select(func.count(func.distinct(SubscriptionStatusHistory.subscription_id))).where(
            SubscriptionStatusHistory.to_status == SubscriptionStatus.CANCELLED,
            SubscriptionStatusHistory.created_at >= date_from,
            SubscriptionStatusHistory.created_at <= date_to,
        )
        return self.db.execute(stmt).scalar_one()

    def monthly_subscription_growth(self, date_from=None, date_to=None) -> List[tuple]:
        """
        Returns (month, new_count, cancelled_count) rows, chronological.
        "New" = Subscription.created_at in that month (when the
        subscription record itself was created, matching the metric's
        literal name -- not a status transition). "Cancelled" = a
        CANCELLED status_history entry in that month.
        """
        new_month_expr = func.date_trunc("month", Subscription.created_at)
        new_stmt = select(new_month_expr.label("month"), func.count()).group_by(new_month_expr)
        if date_from is not None:
            new_stmt = new_stmt.where(Subscription.created_at >= date_from)
        if date_to is not None:
            new_stmt = new_stmt.where(Subscription.created_at <= date_to)
        new_by_month = dict(self.db.execute(new_stmt).all())

        cancelled_month_expr = func.date_trunc("month", SubscriptionStatusHistory.created_at)
        cancelled_stmt = (
            select(cancelled_month_expr.label("month"), func.count(func.distinct(SubscriptionStatusHistory.subscription_id)))
            .where(SubscriptionStatusHistory.to_status == SubscriptionStatus.CANCELLED)
            .group_by(cancelled_month_expr)
        )
        if date_from is not None:
            cancelled_stmt = cancelled_stmt.where(SubscriptionStatusHistory.created_at >= date_from)
        if date_to is not None:
            cancelled_stmt = cancelled_stmt.where(SubscriptionStatusHistory.created_at <= date_to)
        cancelled_by_month = dict(self.db.execute(cancelled_stmt).all())

        all_months = sorted(set(new_by_month.keys()) | set(cancelled_by_month.keys()))
        return [
            (month, new_by_month.get(month, 0), cancelled_by_month.get(month, 0))
            for month in all_months
        ]

    def customers_by_status(self, status: SubscriptionStatus) -> List[tuple]:
        """
        Returns (customer_id, customer_name, customer_email, plan_name,
        subscription_id) rows for every customer whose *current*
        subscription status matches -- used by Module 3, Phase 3c's
        "Customers in Past Due" report (status=PAST_DUE), but written
        generically enough to reuse for any status.
        """
        stmt = (
            select(
                Customer.id,
                Customer.name,
                Customer.email,
                Plan.name,
                Subscription.id,
            )
            .join(Customer, Customer.id == Subscription.customer_id)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(Subscription.status == status)
            .order_by(Subscription.updated_at.desc())
        )
        return list(self.db.execute(stmt).all())

    def customers_cancelled_for_payment_failure(self) -> List[tuple]:
        """
        Returns (customer_id, customer_name, customer_email, plan_name,
        cancelled_at) rows for Module 3, Phase 3d's "Cancelled Due to
        Payment Failure" operational report. Identified by the exact
        `reason` string RetrySchedulerService._exhaust_retries()
        (Phase 1b) writes when a subscription is auto-cancelled after
        all configured retry attempts fail -- reuses
        SubscriptionStatusHistory exactly as trial_exit_counts()/
        count_cancelled_between() above already do, rather than
        parsing the audit log or adding a new column to mark this.
        """
        stmt = (
            select(
                Customer.id,
                Customer.name,
                Customer.email,
                Plan.name,
                SubscriptionStatusHistory.created_at,
            )
            .join(Subscription, Subscription.id == SubscriptionStatusHistory.subscription_id)
            .join(Customer, Customer.id == Subscription.customer_id)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(
                SubscriptionStatusHistory.to_status == SubscriptionStatus.CANCELLED,
                SubscriptionStatusHistory.reason == "All configured payment retry attempts failed",
            )
            .order_by(SubscriptionStatusHistory.created_at.desc())
        )
        return list(self.db.execute(stmt).all())
