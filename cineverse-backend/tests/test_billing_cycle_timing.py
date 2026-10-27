"""
Tests for the billing-cycle timing fix: a subscription must be
invoiced at the START of the period being paid for ("bill in
advance"), not only once that period has already ended ("bill in
arrears"). Before this fix, both create_initial_cycle() and
advance_cycle() set next_billing_date = cycle_end_date, meaning a
brand-new subscriber (or any renewal) would silently get a full extra
billing period free before ever being invoiced -- exactly the
"subscribe + activate but Invoices/Payments stay empty" symptom this
fixes.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.models.customer import Customer
from app.models.enums import BillingInterval
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatus
from app.scheduler.billing_scheduler_service import BillingSchedulerService
from app.services.billing_cycle_service import BillingCycleService


def _make_subscription_row(db_session, status=SubscriptionStatus.ACTIVE):
    """A real Subscription row (billing_cycles has an FK to it)."""
    plan = Plan(
        name=f"Timing Plan {uuid.uuid4().hex[:6]}",
        price=25.00,
        billing_interval=BillingInterval.MONTHLY,
        trial_period_days=0,
    )
    db_session.add(plan)
    db_session.flush()
    customer = Customer(
        name="Timing Customer", email=f"timing_{uuid.uuid4().hex[:6]}@test.com", country="US"
    )
    db_session.add(customer)
    db_session.flush()
    subscription = Subscription(
        customer_id=customer.id,
        plan_id=plan.id,
        status=status,
        activated_at=datetime.now(timezone.utc) if status == SubscriptionStatus.ACTIVE else None,
    )
    db_session.add(subscription)
    db_session.flush()
    return subscription


def test_initial_cycle_bills_at_cycle_start_not_cycle_end(db_session):
    subscription = _make_subscription_row(db_session)
    service = BillingCycleService(db_session)
    start = datetime.now(timezone.utc)

    cycle = service.create_initial_cycle(
        subscription_id=subscription.id,
        billing_interval=BillingInterval.MONTHLY,
        start_date=start,
    )

    assert cycle.next_billing_date == cycle.cycle_start_date
    assert cycle.next_billing_date == start
    assert cycle.next_billing_date != cycle.cycle_end_date


def test_advance_cycle_also_bills_next_period_in_advance(db_session):
    subscription = _make_subscription_row(db_session)
    service = BillingCycleService(db_session)
    initial = service.create_initial_cycle(
        subscription_id=subscription.id,
        billing_interval=BillingInterval.MONTHLY,
        start_date=datetime.now(timezone.utc),
    )
    db_session.commit()

    next_cycle = service.advance_cycle(
        subscription_id=subscription.id, billing_interval=BillingInterval.MONTHLY
    )

    assert next_cycle.next_billing_date == next_cycle.cycle_start_date
    assert next_cycle.cycle_start_date == initial.cycle_end_date


def test_no_trial_subscription_is_immediately_due_for_its_first_invoice(
    client, auth_headers, admin_auth_headers, db_session
):
    """
    End-to-end reproduction of the reported symptom: create a
    subscription on a no-trial plan, activate it, then run the real
    scheduler service immediately (no time-travel/backdating needed --
    that's the whole point of the fix) and confirm an invoice exists.
    """
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": "Immediate Billing Plan",
            "price": 25.00,
            "billing_interval": "monthly",
            "trial_period_days": 0,
        },
    ).json()
    customer_resp = client.get(
        "/api/v1/customers/me",
        headers=auth_headers,
    )
    assert customer_resp.status_code == 200, customer_resp.json()
    customer = customer_resp.json()
    client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    )
    sub = client.get(
        "/api/v1/subscriptions", params={"customer_id": customer["id"]}, headers=auth_headers
    ).json()["items"][0]
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=auth_headers)

    # Confirm truly empty right after activation (matches the reported
    # observation) -- this part is expected, not the bug.
    invoices_before = client.get(
        "/api/v1/invoices", params={"customer_id": customer["id"]}, headers=auth_headers
    ).json()
    assert invoices_before["total"] == 0

    # Run the real scheduler (exactly what Celery Beat invokes
    # periodically) -- no backdating required, since the fix makes the
    # cycle due immediately.
    summary = BillingSchedulerService(db_session).run()
    assert len(summary["invoices_created"]) >= 1

    invoices_after = client.get(
        "/api/v1/invoices", params={"customer_id": customer["id"]}, headers=auth_headers
    ).json()
    assert invoices_after["total"] == 1
    assert invoices_after["items"][0]["status"] == "open"


def test_trial_subscription_is_due_exactly_when_trial_ends_not_a_full_cycle_later(
    client, auth_headers, admin_auth_headers, db_session
):
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": "Trial Timing Plan",
            "price": 15.00,
            "billing_interval": "monthly",
            "trial_period_days": 14,
        },
    ).json()
    customer_resp = client.get(
        "/api/v1/customers/me",
        headers=auth_headers,
    )
    assert customer_resp.status_code == 200, customer_resp.json()
    customer = customer_resp.json()
    client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    )

    # Immediately after subscribing (still well within the 14-day
    # trial), the scheduler must NOT invoice yet.
    summary_during_trial = BillingSchedulerService(db_session).run()
    assert summary_during_trial["invoices_created"] == []

    # Simulate the trial having ended. With the fix, the cycle becomes
    # due exactly at trial_ends_at -- not a further full cycle after
    # that, which is what the pre-fix bug would have required.
    future = datetime.now(timezone.utc) + timedelta(days=15)
    summary_after_trial = BillingSchedulerService(db_session).run(as_of=future)
    assert len(summary_after_trial["invoices_created"]) == 1

    invoices = client.get(
        "/api/v1/invoices", params={"customer_id": customer["id"]}, headers=auth_headers
    ).json()
    assert invoices["total"] == 1
