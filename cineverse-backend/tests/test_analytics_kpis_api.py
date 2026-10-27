"""
Tests for GET /analytics/kpis (Module 3, Phase 3a): trial conversion
rate, churn rate, ARPU, CLV, payment/retry success & failure rates,
monthly subscription growth -- including every required edge case
(zero active subscriptions, zero churn, no payments, only pending
payments, only cancelled retries, empty datasets).
"""
import uuid
from datetime import date, timedelta

from app.models.enums import RetryStatus
from app.models.retry_queue import RetryQueue


def test_kpis_requires_admin(client, auth_headers):
    resp = client.get("/api/v1/analytics/kpis", headers=auth_headers)
    assert resp.status_code == 403


def test_kpis_requires_auth(client):
    resp = client.get("/api/v1/analytics/kpis")
    assert resp.status_code == 401


def test_kpis_empty_dataset_returns_nulls_not_errors(client, admin_auth_headers):
    """
    Brand new platform, nothing seeded yet: every rate must be `None`
    (not a crash, not a fabricated 0%), with explanatory notes.
    """
    resp = client.get("/api/v1/analytics/kpis", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["trial_conversion_rate"] is None
    assert body["arpu"] is None
    assert body["clv"] is None
    assert body["monthly_subscription_growth"] == []
    assert len(body["notes"]) > 0


def _register_and_login(client, email):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "KPI Test", "password": "SuperSecret123", "country": "US"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_subscription(client, admin_auth_headers, trial_days=0):
    email = f"kpi_{uuid.uuid4().hex[:8]}@test.com"
    headers = _register_and_login(client, email)
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": f"KPI Plan {uuid.uuid4().hex[:6]}",
            "price": 20,
            "billing_interval": "monthly",
            "trial_period_days": trial_days,
        },
    ).json()
    customer = client.get("/api/v1/customers/me", headers=headers).json()
    sub = client.post(
        "/api/v1/subscriptions",
        headers=headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    return headers, sub


def test_kpis_trial_conversion_rate_with_data(client, admin_auth_headers):
    headers_a, sub_a = _make_subscription(client, admin_auth_headers, trial_days=7)
    client.post(f"/api/v1/subscriptions/{sub_a['id']}/activate", headers=headers_a)

    headers_b, sub_b = _make_subscription(client, admin_auth_headers, trial_days=7)
    client.post(
        f"/api/v1/subscriptions/{sub_b['id']}/cancel",
        headers=headers_b,
        json={"cancellation_type": "immediate"},
    )

    resp = client.get("/api/v1/analytics/kpis", headers=admin_auth_headers)
    body = resp.json()
    assert body["trial_conversion_rate"] is not None
    assert 0 <= float(body["trial_conversion_rate"]) <= 100


def test_kpis_zero_active_subscriptions_arpu_and_clv_null(client, admin_auth_headers):
    """No active subscriptions at all -- ARPU and CLV must both be null."""
    resp = client.get("/api/v1/analytics/kpis", headers=admin_auth_headers)
    body = resp.json()
    assert body["arpu"] is None
    assert body["clv"] is None
    assert any("ARPU" in n for n in body["notes"])


def test_kpis_zero_churn_clv_null_with_explanation(client, admin_auth_headers):
    """
    An active subscription exists (so ARPU is defined) but nothing
    was cancelled in the period -- churn is 0%, so CLV must be null
    with a clear explanation, not an artificial/infinite number.
    """
    headers, sub = _make_subscription(client, admin_auth_headers, trial_days=0)
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=headers)

    # The period must start *after* the activation above (which
    # happens "now", not at midnight today) for "active at period
    # start" to correctly find it -- otherwise the denominator is
    # legitimately 0 (not yet active at midnight) and churn is
    # undefined, not 0%. Using tomorrow's date as the period brackets
    # the activation correctly: already active by then, and nothing
    # will be cancelled in this future window.
    period = date.today() + timedelta(days=1)
    resp = client.get(
        "/api/v1/analytics/kpis",
        headers=admin_auth_headers,
        params={"date_from": str(period), "date_to": str(period + timedelta(days=1))},
    )
    body = resp.json()
    assert body["arpu"] is not None
    assert body["monthly_churn_rate"] == 0.0 or body["monthly_churn_rate"] == "0.00"
    assert body["clv"] is None
    assert any("churn rate is 0%" in n for n in body["notes"])


