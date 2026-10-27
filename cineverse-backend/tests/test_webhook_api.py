"""
Integration tests for the payment webhook endpoint and handler
(Module 2): paid / failed / refunded events, plus idempotency.
"""
import json
from datetime import datetime, timezone
from unittest.mock import patch


def _process_payment(client, auth_headers, invoice_id, succeed: bool):
    outcome = 0.0 if succeed else 0.999
    with patch("app.services.payment_gateway_service.random.random", return_value=outcome):
        resp = client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": invoice_id},
        )
    return resp.json()


def test_webhook_paid_event_is_idempotent(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    payment = _process_payment(client, auth_headers, fixture["invoice_id"], succeed=True)

    # The in-process webhook sender already delivered this event once
    # (as part of process_payment). Replaying the same event manually
    # must be a no-op, not a duplicate state change or error.
    resp = client.post(
        "/api/v1/webhooks/payment",
        json={
            "invoice_id": fixture["invoice_id"],
            "customer_id": fixture["customer"]["id"],
            "transaction_id": payment["transaction_id"],
            "status": "paid",
            "amount": payment["amount"],
            "event_time": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["event_processed"] is False


def test_webhook_failed_event_marks_subscription_past_due(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    payment = _process_payment(client, auth_headers, fixture["invoice_id"], succeed=False)

    subscription = client.get(
        f"/api/v1/subscriptions/{fixture['subscription']['id']}", headers=auth_headers
    ).json()
    assert subscription["status"] == "past_due"

    # Replaying the failed event again should also be idempotent.
    resp = client.post(
        "/api/v1/webhooks/payment",
        json={
            "invoice_id": fixture["invoice_id"],
            "customer_id": fixture["customer"]["id"],
            "transaction_id": payment["transaction_id"],
            "status": "failed",
            "amount": payment["amount"],
            "event_time": datetime.now(timezone.utc).isoformat(),
            "message": "Simulated gateway decline",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["event_processed"] is False


def test_webhook_unknown_transaction_returns_404(client):
    resp = client.post(
        "/api/v1/webhooks/payment",
        json={
            "invoice_id": "00000000-0000-0000-0000-000000000000",
            "customer_id": "00000000-0000-0000-0000-000000000000",
            "transaction_id": "MOCKTXN-DOESNOTEXIST",
            "status": "paid",
            "amount": 10.00,
            "event_time": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert resp.status_code == 404


def test_webhook_invalid_signature_rejected(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    payment = _process_payment(client, auth_headers, fixture["invoice_id"], succeed=True)

    resp = client.post(
        "/api/v1/webhooks/payment",
        headers={"X-Webhook-Signature": "not-a-valid-signature"},
        json={
            "invoice_id": fixture["invoice_id"],
            "customer_id": fixture["customer"]["id"],
            "transaction_id": payment["transaction_id"],
            "status": "paid",
            "amount": payment["amount"],
            "event_time": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert resp.status_code == 401


def test_webhook_valid_signature_accepted(
    client, auth_headers, active_subscription_with_invoice
):
    from app.services.webhook_sender_service import sign_payload

    fixture = active_subscription_with_invoice
    payment = _process_payment(client, auth_headers, fixture["invoice_id"], succeed=True)

    body = {
        "invoice_id": fixture["invoice_id"],
        "customer_id": fixture["customer"]["id"],
        "transaction_id": payment["transaction_id"],
        "status": "paid",
        "amount": payment["amount"],
        "event_time": datetime.now(timezone.utc).isoformat(),
    }
    raw = json.dumps(body).encode("utf-8")
    signature = sign_payload(raw)

    resp = client.post(
        "/api/v1/webhooks/payment",
        headers={"X-Webhook-Signature": signature, "Content-Type": "application/json"},
        content=raw,
    )
    assert resp.status_code == 200
