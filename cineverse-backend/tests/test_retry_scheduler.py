"""
Tests for Failed Payment Retry execution (Module 3, Phase 1b):
enqueueing on failure, and the event-driven scheduler processing due
queue entries (success, failure-with-more-attempts,
failure-with-attempts-exhausted).
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models.enums import RetryStatus
from app.models.retry_queue import RetryQueue
from app.scheduler.retry_scheduler_service import RetrySchedulerService


def _configure_retries(client, admin_auth_headers, schedule=((1, 1), (2, 3), (3, 7))):
    for attempt, days in schedule:
        client.post(
            "/api/v1/retry/configuration",
            headers=admin_auth_headers,
            json={"retry_attempt": attempt, "retry_after_days": days},
        )


def _fail_payment(client, auth_headers, invoice_id):
    with patch("app.services.payment_gateway_service.random.random", return_value=0.999):
        return client.post(
            "/api/v1/payments/process", headers=auth_headers, json={"invoice_id": invoice_id}
        )


def test_failed_payment_enqueues_initial_retry(
    client, auth_headers, admin_auth_headers, active_subscription_with_invoice, db_session
):
    _configure_retries(client, admin_auth_headers)
    fixture = active_subscription_with_invoice

    resp = _fail_payment(client, auth_headers, fixture["invoice_id"])
    assert resp.status_code == 201
    assert resp.json()["status"] == "failed"

    entries = (
        db_session.query(RetryQueue)
        .filter(RetryQueue.invoice_id == uuid.UUID(fixture["invoice_id"]))
        .all()
    )
    assert len(entries) == 1
    assert entries[0].retry_attempt == 1
    assert entries[0].retry_status == RetryStatus.PENDING
    assert entries[0].scheduled_retry_date > datetime.now(timezone.utc)

    audit = client.get(
        f"/api/v1/audit-logs/invoice/{fixture['invoice_id']}", headers=auth_headers
    ).json()
    assert any(e["event_type"] == "retry_scheduled" for e in audit)


def test_no_retry_enqueued_without_any_configuration(
    client, auth_headers, active_subscription_with_invoice, db_session
):
    """No retry configuration exists at all -- must not break the
    failed-payment flow, and must not create a queue entry."""
    fixture = active_subscription_with_invoice

    resp = _fail_payment(client, auth_headers, fixture["invoice_id"])
    assert resp.status_code == 201  # existing failure flow unaffected

    entries = (
        db_session.query(RetryQueue)
        .filter(RetryQueue.invoice_id == uuid.UUID(fixture["invoice_id"]))
        .all()
    )
    assert entries == []


def _make_entry_due_now(db_session, invoice_id):
    entry = (
        db_session.query(RetryQueue)
        .filter(RetryQueue.invoice_id == uuid.UUID(invoice_id))
        .order_by(RetryQueue.retry_attempt.desc())
        .first()
    )
    entry.scheduled_retry_date = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    return entry


def test_scheduler_ignores_not_yet_due_entries(
    client, auth_headers, admin_auth_headers, active_subscription_with_invoice, db_session
):
    _configure_retries(client, admin_auth_headers)
    fixture = active_subscription_with_invoice
    _fail_payment(client, auth_headers, fixture["invoice_id"])
    # Entry is scheduled 1 day out by default -- not due yet.

    summary = RetrySchedulerService(db_session).run()
    assert summary["processed"] == 0


def test_scheduler_success_reactivates_subscription_and_cancels_remaining(
    client, auth_headers, admin_auth_headers, active_subscription_with_invoice, db_session
):
    _configure_retries(client, admin_auth_headers)
    fixture = active_subscription_with_invoice
    _fail_payment(client, auth_headers, fixture["invoice_id"])
    _make_entry_due_now(db_session, fixture["invoice_id"])

    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        summary = RetrySchedulerService(db_session).run()

    assert summary["processed"] == 1
    assert summary["succeeded"] == 1

    entry = (
        db_session.query(RetryQueue)
        .filter(RetryQueue.invoice_id == uuid.UUID(fixture["invoice_id"]))
        .first()
    )
    db_session.refresh(entry)
    assert entry.retry_status == RetryStatus.SUCCEEDED
    assert entry.actual_retry_date is not None

    sub_resp = client.get(
        f"/api/v1/subscriptions/{fixture['subscription']['id']}", headers=auth_headers
    ).json()
    assert sub_resp["status"] == "active"  # reactivated via the existing _handle_paid logic

    inv_resp = client.get(f"/api/v1/invoices/{fixture['invoice_id']}", headers=auth_headers).json()
    assert inv_resp["status"] == "paid"


def test_scheduler_reschedules_next_attempt_on_failure(
    client, auth_headers, admin_auth_headers, active_subscription_with_invoice, db_session
):
    _configure_retries(client, admin_auth_headers)
    fixture = active_subscription_with_invoice
    _fail_payment(client, auth_headers, fixture["invoice_id"])
    _make_entry_due_now(db_session, fixture["invoice_id"])

    with patch("app.services.payment_gateway_service.random.random", return_value=0.999):
        summary = RetrySchedulerService(db_session).run()

    assert summary["processed"] == 1
    assert summary["rescheduled"] == 1

    entries = (
        db_session.query(RetryQueue)
        .filter(RetryQueue.invoice_id == uuid.UUID(fixture["invoice_id"]))
        .order_by(RetryQueue.retry_attempt.asc())
        .all()
    )
    assert len(entries) == 2
    assert entries[0].retry_status == RetryStatus.FAILED
    assert entries[0].retry_attempt == 1
    assert entries[1].retry_status == RetryStatus.PENDING
    assert entries[1].retry_attempt == 2

    sub_resp = client.get(
        f"/api/v1/subscriptions/{fixture['subscription']['id']}", headers=auth_headers
    ).json()
    assert sub_resp["status"] == "past_due"  # unchanged, still awaiting retry


def test_scheduler_exhausts_retries_cancels_subscription_invoice_stays_failed(
    client, auth_headers, admin_auth_headers, active_subscription_with_invoice, db_session
):
    # Only ONE configured attempt -- the first failed retry exhausts the schedule.
    _configure_retries(client, admin_auth_headers, schedule=[(1, 1)])
    fixture = active_subscription_with_invoice
    _fail_payment(client, auth_headers, fixture["invoice_id"])
    _make_entry_due_now(db_session, fixture["invoice_id"])

    with patch("app.services.payment_gateway_service.random.random", return_value=0.999):
        summary = RetrySchedulerService(db_session).run()

    assert summary["exhausted"] == 1

    sub_resp = client.get(
        f"/api/v1/subscriptions/{fixture['subscription']['id']}", headers=auth_headers
    ).json()
    assert sub_resp["status"] == "cancelled"

    inv_resp = client.get(f"/api/v1/invoices/{fixture['invoice_id']}", headers=auth_headers).json()
    assert inv_resp["status"] == "failed"  # stays FAILED -- matches Module 3's 3-status spec

    audit = client.get(
        f"/api/v1/audit-logs/invoice/{fixture['invoice_id']}", headers=auth_headers
    ).json()
    event_types = [e["event_type"] for e in audit]
    assert "retry_attempted" in event_types
    assert "retry_failed" in event_types
    assert "retry_cancelled" in event_types


def test_full_retry_audit_trail_present(
    client, auth_headers, admin_auth_headers, active_subscription_with_invoice, db_session
):
    _configure_retries(client, admin_auth_headers, schedule=[(1, 1), (2, 3)])
    fixture = active_subscription_with_invoice
    _fail_payment(client, auth_headers, fixture["invoice_id"])
    _make_entry_due_now(db_session, fixture["invoice_id"])

    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        RetrySchedulerService(db_session).run()

    audit = client.get(
        f"/api/v1/audit-logs/invoice/{fixture['invoice_id']}", headers=auth_headers
    ).json()
    event_types = [e["event_type"] for e in audit]
    assert "retry_scheduled" in event_types
    assert "retry_attempted" in event_types
    assert "retry_succeeded" in event_types
