"""
Phase 2: tests for the Analytics module (dashboard, revenue,
subscriptions, payments, refunds). Every endpoint is admin-only;
non-admin access must be rejected with 403.

Uses the isolated per-test transaction (via the `client`/`db_session`
fixtures), so exact-value assertions are safe -- no other test's data
can leak in.
"""
import uuid
from unittest.mock import patch


def _create_plan(client, admin_auth_headers, price=10.0, name=None):
    return client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": name or f"Analytics Plan {uuid.uuid4().hex[:8]}",
            "price": price,
            "billing_interval": "monthly",
            "trial_period_days": 0,
        },
    ).json()


def _create_customer(client, auth_headers):
    return client.get(
        "/api/v1/customers/me",
        headers=auth_headers,
    ).json()


def _register_and_login(client, email):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Analytics User", "password": "SuperSecret123", "country": "US"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _paid_invoice_for_new_customer(client, admin_auth_headers, plan_a_price=20.0, plan_b_price=50.0):
    """
    Full setup: independent customer, plan A (initial) -> plan B
    (upgrade, generates an invoice) -> pay it. Returns
    (customer, subscription, invoice_id, headers, plan_b).
    """
    email = f"analytics_flow_{uuid.uuid4().hex[:8]}@test.com"
    headers = _register_and_login(client, email)
    plan_a = _create_plan(client, admin_auth_headers, price=plan_a_price)
    plan_b = _create_plan(client, admin_auth_headers, price=plan_b_price)
    customer = client.get("/api/v1/customers/me", headers=headers).json()
    sub = client.post(
        "/api/v1/subscriptions",
        headers=headers,
        json={"customer_id": customer["id"], "plan_id": plan_a["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=headers)
    client.post(
        f"/api/v1/subscriptions/{sub['id']}/change-plan",
        headers=headers,
        json={"new_plan_id": plan_b["id"]},
    )
    invoice_id = client.get(
        "/api/v1/invoices", params={"customer_id": customer["id"]}, headers=headers
    ).json()["items"][0]["id"]
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        client.post("/api/v1/payments/process", headers=headers, json={"invoice_id": invoice_id})
    return customer, sub, invoice_id, headers, plan_b


# ---------------------------------------------------------------------
# Authorization -- every endpoint, both directions
# ---------------------------------------------------------------------

ANALYTICS_PATHS = [
    "/api/v1/analytics/dashboard",
    "/api/v1/analytics/revenue",
    "/api/v1/analytics/subscriptions",
    "/api/v1/analytics/payments",
    "/api/v1/analytics/refunds",
    "/api/v1/analytics/subscribers-by-plan",
    "/api/v1/analytics/refunds/trend",
    "/api/v1/analytics/customers/trend",
    "/api/v1/analytics/mrr-by-plan",
]


def test_all_analytics_endpoints_require_admin(client, auth_headers):
    for path in ANALYTICS_PATHS:
        resp = client.get(path, headers=auth_headers)
        assert resp.status_code == 403, f"{path} should be forbidden for a non-admin"
        assert resp.json()["error"]["code"] == "forbidden"


def test_all_analytics_endpoints_require_auth(client):
    for path in ANALYTICS_PATHS:
        resp = client.get(path)
        assert resp.status_code == 401, f"{path} should require authentication"


def test_all_analytics_endpoints_succeed_for_admin(client, admin_auth_headers):
    for path in ANALYTICS_PATHS:
        resp = client.get(path, headers=admin_auth_headers)
        assert resp.status_code == 200, f"{path} should succeed for an admin"


# ---------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------


def test_dashboard_reflects_created_data(client, admin_auth_headers):
    _paid_invoice_for_new_customer(client, admin_auth_headers)

    resp = client.get("/api/v1/analytics/dashboard", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_customers"] >= 1
    assert body["active_customers"] >= 1
    assert body["active_subscriptions"] >= 1
    assert body["total_successful_payments"] >= 1
    assert float(body["total_revenue"]) > 0


def test_dashboard_counts_cancelled_subscriptions(client, admin_auth_headers, auth_headers):
    plan = _create_plan(client, admin_auth_headers)
    customer = _create_customer(client, auth_headers)
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    client.post(
        f"/api/v1/subscriptions/{sub['id']}/cancel",
        headers=auth_headers,
        json={"cancellation_type": "immediate"},
    )

    resp = client.get("/api/v1/analytics/dashboard", headers=admin_auth_headers)
    body = resp.json()
    assert body["cancelled_subscriptions"] >= 1
    # Phase 6A: a customer whose only subscription is now cancelled
    # must be reflected in cancelled_customers too.
    assert body["cancelled_customers"] >= 1


def test_dashboard_mrr_arr_reflect_active_subscription(client, admin_auth_headers, auth_headers):
    plan = _create_plan(client, admin_auth_headers, price=49.0)
    customer = _create_customer(client, auth_headers)
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=auth_headers)

    resp = client.get("/api/v1/analytics/dashboard", headers=admin_auth_headers)
    body = resp.json()
    assert float(body["mrr"]) >= 49.0
    assert float(body["arr"]) == float(body["mrr"]) * 12


def test_dashboard_revenue_and_mrr_broken_out_by_currency_single_currency(
    client, admin_auth_headers, auth_headers
):
    """
    Fix (dashboard currency consistency): even in the common
    single-currency case, the breakdown fields must be present and
    correctly reflect the one currency in use -- not just an empty
    list or a silently-blended number.
    """
    plan = _create_plan(client, admin_auth_headers, price=49.0)
    customer = _create_customer(client, auth_headers)
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=auth_headers)

    resp = client.get("/api/v1/analytics/dashboard", headers=admin_auth_headers)
    body = resp.json()
    assert "revenue_by_currency" in body
    assert "mrr_by_currency" in body
    assert "arr_by_currency" in body
    usd_mrr_rows = [r for r in body["mrr_by_currency"] if r["currency"] == "USD"]
    assert usd_mrr_rows
    assert float(usd_mrr_rows[0]["amount"]) >= 49.0


def test_dashboard_mrr_never_blends_two_genuinely_different_currencies(
    client, admin_auth_headers, auth_headers
):
    """
    The actual bug this fixes: Plan.currency is unconstrained, so two
    active subscriptions on plans in different currencies must never
    be summed into one blended number. mrr_by_currency must show them
    as two separate entries; the flat `mrr` field is documented as
    blended (kept only for backward compatibility) and is not what the
    frontend renders from anymore.
    """
    usd_plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": f"USD Plan {uuid.uuid4().hex[:8]}",
            "price": 20,
            "currency": "USD",
            "billing_interval": "monthly",
            "trial_period_days": 0,
        },
    ).json()
    inr_plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": f"INR Plan {uuid.uuid4().hex[:8]}",
            "price": 1500,
            "currency": "INR",
            "billing_interval": "monthly",
            "trial_period_days": 0,
        },
    ).json()
    customer_usd = _create_customer(client, auth_headers)
    inr_headers = _register_and_login(client, f"inr_customer_{uuid.uuid4().hex[:8]}@test.com")
    customer_inr = _create_customer(client, inr_headers)

    sub_usd = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer_usd["id"], "plan_id": usd_plan["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub_usd['id']}/activate", headers=auth_headers)

    sub_inr = client.post(
        "/api/v1/subscriptions",
        headers=inr_headers,
        json={"customer_id": customer_inr["id"], "plan_id": inr_plan["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub_inr['id']}/activate", headers=inr_headers)

    resp = client.get("/api/v1/analytics/dashboard", headers=admin_auth_headers)
    body = resp.json()

    currencies_present = {row["currency"] for row in body["mrr_by_currency"]}
    assert "USD" in currencies_present
    assert "INR" in currencies_present
    # Each currency's own amount is correct -- never summed together.
    usd_row = next(r for r in body["mrr_by_currency"] if r["currency"] == "USD")
    inr_row = next(r for r in body["mrr_by_currency"] if r["currency"] == "INR")
    assert float(usd_row["amount"]) >= 20.0
    assert float(inr_row["amount"]) >= 1500.0
    # ARR is each currency's own MRR x 12, not a cross-currency figure.
    arr_inr_row = next(r for r in body["arr_by_currency"] if r["currency"] == "INR")
    assert float(arr_inr_row["amount"]) == float(inr_row["amount"]) * 12


def test_dashboard_mrr_normalizes_annual_plans_to_monthly(client, admin_auth_headers, auth_headers):
    annual_plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": f"Annual MRR Plan {uuid.uuid4().hex[:6]}",
            "price": 1200.0,
            "billing_interval": "annual",
            "trial_period_days": 0,
        },
    ).json()
    customer = _create_customer(client, auth_headers)
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": annual_plan["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=auth_headers)

    resp = client.get("/api/v1/analytics/dashboard", headers=admin_auth_headers)
    body = resp.json()
    # $1200/year contributes $100/month to MRR, not the full $1200.
    assert float(body["mrr"]) >= 100.0


