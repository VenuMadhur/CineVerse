"""
Integration tests for Invoice APIs (Module 2).
"""


def test_get_invoice_includes_line_items(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    resp = client.get(f"/api/v1/invoices/{fixture['invoice_id']}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["invoice_number"].startswith("INV-")
    assert len(body["line_items"]) >= 1
    item_types = {li["item_type"] for li in body["line_items"]}
    assert "plan_fee" in item_types
    # US customer -> 8% configured tax rate -> a TAX line item should exist
    assert "tax" in item_types


def test_invoice_totals_include_tax(client, auth_headers, active_subscription_with_invoice):
    fixture = active_subscription_with_invoice
    invoice = client.get(
        f"/api/v1/invoices/{fixture['invoice_id']}", headers=auth_headers
    ).json()
    assert float(invoice["tax_amount"]) > 0
    assert float(invoice["total_amount"]) == float(invoice["subtotal"]) + float(
        invoice["tax_amount"]
    )


def test_list_invoices_by_customer(client, auth_headers, active_subscription_with_invoice):
    fixture = active_subscription_with_invoice
    resp = client.get(
        "/api/v1/invoices",
        params={"customer_id": fixture["customer"]["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(i["customer_id"] == fixture["customer"]["id"] for i in body["items"])


def test_list_invoices_by_status(client, auth_headers, active_subscription_with_invoice):
    fixture = active_subscription_with_invoice
    resp = client.get(
        "/api/v1/invoices", params={"status": "open"}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert all(i["status"] == "open" for i in body["items"])


def test_get_invoice_not_found(client, auth_headers):
    resp = client.get(
        "/api/v1/invoices/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert resp.status_code == 404


def test_invoice_endpoints_require_auth(client, active_subscription_with_invoice):
    fixture = active_subscription_with_invoice
    resp = client.get(f"/api/v1/invoices/{fixture['invoice_id']}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------
# Phase 6C: enriched invoice detail (customer info, payment method,
# discount, refund status) and "Email Invoice"
# ---------------------------------------------------------------------


def test_invoice_detail_includes_denormalized_customer_fields(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    resp = client.get(f"/api/v1/invoices/{fixture['invoice_id']}", headers=auth_headers)
    body = resp.json()
    assert body["customer_name"] == fixture["customer"]["name"]
    assert body["customer_email"] == fixture["customer"]["email"]
    assert body["customer_country"] == fixture["customer"]["country"]


def test_invoice_detail_refund_status_none_before_any_refund(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    resp = client.get(f"/api/v1/invoices/{fixture['invoice_id']}", headers=auth_headers)
    body = resp.json()
    assert body["refund_status"] == "none"
    assert float(body["discount_amount"]) == 0.0
    assert body["payment_method"] is None  # not paid yet in this fixture


def test_invoice_detail_payment_method_after_payment(
    client, auth_headers, active_subscription_with_invoice
):
    from unittest.mock import patch

    fixture = active_subscription_with_invoice
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )

    resp = client.get(f"/api/v1/invoices/{fixture['invoice_id']}", headers=auth_headers)
    body = resp.json()
    assert body["payment_method"] == "mock_gateway"


def test_invoice_detail_refund_status_partial_after_partial_refund(
    client, auth_headers, active_subscription_with_invoice
):
    from unittest.mock import patch

    fixture = active_subscription_with_invoice
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )
    client.post(
        "/api/v1/refunds",
        headers=auth_headers,
        json={"invoice_id": fixture["invoice_id"], "reason": "Partial test", "amount": 1.00},
    )

    resp = client.get(f"/api/v1/invoices/{fixture['invoice_id']}", headers=auth_headers)
    body = resp.json()
    assert body["refund_status"] == "partial"
    assert body["status"] == "paid"  # partial refund doesn't flip invoice status


def test_invoice_detail_refund_status_full_after_full_refund(
    client, auth_headers, active_subscription_with_invoice
):
    from unittest.mock import patch

    fixture = active_subscription_with_invoice
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )
    client.post(
        "/api/v1/refunds",
        headers=auth_headers,
        json={"invoice_id": fixture["invoice_id"], "reason": "Full refund test"},
    )

    resp = client.get(f"/api/v1/invoices/{fixture['invoice_id']}", headers=auth_headers)
    body = resp.json()
    assert body["refund_status"] == "full"
    assert body["status"] == "refunded"


def test_email_invoice_dispatches_task(client, auth_headers, active_subscription_with_invoice):
    from unittest.mock import patch

    fixture = active_subscription_with_invoice
    with patch("app.tasks.notification_tasks.send_invoice_email.delay") as mock_delay:
        resp = client.post(f"/api/v1/invoices/{fixture['invoice_id']}/email", headers=auth_headers)
    assert resp.status_code == 202
    mock_delay.assert_called_once_with(fixture["invoice_id"])


def test_email_invoice_requires_auth(client, active_subscription_with_invoice):
    fixture = active_subscription_with_invoice
    resp = client.post(f"/api/v1/invoices/{fixture['invoice_id']}/email")
    assert resp.status_code == 401


def test_email_invoice_forbidden_for_other_customer(client, active_subscription_with_invoice):
    fixture = active_subscription_with_invoice
    client.post(
        "/api/v1/auth/register",
        json={"email": "other_email_invoice@test.com", "full_name": "Other", "password": "SuperSecret123", "country": "US"},
    )
    other_token = client.post(
        "/api/v1/auth/login",
        json={"email": "other_email_invoice@test.com", "password": "SuperSecret123"},
    ).json()["access_token"]
    resp = client.post(
        f"/api/v1/invoices/{fixture['invoice_id']}/email",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


def test_email_invoice_not_found(client, auth_headers):
    resp = client.post(
        "/api/v1/invoices/00000000-0000-0000-0000-000000000000/email", headers=auth_headers
    )
    assert resp.status_code == 404


def test_email_invoice_failure_does_not_break_request(
    client, auth_headers, active_subscription_with_invoice
):
    """Same non-blocking guarantee as every other notification dispatch."""
    from unittest.mock import patch

    fixture = active_subscription_with_invoice
    with patch(
        "app.tasks.notification_tasks.send_invoice_email.delay",
        side_effect=Exception("broker unreachable"),
    ):
        resp = client.post(f"/api/v1/invoices/{fixture['invoice_id']}/email", headers=auth_headers)
    assert resp.status_code == 202
