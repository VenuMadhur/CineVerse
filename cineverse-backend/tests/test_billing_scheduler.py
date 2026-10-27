"""
Tests for the Celery Beat billing scheduler logic
(BillingSchedulerService), verifying that due subscriptions get
invoiced, their billing cycle advances, and end-of-cycle
cancellations are finalized.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.models.customer import Customer
from app.models.enums import BillingInterval, InvoiceStatus, SubscriptionStatus
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.repositories.billing_cycle_repository import BillingCycleRepository
from app.scheduler.billing_scheduler_service import BillingSchedulerService


def _make_active_subscription_with_due_cycle(db_session, cancel_at_period_end=False):
    plan = Plan(
        name=f"Scheduler Plan {uuid.uuid4().hex[:6]}",
        price=39.00,
        billing_interval=BillingInterval.MONTHLY,
        trial_period_days=0,
    )
    db_session.add(plan)
    db_session.flush()

    customer = Customer(
        name="Scheduler Customer",
        email=f"scheduler_{uuid.uuid4().hex[:6]}@test.com",
        country="US",
    )
    db_session.add(customer)
    db_session.flush()

    subscription = Subscription(
        customer_id=customer.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        activated_at=datetime.now(timezone.utc),
        cancel_at_period_end=cancel_at_period_end,
    )
    db_session.add(subscription)
    db_session.flush()

    from app.models.billing_cycle import BillingCycle

    now = datetime.now(timezone.utc)
    cycle = BillingCycle(
        subscription_id=subscription.id,
        cycle_start_date=now - timedelta(days=30),
        cycle_end_date=now,
        renewal_date=now,
        next_billing_date=now - timedelta(minutes=1),  # already due
        is_billed=False,
    )
    db_session.add(cycle)
    db_session.commit()

    return subscription, plan, cycle


def test_scheduler_generates_invoice_and_advances_cycle(db_session):
    subscription, plan, cycle = _make_active_subscription_with_due_cycle(db_session)

    scheduler = BillingSchedulerService(db_session)
    summary = scheduler.run()

    assert summary["subscriptions_processed"] == 1
    assert len(summary["invoices_created"]) == 1

    db_session.refresh(cycle)
    assert cycle.is_billed is True

    cycle_repo = BillingCycleRepository(db_session)
    cycles = cycle_repo.list_for_subscription(subscription.id)
    assert len(cycles) == 2  # original + newly created next cycle

    from app.models.invoice import Invoice
    from sqlalchemy import select

    invoice = db_session.execute(
        select(Invoice).where(Invoice.subscription_id == subscription.id)
    ).scalar_one()
    assert invoice.status == InvoiceStatus.OPEN
    # Module 2: the invoice now includes tax (US = 8% configured rate)
    # on top of the plan price, rather than a flat total == plan price.
    assert float(invoice.subtotal) == 39.00
    assert float(invoice.tax_amount) == 3.12
    assert float(invoice.total_amount) == 42.12


def test_scheduler_finalizes_end_of_cycle_cancellation(db_session):
    subscription, plan, cycle = _make_active_subscription_with_due_cycle(
        db_session, cancel_at_period_end=True
    )

    scheduler = BillingSchedulerService(db_session)
    summary = scheduler.run()

    assert summary["subscriptions_cancelled"] == 1
    assert summary["invoices_created"] == []

    db_session.refresh(subscription)
    assert subscription.status == SubscriptionStatus.CANCELLED
    assert subscription.cancelled_at is not None


def test_scheduler_skips_cycles_not_yet_due(db_session):
    plan = Plan(
        name=f"Future Plan {uuid.uuid4().hex[:6]}",
        price=10.00,
        billing_interval=BillingInterval.MONTHLY,
    )
    db_session.add(plan)
    db_session.flush()

    customer = Customer(
        name="Future Customer",
        email=f"future_{uuid.uuid4().hex[:6]}@test.com",
        country="US",
    )
    db_session.add(customer)
    db_session.flush()

    subscription = Subscription(
        customer_id=customer.id, plan_id=plan.id, status=SubscriptionStatus.ACTIVE
    )
    db_session.add(subscription)
    db_session.flush()

    from app.models.billing_cycle import BillingCycle

    now = datetime.now(timezone.utc)
    cycle = BillingCycle(
        subscription_id=subscription.id,
        cycle_start_date=now,
        cycle_end_date=now + timedelta(days=30),
        renewal_date=now + timedelta(days=30),
        next_billing_date=now + timedelta(days=30),  # not due yet
        is_billed=False,
    )
    db_session.add(cycle)
    db_session.commit()

    summary = BillingSchedulerService(db_session).run()
    assert summary["subscriptions_processed"] == 0
