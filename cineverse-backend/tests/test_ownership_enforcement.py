"""
Phase 1D: ownership enforcement for Subscriptions, Invoices, Payments,
and Refunds. Extends Phase 1C's Customer-only enforcement so a
non-admin can only access resources belonging to their own linked
Customer, while admins retain full access to everything.
"""
import uuid
from unittest.mock import patch

import pytest


def _register_and_login(client, email):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Test User", "password": "SuperSecret123", "country": "US"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def two_customers_with_paid_invoices(client, admin_auth_headers):
    """
    Sets up two fully independent customers (A and B), each with their
    own activated subscription and a paid invoice, plus a refund on
    B's invoice -- enough data to exercise every ownership check across
    all four resource types in one shared fixture.
    """
    plan_id = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": f"Ownership Plan {uuid.uuid4().hex[:6]}",
            "price": 40.00,
            "billing_interval": "monthly",
            "trial_period_days": 0,
        },
    ).json()["id"]
    upgrade_plan_id = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": f"Ownership Upgrade Plan {uuid.uuid4().hex[:6]}",
            "price": 80.00,
            "billing_interval": "monthly",
        },
    ).json()["id"]

    def _setup_customer(label):
        email = f"owner_{label}_{uuid.uuid4().hex[:8]}@test.com"
        headers = _register_and_login(client, email)
        customer = client.get(
            "/api/v1/customers/me",
            headers=headers,
        ).json()
        sub = client.post(
            "/api/v1/subscriptions",
            headers=headers,
            json={"customer_id": customer["id"], "plan_id": plan_id},
        ).json()
        client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=headers)
        # Generate an invoice via an upgrade, then pay it.
        client.post(
            f"/api/v1/subscriptions/{sub['id']}/change-plan",
            headers=headers,
            json={"new_plan_id": upgrade_plan_id},
        )
        invoice_id = client.get(
            "/api/v1/invoices", params={"customer_id": customer["id"]}, headers=headers
        ).json()["items"][0]["id"]
        with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
            payment = client.post(
                "/api/v1/payments/process",
                headers=headers,
                json={"invoice_id": invoice_id},
            ).json()
        return {
            "headers": headers,
            "customer": customer,
            "subscription": sub,
            "invoice_id": invoice_id,
            "payment_id": payment["transaction_id"],
        }

    customer_a = _setup_customer("a")
    customer_b = _setup_customer("b")

    refund_b = client.post(
        "/api/v1/refunds",
        headers=customer_b["headers"],
        json={"invoice_id": customer_b["invoice_id"], "reason": "Ownership test refund"},
    ).json()
    customer_b["refund_id"] = refund_b["id"]

    # Resolve the actual Payment record ID (not the gateway transaction
    # id) for the payment-detail ownership tests.
    payment_record = client.get(
        "/api/v1/payments",
        params={"invoice_id": customer_a["invoice_id"]},
        headers=customer_a["headers"],
    ).json()["items"][0]
    customer_a["payment_record_id"] = payment_record["id"]

    return customer_a, customer_b


# ---------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------


def test_cannot_view_another_customers_subscription(client, two_customers_with_paid_invoices):
    a, b = two_customers_with_paid_invoices
    resp = client.get(f"/api/v1/subscriptions/{a['subscription']['id']}", headers=b["headers"])
    assert resp.status_code == 403


def test_cannot_pause_another_customers_subscription(client, two_customers_with_paid_invoices):
    a, b = two_customers_with_paid_invoices
    resp = client.post(f"/api/v1/subscriptions/{a['subscription']['id']}/pause", headers=b["headers"])
    assert resp.status_code == 403


def test_cannot_cancel_another_customers_subscription(client, two_customers_with_paid_invoices):
    a, b = two_customers_with_paid_invoices
    resp = client.post(
        f"/api/v1/subscriptions/{a['subscription']['id']}/cancel",
        headers=b["headers"],
        json={"cancellation_type": "immediate"},
    )
    assert resp.status_code == 403


