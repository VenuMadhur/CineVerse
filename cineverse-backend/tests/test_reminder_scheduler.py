"""
Tests for the trial-ending / renewal reminder scheduler
(ReminderSchedulerService), verifying reminders are sent for
subscriptions/cycles within the configured window, deduped via the
audit log so a second scheduler run never double-sends.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models.billing_cycle import BillingCycle
from app.models.customer import Customer
from app.models.enums import BillingInterval, SubscriptionStatus
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.scheduler.reminder_scheduler_service import ReminderSchedulerService


def _make_customer_and_plan(db_session, trial_period_days=14):
    plan = Plan(
        name=f"Reminder Plan {uuid.uuid4().hex[:6]}",
        price=29.00,
        billing_interval=BillingInterval.MONTHLY,
        trial_period_days=trial_period_days,
    )
    db_session.add(plan)
    db_session.flush()

    customer = Customer(
        name="Reminder Customer",
        email=f"reminder_{uuid.uuid4().hex[:6]}@test.com",
        country="US",
    )
    db_session.add(customer)
    db_session.flush()
    return customer, plan


def _make_trial_subscription_ending_in(db_session, days_from_now):
    customer, plan = _make_customer_and_plan(db_session)
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        customer_id=customer.id,
        plan_id=plan.id,
        status=SubscriptionStatus.TRIAL,
        trial_started_at=now - timedelta(days=1),
        trial_ends_at=now + timedelta(days=days_from_now),
    )
    db_session.add(subscription)
    db_session.commit()
    return subscription, plan


def _make_active_subscription_with_cycle_renewing_in(db_session, days_from_now):
    customer, plan = _make_customer_and_plan(db_session, trial_period_days=0)
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        customer_id=customer.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        activated_at=now - timedelta(days=27),
    )
    db_session.add(subscription)
    db_session.flush()

    cycle = BillingCycle(
        subscription_id=subscription.id,
        cycle_start_date=now - timedelta(days=27),
        cycle_end_date=now + timedelta(days=days_from_now),
        renewal_date=now + timedelta(days=days_from_now),
        next_billing_date=now + timedelta(days=days_from_now),
        is_billed=False,
    )
    db_session.add(cycle)
    db_session.commit()
    return subscription, plan, cycle


@patch("app.scheduler.reminder_scheduler_service.notify")
def test_sends_trial_ending_reminder_within_window(mock_notify, db_session):
    subscription, plan = _make_trial_subscription_ending_in(db_session, days_from_now=2)

    summary = ReminderSchedulerService(db_session).run()

    assert summary["trial_reminders_sent"] == 1
    mock_notify.assert_called_once()
    args = mock_notify.call_args[0]
    assert args[0] == "trial_ending_reminder"
    assert args[1] == subscription.customer_id


@patch("app.scheduler.reminder_scheduler_service.notify")
def test_no_trial_reminder_outside_window(mock_notify, db_session):
    _make_trial_subscription_ending_in(db_session, days_from_now=30)  # far in the future

    summary = ReminderSchedulerService(db_session).run()

    assert summary["trial_reminders_sent"] == 0
    mock_notify.assert_not_called()


@patch("app.scheduler.reminder_scheduler_service.notify")
def test_trial_reminder_is_not_sent_twice(mock_notify, db_session):
    _make_trial_subscription_ending_in(db_session, days_from_now=1)

    scheduler = ReminderSchedulerService(db_session)
    first = scheduler.run()
    second = scheduler.run()

    assert first["trial_reminders_sent"] == 1
    assert second["trial_reminders_sent"] == 0  # deduped via the audit log
    mock_notify.assert_called_once()


@patch("app.scheduler.reminder_scheduler_service.notify")
def test_sends_renewal_reminder_within_window(mock_notify, db_session):
    subscription, plan, cycle = _make_active_subscription_with_cycle_renewing_in(
        db_session, days_from_now=2
    )

    summary = ReminderSchedulerService(db_session).run()

    assert summary["renewal_reminders_sent"] == 1
    mock_notify.assert_called_once()
    args = mock_notify.call_args[0]
    assert args[0] == "renewal_reminder"
    assert args[1] == subscription.customer_id


@patch("app.scheduler.reminder_scheduler_service.notify")
def test_no_renewal_reminder_for_already_due_cycle(mock_notify, db_session):
    """
    A cycle that's already *due* (next_billing_date in the past)
    belongs to the billing scheduler, not the reminder scheduler --
    list_upcoming_within only looks ahead, never behind.
    """
    _make_active_subscription_with_cycle_renewing_in(db_session, days_from_now=-1)

    summary = ReminderSchedulerService(db_session).run()

    assert summary["renewal_reminders_sent"] == 0
    mock_notify.assert_not_called()


@patch("app.scheduler.reminder_scheduler_service.notify")
def test_no_renewal_reminder_outside_window(mock_notify, db_session):
    _make_active_subscription_with_cycle_renewing_in(db_session, days_from_now=30)

    summary = ReminderSchedulerService(db_session).run()

    assert summary["renewal_reminders_sent"] == 0
    mock_notify.assert_not_called()


@patch("app.scheduler.reminder_scheduler_service.notify")
def test_renewal_reminder_is_not_sent_twice(mock_notify, db_session):
    _make_active_subscription_with_cycle_renewing_in(db_session, days_from_now=1)

    scheduler = ReminderSchedulerService(db_session)
    first = scheduler.run()
    second = scheduler.run()

    assert first["renewal_reminders_sent"] == 1
    assert second["renewal_reminders_sent"] == 0
    mock_notify.assert_called_once()


@patch("app.scheduler.reminder_scheduler_service.notify")
def test_both_reminder_types_in_a_single_run(mock_notify, db_session):
    _make_trial_subscription_ending_in(db_session, days_from_now=1)
    _make_active_subscription_with_cycle_renewing_in(db_session, days_from_now=1)

    summary = ReminderSchedulerService(db_session).run()

    assert summary["trial_reminders_sent"] == 1
    assert summary["renewal_reminders_sent"] == 1
    assert mock_notify.call_count == 2
