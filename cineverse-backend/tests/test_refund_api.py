"""
Integration tests for Refund processing (Module 2): manual full/
partial refunds, and automatic unused-period refunds on immediate
cancellation (both during trial and after payment).
"""
import uuid
from unittest.mock import patch

from app.scheduler.billing_scheduler_service import BillingSchedulerService


def _pay_invoice(client, auth_headers, invoice_id):
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        return client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": invoice_id},
        ).json()


def test_full_refund_of_paid_invoice(client, auth_headers, active_subscription_with_invoice):
    fixture = active_subscription_with_invoice
    _pay_invoice(client, auth_headers, fixture["invoice_id"])

    resp = client.post(
        "/api/v1/refunds",
        headers=auth_headers,
        json={"invoice_id": fixture["invoice_id"], "reason": "Customer requested full refund"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert float(body["amount"]) == fixture["invoice_total"]
    assert body["status"] == "completed"

    invoice = client.get(f"/api/v1/invoices/{fixture['invoice_id']}", headers=auth_headers).json()
    assert invoice["status"] == "refunded"
    assert float(invoice["total_amount"]) == 0.0


def test_partial_refund_of_paid_invoice(client, auth_headers, active_subscription_with_invoice):
    fixture = active_subscription_with_invoice
    _pay_invoice(client, auth_headers, fixture["invoice_id"])

    partial_amount = round(fixture["invoice_total"] / 2, 2)
    resp = client.post(
        "/api/v1/refunds",
        headers=auth_headers,
        json={
            "invoice_id": fixture["invoice_id"],
            "amount": partial_amount,
            "reason": "Partial goodwill refund",
        },
    )
    assert resp.status_code == 201
    assert float(resp.json()["amount"]) == partial_amount

    invoice = client.get(f"/api/v1/invoices/{fixture['invoice_id']}", headers=auth_headers).json()
    # Partial refund: invoice total is reduced but invoice remains 'paid'
    # since it isn't fully refunded.
    assert invoice["status"] == "paid"
    assert float(invoice["total_amount"]) == round(fixture["invoice_total"] - partial_amount, 2)


def test_partial_refund_proportionally_reduces_tax_and_subtotal(
    client, auth_headers, admin_auth_headers, db_session
):
    """
    Confirmed bug fix: previously only total_amount was reduced on
    refund; tax_amount and subtotal were left at their original
    values. This meant a partially-refunded invoice (which stays
    'paid', so it's still counted by GET /reports/tax) reported the
    full original tax as still collected, even though part of it was
    refunded. Uses an India (18% GST) customer for a clean, exact
    percentage to verify against.
    """
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": f"GST Refund Plan {uuid.uuid4().hex[:6]}",
            "price": 100.00,
            "billing_interval": "monthly",
            "trial_period_days": 0,
        },
    ).json()
    email = f"gst_refund_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "GST Refund Co",
            "email": email,
            "password": "SuperSecret123",
            "country": "IN",
        },
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}).json()["access_token"]
    test_headers = {"Authorization": f"Bearer {token}"}
    customer = client.get("/api/v1/customers/me", headers=test_headers).json()
    sub = client.post(
        "/api/v1/subscriptions",
        headers=test_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=test_headers)
    # Issue 2 fix: trial_period_days=0 now starts the subscription
    # ACTIVE directly, so /activate above is a no-op; the scheduler is
    # what invoices it.
    BillingSchedulerService(db_session).run()
    invoice_id = client.get(
        "/api/v1/invoices", params={"customer_id": customer["id"]}, headers=test_headers
    ).json()["items"][0]["id"]
    _pay_invoice(client, test_headers, invoice_id)

    before = client.get(f"/api/v1/invoices/{invoice_id}", headers=test_headers).json()
    assert float(before["subtotal"]) == 100.00
    assert float(before["tax_amount"]) == 18.00
    assert float(before["total_amount"]) == 118.00

    # Refund exactly half.
    client.post(
        "/api/v1/refunds",
        headers=test_headers,
        json={"invoice_id": invoice_id, "amount": 59.00, "reason": "partial GST refund test"},
    )

    after = client.get(f"/api/v1/invoices/{invoice_id}", headers=test_headers).json()
    assert after["status"] == "paid"
    assert float(after["subtotal"]) == 50.00
    assert float(after["tax_amount"]) == 9.00
    assert float(after["total_amount"]) == 59.00
    # The core invariant: subtotal + tax_amount must always equal total_amount.
    assert round(float(after["subtotal"]) + float(after["tax_amount"]), 2) == float(
        after["total_amount"]
    )


