"""
Repository-level tests for the new Phase 3a aggregation methods
(trial_exit_counts, count_active_as_of, count_cancelled_between,
monthly_subscription_growth) -- verified against known, directly
constructed data before any ratio/business logic is layered on top in
AnalyticsService.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.models.customer import Customer
from app.models.enums import BillingInterval, SubscriptionStatus
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatusHistory
from app.repositories.subscription_repository import SubscriptionRepository


def _make_customer_and_plan(db_session):
    plan = Plan(
        name=f"KPI Plan {uuid.uuid4().hex[:6]}",
        price=50,
        billing_interval=BillingInterval.MONTHLY,
        trial_period_days=14,
    )
    db_session.add(plan)
    db_session.flush()
    customer = Customer(name="KPI Customer", email=f"kpi_{uuid.uuid4().hex[:6]}@test.com", country="US")
    db_session.add(customer)
    db_session.flush()
    return customer, plan


def _make_subscription(db_session, status, created_at=None):
    customer, plan = _make_customer_and_plan(db_session)
    sub = Subscription(
        customer_id=customer.id,
        plan_id=plan.id,
        status=status,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db_session.add(sub)
    db_session.flush()
    return sub


def _add_history(db_session, sub, from_status, to_status, created_at=None):
    history = SubscriptionStatusHistory(
        subscription_id=sub.id,
        from_status=from_status,
        to_status=to_status,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db_session.add(history)
    db_session.flush()


def test_trial_exit_counts_converted_vs_cancelled(db_session):
    repo = SubscriptionRepository(db_session)

    converted = _make_subscription(db_session, SubscriptionStatus.ACTIVE)
    _add_history(db_session, converted, SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE)

    cancelled_from_trial = _make_subscription(db_session, SubscriptionStatus.CANCELLED)
    _add_history(
        db_session, cancelled_from_trial, SubscriptionStatus.TRIAL, SubscriptionStatus.CANCELLED
    )

    still_in_trial = _make_subscription(db_session, SubscriptionStatus.TRIAL)
    # No history row at all -- never exited trial, must not be counted either way.
    db_session.commit()

    counts = repo.trial_exit_counts()
    assert counts.get(SubscriptionStatus.ACTIVE, 0) == 1
    assert counts.get(SubscriptionStatus.CANCELLED, 0) == 1
    assert still_in_trial.id is not None  # sanity: exists but contributes nothing above


def test_trial_exit_counts_excludes_post_conversion_cancellation(db_session):
    """
    A subscription that converted (TRIAL->ACTIVE) and was *later*
    cancelled (ACTIVE->CANCELLED) must count as "converted", not
    "cancelled from trial" -- only the transition whose from_status is
    literally TRIAL counts.
    """
    repo = SubscriptionRepository(db_session)
    sub = _make_subscription(db_session, SubscriptionStatus.CANCELLED)
    _add_history(db_session, sub, SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE)
    _add_history(db_session, sub, SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED)
    db_session.commit()

    counts = repo.trial_exit_counts()
    assert counts.get(SubscriptionStatus.ACTIVE, 0) == 1
    assert counts.get(SubscriptionStatus.CANCELLED, 0) == 0


def test_count_active_as_of_point_in_time(db_session):
    repo = SubscriptionRepository(db_session)
    now = datetime.now(timezone.utc)

    sub = _make_subscription(db_session, SubscriptionStatus.CANCELLED)
    _add_history(
        db_session, sub, SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE,
        created_at=now - timedelta(days=10),
    )
    _add_history(
        db_session, sub, SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED,
        created_at=now - timedelta(days=2),
    )
    db_session.commit()

    # 5 days ago: was active (activated 10 days ago, cancelled only 2 days ago).
    assert repo.count_active_as_of(now - timedelta(days=5)) == 1
    # Right now: no longer active (cancelled 2 days ago).
    assert repo.count_active_as_of(now) == 0
    # Before it was ever activated: not active yet.
    assert repo.count_active_as_of(now - timedelta(days=15)) == 0


def test_count_cancelled_between(db_session):
    repo = SubscriptionRepository(db_session)
    now = datetime.now(timezone.utc)

    in_range = _make_subscription(db_session, SubscriptionStatus.CANCELLED)
    _add_history(
        db_session, in_range, SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED,
        created_at=now - timedelta(days=5),
    )
    out_of_range = _make_subscription(db_session, SubscriptionStatus.CANCELLED)
    _add_history(
        db_session, out_of_range, SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED,
        created_at=now - timedelta(days=60),
    )
    db_session.commit()

    count = repo.count_cancelled_between(now - timedelta(days=10), now)
    assert count == 1


def test_monthly_subscription_growth_net(db_session):
    repo = SubscriptionRepository(db_session)
    this_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    _make_subscription(db_session, SubscriptionStatus.ACTIVE, created_at=this_month_start + timedelta(days=1))
    new_sub_2 = _make_subscription(db_session, SubscriptionStatus.CANCELLED, created_at=this_month_start + timedelta(days=2))
    _add_history(
        db_session, new_sub_2, SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED,
        created_at=this_month_start + timedelta(days=3),
    )
    db_session.commit()

    rows = repo.monthly_subscription_growth(this_month_start, this_month_start + timedelta(days=31))
    assert len(rows) == 1
    month, new_count, cancelled_count = rows[0]
    assert new_count == 2  # both subs created this month
    assert cancelled_count == 1  # one of them also cancelled this month