def test_kpis_no_payments_rate_null(client, admin_auth_headers):
    resp = client.get("/api/v1/analytics/kpis", headers=admin_auth_headers)
    body = resp.json()
    assert body["payment_success_rate"] is None
    assert body["payment_failure_rate"] is None


def test_kpis_only_pending_payments_excluded_from_rate(
    client, auth_headers, admin_auth_headers, active_subscription_with_invoice, db_session
):
    """
    PENDING payments must be excluded from the success/failure rate
    denominator entirely -- a payment stuck pending should not count
    as neither succeeded nor failed while still showing up as "0
    concluded payments", not skew the rate toward failure.
    """
    from app.models.enums import PaymentStatus
    from app.models.payment import Payment

    fixture = active_subscription_with_invoice
    payment = Payment(
        invoice_id=fixture["invoice_id"],
        amount=fixture["invoice_total"],
        currency="USD",
        status=PaymentStatus.PENDING,
        payment_method="mock_gateway",
        attempt_number=1,
    )
    db_session.add(payment)
    db_session.commit()

    resp = client.get("/api/v1/analytics/kpis", headers=admin_auth_headers)
    body = resp.json()
    assert body["payment_success_rate"] is None
    assert body["payment_failure_rate"] is None


def test_kpis_only_cancelled_retries_excluded_from_rate(
    client, auth_headers, admin_auth_headers, active_subscription_with_invoice, db_session
):
    """
    CANCELLED retry queue entries (e.g. a later attempt cancelled
    because an earlier one already succeeded) must be excluded from
    the retry success/failure rate denominator.
    """
    from datetime import datetime, timezone

    fixture = active_subscription_with_invoice
    entry = RetryQueue(
        invoice_id=fixture["invoice_id"],
        customer_id=fixture["customer"]["id"],
        retry_attempt=2,
        scheduled_retry_date=datetime.now(timezone.utc),
        retry_status=RetryStatus.CANCELLED,
    )
    db_session.add(entry)
    db_session.commit()

    resp = client.get("/api/v1/analytics/kpis", headers=admin_auth_headers)
    body = resp.json()
    assert body["retry_success_rate"] is None
    assert body["retry_failure_rate"] is None


def test_kpis_monthly_growth_reflects_new_and_cancelled(client, admin_auth_headers):
    headers, sub = _make_subscription(client, admin_auth_headers, trial_days=0)
    client.post(
        f"/api/v1/subscriptions/{sub['id']}/cancel",
        headers=headers,
        json={"cancellation_type": "immediate"},
    )

    resp = client.get("/api/v1/analytics/kpis", headers=admin_auth_headers)
    body = resp.json()
    assert len(body["monthly_subscription_growth"]) >= 1
    this_month = body["monthly_subscription_growth"][-1]
    assert this_month["new_subscriptions"] >= 1
    assert this_month["cancelled_subscriptions"] >= 1
    assert this_month["net_growth"] == (
        this_month["new_subscriptions"] - this_month["cancelled_subscriptions"]
    )


def test_kpis_default_churn_period_note_present_when_no_dates_given(client, admin_auth_headers):
    resp = client.get("/api/v1/analytics/kpis", headers=admin_auth_headers)
    body = resp.json()
    assert any("defaulted to the last full calendar month" in n for n in body["notes"])


def test_kpis_custom_date_range_accepted(client, admin_auth_headers):
    resp = client.get(
        "/api/v1/analytics/kpis",
        headers=admin_auth_headers,
        params={"date_from": "2020-01-01", "date_to": "2020-01-31"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["date_from"] == "2020-01-01"
    assert body["date_to"] == "2020-01-31"
    # No note about defaulting, since explicit dates were given.
    assert not any("defaulted" in n for n in body["notes"])