def test_cannot_change_plan_of_another_customers_subscription(
    client, two_customers_with_paid_invoices, admin_auth_headers
):
    a, b = two_customers_with_paid_invoices
    other_plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"Hijack Plan {uuid.uuid4().hex[:6]}", "price": 10, "billing_interval": "monthly"},
    ).json()
    resp = client.post(
        f"/api/v1/subscriptions/{a['subscription']['id']}/change-plan",
        headers=b["headers"],
        json={"new_plan_id": other_plan["id"]},
    )
    assert resp.status_code == 403


def test_cannot_view_billing_cycles_of_another_customers_subscription(
    client, two_customers_with_paid_invoices
):
    a, b = two_customers_with_paid_invoices
    resp = client.get(
        f"/api/v1/subscriptions/{a['subscription']['id']}/billing-cycles", headers=b["headers"]
    )
    assert resp.status_code == 403


def test_cannot_create_subscription_for_another_customer(
    client, two_customers_with_paid_invoices, admin_auth_headers
):
    a, b = two_customers_with_paid_invoices
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"Hijack Sub Plan {uuid.uuid4().hex[:6]}", "price": 10, "billing_interval": "monthly"},
    ).json()
    resp = client.post(
        "/api/v1/subscriptions",
        headers=b["headers"],
        json={"customer_id": a["customer"]["id"], "plan_id": plan["id"]},
    )
    assert resp.status_code == 403


def test_subscription_list_scoped_to_own_customer(client, two_customers_with_paid_invoices):
    a, b = two_customers_with_paid_invoices
    # Even explicitly requesting A's customer_id, B only ever sees B's own.
    resp = client.get(
        "/api/v1/subscriptions", params={"customer_id": a["customer"]["id"]}, headers=b["headers"]
    )
    assert resp.status_code == 200
    body = resp.json()
    returned_ids = {item["id"] for item in body["items"]}
    assert a["subscription"]["id"] not in returned_ids


def test_own_subscription_access_still_works(client, two_customers_with_paid_invoices):
    a, _ = two_customers_with_paid_invoices
    resp = client.get(f"/api/v1/subscriptions/{a['subscription']['id']}", headers=a["headers"])
    assert resp.status_code == 200


def test_admin_can_access_any_subscription(client, two_customers_with_paid_invoices, admin_auth_headers):
    a, _ = two_customers_with_paid_invoices
    resp = client.get(f"/api/v1/subscriptions/{a['subscription']['id']}", headers=admin_auth_headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------


def test_cannot_view_another_customers_invoice(client, two_customers_with_paid_invoices):
    a, b = two_customers_with_paid_invoices
    resp = client.get(f"/api/v1/invoices/{a['invoice_id']}", headers=b["headers"])
    assert resp.status_code == 403


def test_cannot_view_another_customers_invoice_payments(client, two_customers_with_paid_invoices):
    a, b = two_customers_with_paid_invoices
    resp = client.get(f"/api/v1/invoices/{a['invoice_id']}/payments", headers=b["headers"])
    assert resp.status_code == 403


def test_cannot_view_another_customers_invoice_refunds(client, two_customers_with_paid_invoices):
    a, b = two_customers_with_paid_invoices
    resp = client.get(f"/api/v1/invoices/{a['invoice_id']}/refunds", headers=b["headers"])
    assert resp.status_code == 403


def test_invoice_list_scoped_to_own_customer(client, two_customers_with_paid_invoices):
    a, b = two_customers_with_paid_invoices
    resp = client.get(
        "/api/v1/invoices", params={"customer_id": a["customer"]["id"]}, headers=b["headers"]
    )
    assert resp.status_code == 200
    returned_ids = {item["id"] for item in resp.json()["items"]}
    assert a["invoice_id"] not in returned_ids


def test_own_invoice_access_still_works(client, two_customers_with_paid_invoices):
    a, _ = two_customers_with_paid_invoices
    resp = client.get(f"/api/v1/invoices/{a['invoice_id']}", headers=a["headers"])
    assert resp.status_code == 200


def test_admin_can_access_any_invoice(client, two_customers_with_paid_invoices, admin_auth_headers):
    a, _ = two_customers_with_paid_invoices
    resp = client.get(f"/api/v1/invoices/{a['invoice_id']}", headers=admin_auth_headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------


def test_cannot_pay_another_customers_invoice(client, two_customers_with_paid_invoices, admin_auth_headers):
    a, b = two_customers_with_paid_invoices
    # A's invoice is already paid; use a fresh unpaid one on A's account
    # so the 403 (ownership) is what's being tested, not a 409 (already
    # paid). Must be priced *higher* than A's current plan ($80, from
    # the fixture's upgrade) -- a downgrade generates no invoice at all.
    upgrade_plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"Fresh Invoice Plan {uuid.uuid4().hex[:6]}", "price": 150, "billing_interval": "monthly"},
    ).json()
    client.post(
        f"/api/v1/subscriptions/{a['subscription']['id']}/change-plan",
        headers=a["headers"],
        json={"new_plan_id": upgrade_plan["id"]},
    )
    invoices = client.get(
        "/api/v1/invoices",
        params={"customer_id": a["customer"]["id"], "status": "open"},
        headers=a["headers"],
    ).json()["items"]
    assert len(invoices) >= 1
    fresh_invoice_id = invoices[0]["id"]

    resp = client.post(
        "/api/v1/payments/process", headers=b["headers"], json={"invoice_id": fresh_invoice_id}
    )
    assert resp.status_code == 403