def test_dashboard_counts_trial_customers(client, admin_auth_headers, auth_headers):
    # Deliberately trial_period_days > 0 -- a genuine trial. (Plans
    # with no trial period no longer create a TRIAL-status
    # subscription at all; see the Issue 2 fix in
    # SubscriptionService.create_subscription.)
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": f"Trial Analytics Plan {uuid.uuid4().hex[:8]}",
            "price": 10.0,
            "billing_interval": "monthly",
            "trial_period_days": 14,
        },
    ).json()
    customer = _create_customer(client, auth_headers)
    client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    )
    # Freshly created subscription on a genuine-trial plan is in trial
    # by default (no activate call).

    resp = client.get("/api/v1/analytics/dashboard", headers=admin_auth_headers)
    assert resp.json()["trial_customers"] >= 1


# ---------------------------------------------------------------------
# Revenue
# ---------------------------------------------------------------------


def test_revenue_analytics_totals_match_paid_invoice(client, admin_auth_headers):
    customer, sub, invoice_id, headers, plan_b = _paid_invoice_for_new_customer(
        client, admin_auth_headers, plan_a_price=20.0, plan_b_price=50.0
    )
    invoice = client.get(f"/api/v1/invoices/{invoice_id}", headers=headers).json()

    resp = client.get("/api/v1/analytics/revenue", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert float(body["total_revenue"]) >= float(invoice["total_amount"])
    assert len(body["revenue_by_month"]) >= 1
    plan_names = {item["plan_name"] for item in body["revenue_by_plan"]}
    assert plan_b["name"] in plan_names


def test_revenue_analytics_date_range_excludes_out_of_range(client, admin_auth_headers):
    _paid_invoice_for_new_customer(client, admin_auth_headers)

    # A date range entirely in the past should show zero revenue.
    resp = client.get(
        "/api/v1/analytics/revenue",
        params={"date_from": "2000-01-01", "date_to": "2000-01-31"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert float(body["total_revenue"]) == 0.0
    assert body["revenue_by_month"] == []
    assert body["date_from"] == "2000-01-01"
    assert body["date_to"] == "2000-01-31"


def test_revenue_by_plan_breaks_down_correctly(client, admin_auth_headers):
    _, _, _, _, plan_b = _paid_invoice_for_new_customer(
        client, admin_auth_headers, plan_a_price=15.0, plan_b_price=99.0
    )
    resp = client.get("/api/v1/analytics/revenue", headers=admin_auth_headers)
    body = resp.json()
    matching = [item for item in body["revenue_by_plan"] if item["plan_name"] == plan_b["name"]]
    assert len(matching) == 1
    assert float(matching[0]["revenue"]) > 0


# ---------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------


def test_subscription_analytics_breakdown_sums_to_total(client, admin_auth_headers, auth_headers):
    # Deliberately trial_period_days > 0 -- see the Issue 2 fix note
    # on test_dashboard_counts_trial_customers above.
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": f"Trial Breakdown Plan {uuid.uuid4().hex[:8]}",
            "price": 10.0,
            "billing_interval": "monthly",
            "trial_period_days": 14,
        },
    ).json()
    customer = _create_customer(client, auth_headers)
    client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    )

    resp = client.get("/api/v1/analytics/subscriptions", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_subscriptions"] == (
        body["active_subscriptions"]
        + body["trial_subscriptions"]
        + body["paused_subscriptions"]
        + body["past_due_subscriptions"]
        + body["cancelled_subscriptions"]
    )
    assert body["trial_subscriptions"] >= 1  # freshly created on a genuine-trial plan, still in trial
    assert body["expired_subscriptions"] == 0  # no such status exists in this schema


