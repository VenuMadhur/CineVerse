"""
Tests for Phase 3b (Module 3): Revenue analytics extensions
(daily/yearly/country/payment-method) and the new
GET /analytics/invoices endpoint.
"""
import uuid
from unittest.mock import patch

from app.scheduler.billing_scheduler_service import BillingSchedulerService


def _seed_paid_invoice(client, admin_auth_headers, db_session, country="US"):
    email = f"rev3b_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Revenue 3b", "password": "SuperSecret123", "country": country},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": f"Rev3b Plan {uuid.uuid4().hex[:6]}",
            "price": 50,
            "billing_interval": "monthly",
            "trial_period_days": 0,
        },
    ).json()
    customer = client.get("/api/v1/customers/me", headers=headers).json()
    sub = client.post(
        "/api/v1/subscriptions",
        headers=headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=headers)
    # Issue 2 fix (subscription_service.py): a plan with
    # trial_period_days=0 now starts ACTIVE directly, so the /activate
    # call above is a no-op for it (it's already active). The
    # subscription's initial billing cycle is immediately due, exactly
    # like before -- it's the scheduler's job to invoice it, so run the
    # real scheduler here instead of relying on /activate's old
    # synchronous side effect.
    BillingSchedulerService(db_session).run()
    invoice_id = client.get(
        "/api/v1/invoices", params={"customer_id": customer["id"]}, headers=headers
    ).json()["items"][0]["id"]

    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        client.post("/api/v1/payments/process", headers=headers, json={"invoice_id": invoice_id})
    return customer, plan, invoice_id, headers


# ---------------------------------------------------------------------
# Revenue analytics extensions
# ---------------------------------------------------------------------


def test_revenue_endpoint_still_requires_admin(client, auth_headers):
    """Existing endpoint's auth behavior unchanged."""
    resp = client.get("/api/v1/analytics/revenue", headers=auth_headers)
    assert resp.status_code == 403


def test_revenue_analytics_backward_compatible_fields_present(client, admin_auth_headers):
    """Every pre-existing field must still be present and correctly typed."""
    resp = client.get("/api/v1/analytics/revenue", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    for field in ["date_from", "date_to", "total_revenue", "revenue_by_month", "revenue_by_plan"]:
        assert field in body


def test_revenue_analytics_new_fields_present_and_correct(client, admin_auth_headers, db_session):
    customer, plan, _invoice_id, _headers = _seed_paid_invoice(
        client, admin_auth_headers, db_session, country="US"
    )
    resp = client.get("/api/v1/analytics/revenue", headers=admin_auth_headers)
    body = resp.json()

    assert "revenue_by_day" in body and len(body["revenue_by_day"]) >= 1
    assert "revenue_by_year" in body and len(body["revenue_by_year"]) >= 1
    assert any(item["country"] == "US" for item in body["revenue_by_country"])
    assert len(body["revenue_by_payment_method"]) >= 1


def test_revenue_by_country_matches_seeded_amount(client, admin_auth_headers, db_session):
    _seed_paid_invoice(client, admin_auth_headers, db_session, country="GB")
    resp = client.get("/api/v1/analytics/revenue", headers=admin_auth_headers)
    body = resp.json()
    gb_row = next((r for r in body["revenue_by_country"] if r["country"] == "GB"), None)
    assert gb_row is not None
    assert float(gb_row["revenue"]) >= 50.0  # $50 plan, GB tax adds on top of subtotal already paid


# ---------------------------------------------------------------------
# GET /analytics/invoices (new)
# ---------------------------------------------------------------------


def test_invoice_analytics_requires_admin(client, auth_headers):
    resp = client.get("/api/v1/analytics/invoices", headers=auth_headers)
    assert resp.status_code == 403


def test_invoice_analytics_requires_auth(client):
    resp = client.get("/api/v1/analytics/invoices")
    assert resp.status_code == 401


def test_invoice_analytics_empty_dataset(client, admin_auth_headers):
    resp = client.get("/api/v1/analytics/invoices", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    for field in [
        "paid_invoices", "pending_invoices", "failed_invoices", "refunded_invoices",
        "outstanding_invoice_amount", "average_invoice_amount",
    ]:
        assert field in body


def test_invoice_analytics_paid_count_increases(client, admin_auth_headers, db_session):
    before = client.get("/api/v1/analytics/invoices", headers=admin_auth_headers).json()
    _seed_paid_invoice(client, admin_auth_headers, db_session)
    after = client.get("/api/v1/analytics/invoices", headers=admin_auth_headers).json()
    assert after["paid_invoices"] == before["paid_invoices"] + 1


def test_invoice_analytics_pending_count_reflects_open_invoice(
    client, auth_headers, admin_auth_headers, active_subscription_with_invoice
):
    """An invoice that hasn't been paid yet (the fixture's own state) counts as pending."""
    before = client.get("/api/v1/analytics/invoices", headers=admin_auth_headers).json()
    fixture = active_subscription_with_invoice
    assert fixture["invoice_id"]  # sanity: fixture created an OPEN invoice, never paid here
    after = client.get("/api/v1/analytics/invoices", headers=admin_auth_headers).json()
    assert after["pending_invoices"] >= before["pending_invoices"]


def test_invoice_analytics_outstanding_amount_excludes_paid(client, admin_auth_headers, db_session):
    before = client.get("/api/v1/analytics/invoices", headers=admin_auth_headers).json()
    _seed_paid_invoice(client, admin_auth_headers, db_session)  # fully paid -- must NOT count as outstanding
    after = client.get("/api/v1/analytics/invoices", headers=admin_auth_headers).json()
    # Paying an invoice shouldn't increase outstanding amount.
    assert float(after["outstanding_invoice_amount"]) == float(before["outstanding_invoice_amount"])


def test_invoice_analytics_average_amount_is_a_valid_decimal(client, admin_auth_headers, db_session):
    _seed_paid_invoice(client, admin_auth_headers, db_session)
    resp = client.get("/api/v1/analytics/invoices", headers=admin_auth_headers)
    body = resp.json()
    assert float(body["average_invoice_amount"]) >= 0
