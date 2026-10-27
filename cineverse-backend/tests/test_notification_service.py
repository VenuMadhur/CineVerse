"""
Tests for the Phase 6B email notification system: the shared
`notification_dispatch.notify()` helper, `NotificationService`'s
message building (12 event types, HTML + plain-text) and delivery,
and its integration into every real trigger point across
CustomerService, SubscriptionService, InvoiceService,
PaymentWebhookHandlerService, and RefundService.

Replaces the pre-Phase-6B version of this file, which tested the old
3-event, no-HTML-template architecture and was left failing (wrong
function name, wrong signatures) after the refactor to the shared
`notify()` helper -- this rewrite is the fix for that regression.
"""
import uuid
from unittest.mock import patch

import pytest

from app.services.notification_service import NotificationService
from app.services import email_templates


class FakeCustomer:
    def __init__(self, email="jane@test.com", name="Jane Doe"):
        self.email = email
        self.name = name


ALL_EVENT_TYPES = [
    "welcome",
    "profile_updated",
    "subscription_started",
    "subscription_activated",
    "subscription_paused",
    "subscription_resumed",
    "subscription_cancelled",
    "plan_changed",
    "invoice_generated",
    "payment_succeeded",
    "payment_failed",
    "refund_completed",
]


# ---------------------------------------------------------------------
# Email template shell
# ---------------------------------------------------------------------


def test_render_email_contains_branding_and_support_contact():
    html = email_templates.render_email(
        preheader="Test preheader", heading="Test Heading", body_html="<p>Body</p>"
    )
    assert "CineVerse" in html
    assert "support@cineverse.example.com" in html
    assert "Test Heading" in html
    assert "<p>Body</p>" in html
    assert "viewport" in html  # responsive meta tag present


def test_detail_table_renders_rows():
    table = email_templates.detail_table([("Invoice Number", "INV-1"), ("Amount", "$10")])
    assert "Invoice Number" in table
    assert "INV-1" in table
    assert "$10" in table


def test_detail_table_empty_when_no_rows():
    assert email_templates.detail_table([]) == ""


# ---------------------------------------------------------------------
# NotificationService: message building, every event type
# ---------------------------------------------------------------------


@pytest.mark.parametrize("event_type", ALL_EVENT_TYPES)
def test_build_message_every_event_type_produces_valid_output(db_session, event_type):
    service = NotificationService(db_session)
    subject, html, text = service._build_message(
        event_type,
        FakeCustomer(),
        {
            "plan_name": "Pro Plan",
            "old_plan_name": "Basic",
            "new_plan_name": "Pro",
            "direction": "upgraded",
            "invoice_number": "INV-202601-ABCDEF12",
            "amount": "42.00",
            "currency": "USD",
            "transaction_id": "MOCKTXN-123",
            "reason": "Card declined",
            "due_date": "2026-02-01",
            "trial_ends_at": "2026-02-15",
        },
    )
    assert subject
    assert "Jane Doe" in html
    assert "Jane Doe" in text
    assert "<html" in html.lower()


def test_build_message_unknown_event_type_falls_back_gracefully(db_session):
    service = NotificationService(db_session)
    subject, html, text = service._build_message("some_unknown_event", FakeCustomer(), {})
    assert subject
    assert "Jane Doe" in html


def test_build_message_payment_failed_includes_reason(db_session):
    service = NotificationService(db_session)
    _subject, html, text = service._build_message(
        "payment_failed", FakeCustomer(), {"invoice_number": "INV-1", "reason": "Card declined"}
    )
    assert "Card declined" in html
    assert "Card declined" in text


def test_build_message_plan_changed_reflects_direction(db_session):
    service = NotificationService(db_session)
    _subject, html, _text = service._build_message(
        "plan_changed",
        FakeCustomer(),
        {"direction": "downgraded", "old_plan_name": "Pro", "new_plan_name": "Basic"},
    )
    assert "downgraded" in html
    assert "Pro" in html
    assert "Basic" in html


# ---------------------------------------------------------------------
# NotificationService: dispatch() behavior
# ---------------------------------------------------------------------


def test_dispatch_skips_when_notifications_disabled(db_session):
    from app.config.settings import settings

    service = NotificationService(db_session)
    with patch.object(settings, "NOTIFICATIONS_ENABLED", False):
        with patch.object(service, "_send") as mock_send:
            service.dispatch("welcome", customer_id=uuid.uuid4())
            mock_send.assert_not_called()


def test_dispatch_skips_gracefully_when_customer_missing(db_session):
    service = NotificationService(db_session)
    with patch.object(service, "_send") as mock_send:
        service.dispatch("welcome", customer_id=uuid.uuid4())
        mock_send.assert_not_called()


def test_send_logs_when_smtp_not_configured(db_session, caplog):
    service = NotificationService(db_session)
    with caplog.at_level("INFO"):
        service._send("jane@test.com", "Test subject", "<p>html</p>", "text")
    assert any("simulated" in record.message.lower() for record in caplog.records)


# ---------------------------------------------------------------------
# notification_dispatch.notify() -- the shared helper every service uses
# ---------------------------------------------------------------------


def test_notify_dispatches_via_celery_task():
    from app.services.notification_dispatch import notify

    with patch("app.tasks.notification_tasks.send_notification_email.delay") as mock_delay:
        notify("welcome", uuid.uuid4(), {"foo": "bar"})
    mock_delay.assert_called_once()


def test_notify_swallows_dispatch_failures():
    """Must never raise, even if the broker is unreachable."""
    from app.services.notification_dispatch import notify

    with patch(
        "app.tasks.notification_tasks.send_notification_email.delay",
        side_effect=Exception("broker unreachable"),
    ):
        notify("welcome", uuid.uuid4(), {})  # must not raise