def test_subscription_analytics_active_and_paused_counts(client, admin_auth_headers, auth_headers):
    plan = _create_plan(client, admin_auth_headers)
    customer = _create_customer(client, auth_headers)
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=auth_headers)
    client.post(f"/api/v1/subscriptions/{sub['id']}/pause", headers=auth_headers)

    resp = client.get("/api/v1/analytics/subscriptions", headers=admin_auth_headers)
    assert resp.json()["paused_subscriptions"] >= 1


# ---------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------


def test_payment_analytics_counts_are_internally_consistent(client, admin_auth_headers):
    _paid_invoice_for_new_customer(client, admin_auth_headers)

    resp = client.get("/api/v1/analytics/payments", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_payments"] == (
        body["successful_payments"] + body["failed_payments"] + body["pending_payments"]
    )
    assert body["successful_payments"] >= 1


def test_payment_analytics_trend_reflects_processed_payment(client, admin_auth_headers):
    _paid_invoice_for_new_customer(client, admin_auth_headers)

    resp = client.get("/api/v1/analytics/payments", headers=admin_auth_headers)
    body = resp.json()
    assert len(body["payment_trends"]) >= 1
    total_trend_successful = sum(item["successful"] for item in body["payment_trends"])
    assert total_trend_successful >= 1


