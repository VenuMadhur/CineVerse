"""
Regression tests for a pagination bug found during the Module 1/2
review: several list endpoints computed `total` as `len(items)` (the
current page's item count) instead of the true count of all matching
rows. With more rows than one page, this made `total` incorrectly
capped at `page_size`, hiding every row past page 1 from any client
that computes total pages from `total`.

Fixed in: SubscriptionRepository, InvoiceRepository, PaymentRepository,
RefundRepository, AuditLogRepository (added `count_all`), and their
respective routers/services now use it instead of `len(items)`.
"""
import uuid
from unittest.mock import patch


def _create_plan(client, admin_auth_headers, price=10.0):
    return client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": f"Pagination Plan {uuid.uuid4().hex[:8]}",
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


def test_subscriptions_total_reflects_full_count_beyond_one_page(client, auth_headers, admin_auth_headers):
    customer = _create_customer(client, auth_headers)
    plans = [_create_plan(client, admin_auth_headers) for _ in range(3)]

    for plan in plans:
        client.post(
            "/api/v1/subscriptions",
            headers=auth_headers,
            json={"customer_id": customer["id"], "plan_id": plan["id"]},
        )

    # Request a page smaller than the number of subscriptions that exist.
    resp = client.get(
        "/api/v1/subscriptions",
        params={"customer_id": customer["id"], "page": 1, "page_size": 2},
        headers=auth_headers,
    )
    body = resp.json()
    assert len(body["items"]) == 2  # page is capped at page_size...
    assert body["total"] == 3  # ...but total must reflect the full count


def test_invoices_total_reflects_full_count_beyond_one_page(client, auth_headers, admin_auth_headers):
    customer = _create_customer(client, auth_headers)
    plan_a = _create_plan(client, admin_auth_headers, price=10.0)
    plan_b = _create_plan(client, admin_auth_headers, price=30.0)

    # Each activated subscription + upgrade generates one proration
    # invoice, giving us a precisely known number of invoices to check
    # pagination against.
    invoice_count = 0
    for _ in range(3):
        sub = client.post(
            "/api/v1/subscriptions",
            headers=auth_headers,
            json={"customer_id": customer["id"], "plan_id": plan_a["id"]},
        ).json()
        client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=auth_headers)
        change = client.post(
            f"/api/v1/subscriptions/{sub['id']}/change-plan",
            headers=auth_headers,
            json={"new_plan_id": plan_b["id"]},
        ).json()
        if change.get("proration") and change["proration"]["applicable"]:
            invoice_count += 1

    assert invoice_count >= 2  # sanity check the setup actually created multiple invoices

    resp = client.get(
        "/api/v1/invoices",
        params={"customer_id": customer["id"], "page": 1, "page_size": 1},
        headers=auth_headers,
    )
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["total"] == invoice_count


def test_refunds_total_reflects_full_count_beyond_one_page(client, auth_headers, admin_auth_headers):
    customer = _create_customer(client, auth_headers)
    plan_a = _create_plan(client, admin_auth_headers, price=20.0)
    plan_b = _create_plan(client, admin_auth_headers, price=40.0)

    subs_with_invoices = []
    for _ in range(3):
        sub = client.post(
            "/api/v1/subscriptions",
            headers=auth_headers,
            json={"customer_id": customer["id"], "plan_id": plan_a["id"]},
        ).json()
        client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=auth_headers)
        change = client.post(
            f"/api/v1/subscriptions/{sub['id']}/change-plan",
            headers=auth_headers,
            json={"new_plan_id": plan_b["id"]},
        ).json()
        if change.get("proration") and change["proration"]["applicable"]:
            subs_with_invoices.append(sub["id"])

    invoices = client.get(
        "/api/v1/invoices",
        params={"customer_id": customer["id"], "page_size": 50},
        headers=auth_headers,
    ).json()["items"]

    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        for invoice in invoices:
            client.post(
                "/api/v1/payments/process",
                headers=auth_headers,
                json={"invoice_id": invoice["id"]},
            )

    for invoice in invoices:
        client.post(
            "/api/v1/refunds",
            headers=auth_headers,
            json={"invoice_id": invoice["id"], "reason": "Pagination regression test"},
        )

    total_refunds = len(invoices)
    assert total_refunds >= 2  # sanity check the setup actually created multiple refunds

    resp = client.get(
        "/api/v1/refunds",
        params={"customer_id": customer["id"], "page": 1, "page_size": 1},
        headers=auth_headers,
    )
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["total"] == total_refunds


def test_audit_logs_total_reflects_full_count_beyond_one_page(client, auth_headers, admin_auth_headers):
    # Creating 3 plans generates at least 3 plan_created audit events.
    for _ in range(3):
        _create_plan(client, admin_auth_headers)

    resp = client.get(
        "/api/v1/audit-logs",
        params={"entity_type": "plan", "page": 1, "page_size": 1},
        headers=auth_headers,
    )
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["total"] >= 3


def test_payments_list_supports_customer_id_filter(
    client, auth_headers, active_subscription_with_invoice
):
    """
    Payment History previously only supported filtering by invoice_id;
    this verifies parity with Invoices/Refunds via the new customer_id
    filter (join through Invoice, no schema change).
    """
    fixture = active_subscription_with_invoice
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )

    resp = client.get(
        "/api/v1/payments",
        params={"customer_id": fixture["customer"]["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1

    # Phase 1D: a non-admin's customer_id filter is always forced to
    # their own linked customer, regardless of what they pass. So the
    # correct way to verify the security boundary is from the OTHER
    # user's perspective: they have no payments of their own, and
    # cannot see the first customer's payment even by explicitly
    # requesting that customer_id as a filter -- it's silently ignored
    # and replaced with their own (empty) scope.
    other_email = f"other_payments_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": other_email, "full_name": "Other User", "password": "SuperSecret123", "country": "US"},
    )
    other_token = client.post(
        "/api/v1/auth/login", json={"email": other_email, "password": "SuperSecret123"}
    ).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}
    _create_customer(client, other_headers)

    empty_resp = client.get(
        "/api/v1/payments",
        params={"customer_id": fixture["customer"]["id"]},  # attempt to see the first customer's payment
        headers=other_headers,
    )
    assert empty_resp.json()["total"] == 0