# ---------------------------------------------------------------------
# Real integration: every actual trigger point across the 5 services
# ---------------------------------------------------------------------


def _register_and_login(client, email):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Notif Test", "password": "SuperSecret123", "country": "US"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@patch("app.tasks.notification_tasks.send_notification_email.delay")
def test_create_customer_dispatches_welcome(mock_delay, client):
    email = f"welcome_{uuid.uuid4().hex[:8]}@test.com"
    headers = _register_and_login(client, email)
    resp = client.get("/api/v1/customers/me", headers=headers)
    assert resp.status_code == 200
    mock_delay.assert_called_once()
    args = mock_delay.call_args[0]
    assert args[0] == "welcome"


@patch("app.tasks.notification_tasks.send_notification_email.delay")
def test_update_customer_dispatches_profile_updated_only_when_changed(mock_delay, client):
    email = f"profile_{uuid.uuid4().hex[:8]}@test.com"
    headers = _register_and_login(client, email)
    customer = client.get("/api/v1/customers/me", headers=headers).json()
    mock_delay.reset_mock()  # clear the "welcome" call from creation above

    # No actual change (same name) -- should NOT fire profile_updated.
    client.patch(f"/api/v1/customers/{customer['id']}", headers=headers, json={"name": "Notif Test"})
    mock_delay.assert_not_called()

    # Genuine change -- should fire.
    client.patch(f"/api/v1/customers/{customer['id']}", headers=headers, json={"name": "New Name"})
    mock_delay.assert_called_once()
    assert mock_delay.call_args[0][0] == "profile_updated"


def test_subscription_lifecycle_dispatches_every_event(client, admin_auth_headers):
    email = f"lifecycle_{uuid.uuid4().hex[:8]}@test.com"
    headers = _register_and_login(client, email)
    plan_a = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"Notif Plan A {uuid.uuid4().hex[:6]}", "price": 10, "billing_interval": "monthly", "trial_period_days": 7},
    ).json()
    plan_b = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"Notif Plan B {uuid.uuid4().hex[:6]}", "price": 30, "billing_interval": "monthly"},
    ).json()
    customer = client.get("/api/v1/customers/me", headers=headers).json()

    with patch("app.tasks.notification_tasks.send_notification_email.delay") as mock_delay:
        sub = client.post(
            "/api/v1/subscriptions",
            headers=headers,
            json={"customer_id": customer["id"], "plan_id": plan_a["id"]},
        ).json()
    assert mock_delay.call_args[0][0] == "subscription_started"

    with patch("app.tasks.notification_tasks.send_notification_email.delay") as mock_delay:
        client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=headers)
    assert mock_delay.call_args[0][0] == "subscription_activated"

    with patch("app.tasks.notification_tasks.send_notification_email.delay") as mock_delay:
        client.post(
            f"/api/v1/subscriptions/{sub['id']}/change-plan",
            headers=headers,
            json={"new_plan_id": plan_b["id"]},
        )
    calls = [c[0][0] for c in mock_delay.call_args_list]
    assert "plan_changed" in calls
    assert "invoice_generated" in calls  # upgrade generates a proration invoice

    with patch("app.tasks.notification_tasks.send_notification_email.delay") as mock_delay:
        client.post(f"/api/v1/subscriptions/{sub['id']}/pause", headers=headers)
    assert mock_delay.call_args[0][0] == "subscription_paused"

    with patch("app.tasks.notification_tasks.send_notification_email.delay") as mock_delay:
        client.post(f"/api/v1/subscriptions/{sub['id']}/resume", headers=headers)
    assert mock_delay.call_args[0][0] == "subscription_resumed"

    with patch("app.tasks.notification_tasks.send_notification_email.delay") as mock_delay:
        client.post(
            f"/api/v1/subscriptions/{sub['id']}/cancel",
            headers=headers,
            json={"cancellation_type": "immediate"},
        )
    assert mock_delay.call_args[0][0] == "subscription_cancelled"


def test_payment_succeeded_dispatches_notification(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0), patch(
        "app.tasks.notification_tasks.send_notification_email.delay"
    ) as mock_delay:
        resp = client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )
    assert resp.status_code == 201
    mock_delay.assert_called_once()
    args = mock_delay.call_args[0]
    assert args[0] == "payment_succeeded"


def test_payment_failed_dispatches_notification(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    with patch(
        "app.services.payment_gateway_service.random.random", return_value=0.999
    ), patch("app.tasks.notification_tasks.send_notification_email.delay") as mock_delay:
        resp = client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )
    assert resp.status_code == 201
    mock_delay.assert_called_once()
    assert mock_delay.call_args[0][0] == "payment_failed"


def test_refund_dispatches_notification(client, auth_headers, active_subscription_with_invoice):
    fixture = active_subscription_with_invoice
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )

    with patch("app.tasks.notification_tasks.send_notification_email.delay") as mock_delay:
        resp = client.post(
            "/api/v1/refunds",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"], "reason": "Notification test"},
        )
    assert resp.status_code == 201
    mock_delay.assert_called_once()
    assert mock_delay.call_args[0][0] == "refund_completed"


def test_notification_dispatch_failure_does_not_break_payment_processing(
    client, auth_headers, active_subscription_with_invoice
):
    """Core guarantee: a broker outage must never break the billing action."""
    fixture = active_subscription_with_invoice
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0), patch(
        "app.tasks.notification_tasks.send_notification_email.delay",
        side_effect=Exception("broker unreachable"),
    ):
        resp = client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )
    assert resp.status_code == 201
    assert resp.json()["status"] == "succeeded"