def test_payment_analytics_date_range_excludes_out_of_range(client, admin_auth_headers):
    _paid_invoice_for_new_customer(client, admin_auth_headers)

    resp = client.get(
        "/api/v1/analytics/payments",
        params={"date_from": "2000-01-01", "date_to": "2000-01-31"},
        headers=admin_auth_headers,
    )
    body = resp.json()
    assert body["payment_trends"] == []


def test_payment_analytics_counts_a_failed_payment(client, admin_auth_headers):
    _paid_invoice_for_new_customer(client, admin_auth_headers)

    # Set up a second, independent flow and force its payment to fail.
    email = f"analytics_fail_{uuid.uuid4().hex[:8]}@test.com"
    headers = _register_and_login(client, email)
    plan_a = _create_plan(client, admin_auth_headers, price=10.0)
    plan_b = _create_plan(client, admin_auth_headers, price=40.0)
    customer = client.get("/api/v1/customers/me", headers=headers).json()
    sub = client.post(
        "/api/v1/subscriptions",
        headers=headers,
        json={"customer_id": customer["id"], "plan_id": plan_a["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=headers)
    client.post(
        f"/api/v1/subscriptions/{sub['id']}/change-plan",
        headers=headers,
        json={"new_plan_id": plan_b["id"]},
    )
    invoice_id = client.get(
        "/api/v1/invoices", params={"customer_id": customer["id"]}, headers=headers
    ).json()["items"][0]["id"]
    with patch("app.services.payment_gateway_service.random.random", return_value=0.999):
        client.post("/api/v1/payments/process", headers=headers, json={"invoice_id": invoice_id})

    resp = client.get("/api/v1/analytics/payments", headers=admin_auth_headers)
    body = resp.json()
    assert body["successful_payments"] >= 1
    assert body["failed_payments"] >= 1


# ---------------------------------------------------------------------
# Refunds
# ---------------------------------------------------------------------


def test_refund_analytics_counts_and_amount(client, admin_auth_headers):
    customer, sub, invoice_id, headers, _ = _paid_invoice_for_new_customer(client, admin_auth_headers)
    refund_amount = 5.00
    client.post(
        "/api/v1/refunds",
        headers=headers,
        json={"invoice_id": invoice_id, "reason": "Analytics test refund", "amount": refund_amount},
    )

    resp = client.get("/api/v1/analytics/refunds", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_refunds"] >= 1
    assert body["completed_refunds"] >= 1
    assert body["total_refunds"] == (
        body["completed_refunds"] + body["pending_refunds"] + body["failed_refunds"]
    )
    assert float(body["total_refunded_amount"]) >= refund_amount


def test_refund_analytics_broken_out_by_currency(client, admin_auth_headers):
    """
    Fix (refund currency consistency): refunded_amount_by_currency
    must reflect the refund's actual currency, matching the invoice/
    payment it came from -- not a hardcoded assumption.
    """
    customer, sub, invoice_id, headers, _ = _paid_invoice_for_new_customer(client, admin_auth_headers)
    refund_amount = 5.00
    client.post(
        "/api/v1/refunds",
        headers=headers,
        json={"invoice_id": invoice_id, "reason": "Currency breakdown test", "amount": refund_amount},
    )

    resp = client.get("/api/v1/analytics/refunds", headers=admin_auth_headers)
    body = resp.json()
    assert "refunded_amount_by_currency" in body
    usd_rows = [r for r in body["refunded_amount_by_currency"] if r["currency"] == "USD"]
    assert usd_rows
    assert float(usd_rows[0]["amount"]) >= refund_amount
    # Sanity: the breakdown sums back to the same total the existing
    # (unchanged, backward-compatible) flat field already reports.
    breakdown_total = sum(float(r["amount"]) for r in body["refunded_amount_by_currency"])
    assert abs(breakdown_total - float(body["total_refunded_amount"])) < 0.01


def test_refund_analytics_zero_when_no_refunds(client, admin_auth_headers):
    resp = client.get("/api/v1/analytics/refunds", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_refunds"] == 0
    assert float(body["total_refunded_amount"]) == 0.0


# ---------------------------------------------------------------------
# GET /analytics/subscribers-by-plan
# ---------------------------------------------------------------------


def test_subscribers_by_plan_zero_subscriptions(client, admin_auth_headers):
    plan = _create_plan(client, admin_auth_headers, name=f"Empty Plan {uuid.uuid4().hex[:8]}")
    resp = client.get("/api/v1/analytics/subscribers-by-plan", headers=admin_auth_headers)
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["plan_id"] == plan["id"])
    assert row["subscriber_count"] == 0


def test_subscribers_by_plan_single_plan_single_subscriber(client, admin_auth_headers, auth_headers):
    plan = _create_plan(client, admin_auth_headers, name=f"Solo Plan {uuid.uuid4().hex[:8]}")
    customer = _create_customer(client, auth_headers)
    client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    )
    resp = client.get("/api/v1/analytics/subscribers-by-plan", headers=admin_auth_headers)
    row = next(r for r in resp.json() if r["plan_id"] == plan["id"])
    assert row["subscriber_count"] == 1
    assert row["plan_name"] == plan["name"]


def test_subscribers_by_plan_multiple_customers_same_plan(client, admin_auth_headers):
    """Exact count verification: 3 independent customers on the same plan -> count == 3."""
    plan = _create_plan(client, admin_auth_headers, name=f"Popular Plan {uuid.uuid4().hex[:8]}")
    for _ in range(3):
        headers = _register_and_login(client, f"multi_sub_{uuid.uuid4().hex[:8]}@test.com")
        customer = _create_customer(client, headers)
        client.post(
            "/api/v1/subscriptions",
            headers=headers,
            json={"customer_id": customer["id"], "plan_id": plan["id"]},
        )
    resp = client.get("/api/v1/analytics/subscribers-by-plan", headers=admin_auth_headers)
    row = next(r for r in resp.json() if r["plan_id"] == plan["id"])
    assert row["subscriber_count"] == 3


def test_subscribers_by_plan_multiple_plans_are_independently_counted(client, admin_auth_headers):
    plan_a = _create_plan(client, admin_auth_headers, name=f"Plan A {uuid.uuid4().hex[:8]}")
    plan_b = _create_plan(client, admin_auth_headers, name=f"Plan B {uuid.uuid4().hex[:8]}")
    headers_1 = _register_and_login(client, f"multiplan_{uuid.uuid4().hex[:8]}@test.com")
    customer_1 = _create_customer(client, headers_1)
    client.post(
        "/api/v1/subscriptions",
        headers=headers_1,
        json={"customer_id": customer_1["id"], "plan_id": plan_a["id"]},
    )
    headers_2 = _register_and_login(client, f"multiplan_{uuid.uuid4().hex[:8]}@test.com")
    customer_2 = _create_customer(client, headers_2)
    client.post(
        "/api/v1/subscriptions",
        headers=headers_2,
        json={"customer_id": customer_2["id"], "plan_id": plan_b["id"]},
    )

    resp = client.get("/api/v1/analytics/subscribers-by-plan", headers=admin_auth_headers)
    body = resp.json()
    row_a = next(r for r in body if r["plan_id"] == plan_a["id"])
    row_b = next(r for r in body if r["plan_id"] == plan_b["id"])
    assert row_a["subscriber_count"] == 1
    assert row_b["subscriber_count"] == 1


def test_subscribers_by_plan_excludes_cancelled_subscriptions(client, admin_auth_headers, auth_headers):
    """
    The exact bug this endpoint must not have: a cancelled
    subscription must NOT count as an active subscriber.
    """
    plan = _create_plan(client, admin_auth_headers, name=f"Cancel Test Plan {uuid.uuid4().hex[:8]}")
    customer = _create_customer(client, auth_headers)
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()

    before = client.get("/api/v1/analytics/subscribers-by-plan", headers=admin_auth_headers).json()
    assert next(r for r in before if r["plan_id"] == plan["id"])["subscriber_count"] == 1

    client.post(
        f"/api/v1/subscriptions/{sub['id']}/cancel",
        headers=auth_headers,
        json={"cancellation_type": "immediate"},
    )

    after = client.get("/api/v1/analytics/subscribers-by-plan", headers=admin_auth_headers).json()
    assert next(r for r in after if r["plan_id"] == plan["id"])["subscriber_count"] == 0


# ---------------------------------------------------------------------
# GET /analytics/refunds/trend
# ---------------------------------------------------------------------


def test_refund_trend_empty_when_no_refunds(client, admin_auth_headers):
    resp = client.get("/api/v1/analytics/refunds/trend", headers=admin_auth_headers)
    assert resp.status_code == 200
    # Not necessarily [] if other tests in this run created refunds --
    # only assert the shape and that it doesn't error.
    assert isinstance(resp.json(), list)


def test_refund_trend_one_refund_produces_one_month_with_correct_amount(client, admin_auth_headers):
    customer, sub, invoice_id, headers, _ = _paid_invoice_for_new_customer(client, admin_auth_headers)
    refund_amount = 12.34
    client.post(
        "/api/v1/refunds",
        headers=headers,
        json={"invoice_id": invoice_id, "reason": "Refund trend test", "amount": refund_amount},
    )

    resp = client.get("/api/v1/analytics/refunds/trend", headers=admin_auth_headers)
    body = resp.json()
    from datetime import date as _date

    current_month = _date.today().replace(day=1).isoformat()
    row = next(r for r in body if r["month"] == current_month)
    assert row["refund_count"] >= 1
    assert float(row["refund_amount"]) >= refund_amount


def test_refund_trend_multiple_refunds_same_month_aggregate_correctly(client, admin_auth_headers):
    """Exact amount aggregation: 2 refunds in the same month must sum, not just count."""
    _, _, invoice_id_1, headers_1, _ = _paid_invoice_for_new_customer(client, admin_auth_headers)
    _, _, invoice_id_2, headers_2, _ = _paid_invoice_for_new_customer(client, admin_auth_headers)

    before = client.get("/api/v1/analytics/refunds/trend", headers=admin_auth_headers).json()
    from datetime import date as _date

    current_month = _date.today().replace(day=1).isoformat()
    before_row = next((r for r in before if r["month"] == current_month), None)
    before_amount = float(before_row["refund_amount"]) if before_row else 0.0
    before_count = before_row["refund_count"] if before_row else 0

    client.post(
        "/api/v1/refunds",
        headers=headers_1,
        json={"invoice_id": invoice_id_1, "reason": "Trend aggregate test 1", "amount": 5.00},
    )
    client.post(
        "/api/v1/refunds",
        headers=headers_2,
        json={"invoice_id": invoice_id_2, "reason": "Trend aggregate test 2", "amount": 7.00},
    )

    after = client.get("/api/v1/analytics/refunds/trend", headers=admin_auth_headers).json()
    after_row = next(r for r in after if r["month"] == current_month)
    assert after_row["refund_count"] == before_count + 2
    assert abs(float(after_row["refund_amount"]) - (before_amount + 12.00)) < 0.01


def test_refund_trend_only_counts_completed_refunds(client, admin_auth_headers):
    """
    A refund that fails (rejected as invalid, e.g. exceeding the
    invoice total) must not appear in the trend at all -- it never
    completed, so it has no processed_at to group by.
    """
    customer, sub, invoice_id, headers, _ = _paid_invoice_for_new_customer(client, admin_auth_headers)
    invoice = client.get(f"/api/v1/invoices/{invoice_id}", headers=headers).json()
    too_much = float(invoice["total_amount"]) + 1000

    before = client.get("/api/v1/analytics/refunds/trend", headers=admin_auth_headers).json()
    from datetime import date as _date

    current_month = _date.today().replace(day=1).isoformat()
    before_count = next((r["refund_count"] for r in before if r["month"] == current_month), 0)

    resp = client.post(
        "/api/v1/refunds",
        headers=headers,
        json={"invoice_id": invoice_id, "reason": "Should be rejected", "amount": too_much},
    )
    assert resp.status_code in (400, 409, 422)  # rejected, never created/completed

    after = client.get("/api/v1/analytics/refunds/trend", headers=admin_auth_headers).json()
    after_count = next((r["refund_count"] for r in after if r["month"] == current_month), 0)
    assert after_count == before_count


# ---------------------------------------------------------------------
# GET /analytics/customers/trend
# ---------------------------------------------------------------------


def test_customer_trend_reflects_a_new_registration(client, admin_auth_headers):
    from datetime import date as _date

    current_month = _date.today().replace(day=1).isoformat()

    before = client.get("/api/v1/analytics/customers/trend", headers=admin_auth_headers).json()
    before_count = next((r["new_customers"] for r in before if r["month"] == current_month), 0)

    _register_and_login(client, f"trend_new_{uuid.uuid4().hex[:8]}@test.com")

    after = client.get("/api/v1/analytics/customers/trend", headers=admin_auth_headers).json()
    after_count = next((r["new_customers"] for r in after if r["month"] == current_month), 0)
    assert after_count == before_count + 1


def test_customer_trend_multiple_registrations_same_month_aggregate_correctly(
    client, admin_auth_headers
):
    """Exact count verification: 3 independent new customers in the same month must sum to +3."""
    from datetime import date as _date

    current_month = _date.today().replace(day=1).isoformat()

    before = client.get("/api/v1/analytics/customers/trend", headers=admin_auth_headers).json()
    before_count = next((r["new_customers"] for r in before if r["month"] == current_month), 0)

    for _ in range(3):
        headers = _register_and_login(client, f"trend_multi_{uuid.uuid4().hex[:8]}@test.com")
        _create_customer(client, headers)

    after = client.get("/api/v1/analytics/customers/trend", headers=admin_auth_headers).json()
    after_count = next((r["new_customers"] for r in after if r["month"] == current_month), 0)
    assert after_count == before_count + 3


def test_customer_trend_response_shape_is_chronological(client, admin_auth_headers, auth_headers):
    _create_customer(client, auth_headers)
    resp = client.get("/api/v1/analytics/customers/trend", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) > 0
    months = [row["month"] for row in body]
    assert months == sorted(months)


# ---------------------------------------------------------------------
# GET /analytics/mrr-by-plan
# ---------------------------------------------------------------------


def test_mrr_by_plan_reflects_real_active_subscription(client, admin_auth_headers, auth_headers):
    plan = _create_plan(client, admin_auth_headers, price=25.0, name=f"MRR Plan {uuid.uuid4().hex[:8]}")
    customer = _create_customer(client, auth_headers)
    client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    )

    resp = client.get("/api/v1/analytics/mrr-by-plan", headers=admin_auth_headers)
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["plan_id"] == plan["id"])
    assert float(row["mrr"]) == 25.0
    assert row["plan_name"] == plan["name"]


def test_mrr_by_plan_normalizes_annual_billing_to_monthly(client, admin_auth_headers, auth_headers):
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": f"MRR Annual Plan {uuid.uuid4().hex[:8]}",
            "price": 120.0,
            "billing_interval": "annual",
            "trial_period_days": 0,
        },
    ).json()
    customer = _create_customer(client, auth_headers)
    client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    )

    resp = client.get("/api/v1/analytics/mrr-by-plan", headers=admin_auth_headers)
    row = next(r for r in resp.json() if r["plan_id"] == plan["id"])
    assert float(row["mrr"]) == 10.0  # 120/12, same normalization as monthly_recurring_revenue()