def test_cannot_view_another_customers_payment_by_id(client, two_customers_with_paid_invoices):
    a, b = two_customers_with_paid_invoices
    resp = client.get(f"/api/v1/payments/{a['payment_record_id']}", headers=b["headers"])
    assert resp.status_code == 403


def test_payment_list_scoped_to_own_customer(client, two_customers_with_paid_invoices):
    a, b = two_customers_with_paid_invoices
    resp = client.get(
        "/api/v1/payments", params={"customer_id": a["customer"]["id"]}, headers=b["headers"]
    )
    assert resp.status_code == 200
    returned_ids = {item["id"] for item in resp.json()["items"]}
    assert a["payment_record_id"] not in returned_ids


def test_own_payment_access_still_works(client, two_customers_with_paid_invoices):
    a, _ = two_customers_with_paid_invoices
    resp = client.get(f"/api/v1/payments/{a['payment_record_id']}", headers=a["headers"])
    assert resp.status_code == 200


def test_admin_can_access_any_payment(client, two_customers_with_paid_invoices, admin_auth_headers):
    a, _ = two_customers_with_paid_invoices
    resp = client.get(f"/api/v1/payments/{a['payment_record_id']}", headers=admin_auth_headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------
# Refunds
# ---------------------------------------------------------------------


def test_cannot_refund_another_customers_invoice(client, two_customers_with_paid_invoices):
    a, b = two_customers_with_paid_invoices
    resp = client.post(
        "/api/v1/refunds",
        headers=b["headers"],
        json={"invoice_id": a["invoice_id"], "reason": "Attempted hijack refund"},
    )
    assert resp.status_code == 403


def test_cannot_view_another_customers_refund_by_id(client, two_customers_with_paid_invoices):
    a, b = two_customers_with_paid_invoices
    resp = client.get(f"/api/v1/refunds/{b['refund_id']}", headers=a["headers"])
    assert resp.status_code == 403


def test_refund_list_scoped_to_own_customer(client, two_customers_with_paid_invoices):
    a, b = two_customers_with_paid_invoices
    resp = client.get(
        "/api/v1/refunds", params={"customer_id": b["customer"]["id"]}, headers=a["headers"]
    )
    assert resp.status_code == 200
    returned_ids = {item["id"] for item in resp.json()["items"]}
    assert b["refund_id"] not in returned_ids


def test_own_refund_access_still_works(client, two_customers_with_paid_invoices):
    _, b = two_customers_with_paid_invoices
    resp = client.get(f"/api/v1/refunds/{b['refund_id']}", headers=b["headers"])
    assert resp.status_code == 200


def test_admin_can_access_any_refund(client, two_customers_with_paid_invoices, admin_auth_headers):
    _, b = two_customers_with_paid_invoices
    resp = client.get(f"/api/v1/refunds/{b['refund_id']}", headers=admin_auth_headers)
    assert resp.status_code == 200