def test_full_refund_reduces_tax_and_subtotal_to_exactly_zero(
    client, auth_headers, admin_auth_headers, db_session
):
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": f"GST Full Refund Plan {uuid.uuid4().hex[:6]}",
            "price": 100.00,
            "billing_interval": "monthly",
            "trial_period_days": 0,
        },
    ).json()
    email = f"gst_full_refund_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "GST Full Refund Co",
            "email": email,
            "password": "SuperSecret123",
            "country": "IN",
        },
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}).json()["access_token"]
    test_headers = {"Authorization": f"Bearer {token}"}
    customer = client.get("/api/v1/customers/me", headers=test_headers).json()
    sub = client.post(
        "/api/v1/subscriptions",
        headers=test_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=test_headers)
    # Issue 2 fix: same reasoning as above.
    BillingSchedulerService(db_session).run()
    invoice_id = client.get(
        "/api/v1/invoices", params={"customer_id": customer["id"]}, headers=test_headers
    ).json()["items"][0]["id"]
    _pay_invoice(client, test_headers, invoice_id)

    client.post(
        "/api/v1/refunds",
        headers=test_headers,
        json={"invoice_id": invoice_id, "reason": "full GST refund test"},
    )

    after = client.get(f"/api/v1/invoices/{invoice_id}", headers=test_headers).json()
    assert after["status"] == "refunded"
    assert float(after["subtotal"]) == 0.00
    assert float(after["tax_amount"]) == 0.00
    assert float(after["total_amount"]) == 0.00


def test_cannot_refund_more_than_invoice_total(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    _pay_invoice(client, auth_headers, fixture["invoice_id"])

    resp = client.post(
        "/api/v1/refunds",
        headers=auth_headers,
        json={
            "invoice_id": fixture["invoice_id"],
            "amount": fixture["invoice_total"] + 100,
            "reason": "Too much",
        },
    )
    assert resp.status_code == 422


def test_cannot_refund_unpaid_invoice(client, auth_headers, active_subscription_with_invoice):
    fixture = active_subscription_with_invoice
    # Invoice exists but was never paid.
    resp = client.post(
        "/api/v1/refunds",
        headers=auth_headers,
        json={"invoice_id": fixture["invoice_id"], "reason": "Should fail"},
    )
    assert resp.status_code == 409


def test_view_refund_history_for_invoice(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    _pay_invoice(client, auth_headers, fixture["invoice_id"])
    client.post(
        "/api/v1/refunds",
        headers=auth_headers,
        json={"invoice_id": fixture["invoice_id"], "reason": "History check"},
    )

    history = client.get(
        f"/api/v1/invoices/{fixture['invoice_id']}/refunds", headers=auth_headers
    )
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_cancellation_during_trial_does_not_create_refund(client, auth_headers, admin_auth_headers):
    """No payment has occurred during trial, so immediate cancellation
    should not create any refund record."""
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Trial Cancel Plan", "price": 20, "billing_interval": "monthly", "trial_period_days": 14},
    ).json()
    customer = client.get("/api/v1/customers/me", headers=auth_headers).json()
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    assert sub["status"] == "trial"

    client.post(
        f"/api/v1/subscriptions/{sub['id']}/cancel",
        headers=auth_headers,
        json={"cancellation_type": "immediate", "reason": "Changed my mind during trial"},
    )

    refunds = client.get(
        "/api/v1/refunds", params={"customer_id": customer["id"]}, headers=auth_headers
    ).json()
    assert refunds["total"] == 0


def test_cancellation_after_payment_auto_refunds_unused_period(
    client, auth_headers, active_subscription_with_invoice
):
    """Cancelling an active, already-paid subscription immediately
    should automatically refund the unused portion of the current
    cycle."""
    fixture = active_subscription_with_invoice
    _pay_invoice(client, auth_headers, fixture["invoice_id"])

    invoice_before = client.get(
        f"/api/v1/invoices/{fixture['invoice_id']}", headers=auth_headers
    ).json()
    assert invoice_before["status"] == "paid"

    cancel_resp = client.post(
        f"/api/v1/subscriptions/{fixture['subscription']['id']}/cancel",
        headers=auth_headers,
        json={"cancellation_type": "immediate", "reason": "No longer needed"},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    refunds = client.get(
        "/api/v1/refunds",
        params={"customer_id": fixture["customer"]["id"]},
        headers=auth_headers,
    ).json()
    assert refunds["total"] == 1
    assert float(refunds["items"][0]["amount"]) > 0