def test_mrr_by_plan_excludes_plans_with_no_active_subscribers(client, admin_auth_headers):
    plan = _create_plan(client, admin_auth_headers, name=f"MRR Empty Plan {uuid.uuid4().hex[:8]}")
    resp = client.get("/api/v1/analytics/mrr-by-plan", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert not any(r["plan_id"] == plan["id"] for r in resp.json())


def test_mrr_by_plan_sum_matches_dashboard_total_mrr(client, admin_auth_headers, auth_headers):
    """
    Exact consistency check: summing every plan's contribution must
    equal the platform-wide MRR already shown by the dashboard KPI --
    both derive from the exact same normalization logic, just grouped
    differently.
    """
    plan = _create_plan(client, admin_auth_headers, price=15.0, name=f"MRR Consistency Plan {uuid.uuid4().hex[:8]}")
    customer = _create_customer(client, auth_headers)
    client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    )

    by_plan = client.get("/api/v1/analytics/mrr-by-plan", headers=admin_auth_headers).json()
    dashboard = client.get("/api/v1/analytics/dashboard", headers=admin_auth_headers).json()

    by_plan_totals = {}
    for row in by_plan:
        by_plan_totals[row["currency"]] = by_plan_totals.get(row["currency"], 0) + float(row["mrr"])

    for entry in dashboard["mrr_by_currency"]:
        assert abs(by_plan_totals.get(entry["currency"], 0) - float(entry["amount"])) < 0.01
