"""
Integration tests for the mock payment gateway APIs (Module 2).
"""
from unittest.mock import patch


def test_process_payment_success_updates_invoice_and_subscription(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        resp = client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["transaction_id"].startswith("MOCKTXN-")

    invoice = client.get(
        f"/api/v1/invoices/{fixture['invoice_id']}", headers=auth_headers
    ).json()
    assert invoice["status"] == "paid"


def test_process_payment_failure_marks_subscription_past_due(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    with patch("app.services.payment_gateway_service.random.random", return_value=0.999):
        resp = client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )
    assert resp.status_code == 201
    assert resp.json()["status"] == "failed"

    invoice = client.get(
        f"/api/v1/invoices/{fixture['invoice_id']}", headers=auth_headers
    ).json()
    assert invoice["status"] == "failed"

    subscription = client.get(
        f"/api/v1/subscriptions/{fixture['subscription']['id']}", headers=auth_headers
    ).json()
    assert subscription["status"] == "past_due"
    assert subscription["past_due_at"] is not None


def test_process_payment_uses_invoice_total_by_default(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        resp = client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )
    assert float(resp.json()["amount"]) == fixture["invoice_total"]


def test_cannot_pay_already_paid_invoice(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )
        second = client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )
    assert second.status_code == 409


def test_payment_process_requires_auth(client, active_subscription_with_invoice):
    fixture = active_subscription_with_invoice
    resp = client.post(
        "/api/v1/payments/process", json={"invoice_id": fixture["invoice_id"]}
    )
    assert resp.status_code == 401


def test_view_payment_history_for_invoice(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )

    history = client.get(
        f"/api/v1/invoices/{fixture['invoice_id']}/payments", headers=auth_headers
    )
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["status"] == "succeeded"


def test_attempt_number_increments_across_retries(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    with patch("app.services.payment_gateway_service.random.random", return_value=0.999):
        first = client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )
    assert first.status_code == 201

    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        second = client.post(
            "/api/v1/payments/process",
            headers=auth_headers,
            json={"invoice_id": fixture["invoice_id"]},
        )
    assert second.status_code == 201

    history = client.get(
        f"/api/v1/invoices/{fixture['invoice_id']}/payments", headers=auth_headers
    ).json()
    attempt_numbers = sorted(p["attempt_number"] for p in history)
    assert attempt_numbers == [1, 2]
