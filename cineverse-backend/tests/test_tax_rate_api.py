"""
Tests for the Tax Rate CRUD API (Module 3, Phase 2a).
"""
import uuid
from datetime import date


def test_create_tax_rate_admin_only(client, auth_headers, admin_auth_headers):
    resp = client.post(
        "/api/v1/tax/rates",
        headers=auth_headers,
        json={
            "country": "JP",
            "tax_name": "Consumption Tax",
            "tax_percentage": 10.00,
            "effective_from": str(date.today()),
        },
    )
    assert resp.status_code == 403

    resp = client.post(
        "/api/v1/tax/rates",
        headers=admin_auth_headers,
        json={
            "country": "jp",
            "tax_name": "Consumption Tax",
            "tax_percentage": 10.00,
            "effective_from": str(date.today()),
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["country"] == "JP"  # normalized to uppercase
    assert float(body["tax_percentage"]) == 10.00
    assert body["is_active"] is True


def test_create_tax_rate_requires_auth(client):
    resp = client.post(
        "/api/v1/tax/rates",
        json={
            "country": "JP",
            "tax_name": "Tax",
            "tax_percentage": 10.00,
            "effective_from": str(date.today()),
        },
    )
    assert resp.status_code == 401


def test_list_tax_rates_admin_only_and_filterable_by_country(
    client, auth_headers, admin_auth_headers
):
    resp = client.get("/api/v1/tax/rates", headers=auth_headers)
    assert resp.status_code == 403

    before = client.get("/api/v1/tax/rates", headers=admin_auth_headers).json()["total"]
    client.post(
        "/api/v1/tax/rates",
        headers=admin_auth_headers,
        json={
            "country": "NZ",
            "tax_name": "GST",
            "tax_percentage": 15.00,
            "effective_from": str(date.today()),
        },
    )
    after_resp = client.get("/api/v1/tax/rates", headers=admin_auth_headers)
    assert after_resp.status_code == 200
    assert after_resp.json()["total"] == before + 1

    resp = client.get(
        "/api/v1/tax/rates", headers=admin_auth_headers, params={"country": "NZ"}
    )
    assert resp.status_code == 200
    assert all(item["country"] == "NZ" for item in resp.json()["items"])
    assert len(resp.json()["items"]) == 1


def test_get_tax_rate_by_id(client, admin_auth_headers):
    created = client.post(
        "/api/v1/tax/rates",
        headers=admin_auth_headers,
        json={
            "country": "MX",
            "tax_name": "IVA",
            "tax_percentage": 16.00,
            "effective_from": str(date.today()),
        },
    ).json()

    resp = client.get(f"/api/v1/tax/rates/{created['id']}", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_tax_rate_not_found(client, admin_auth_headers):
    resp = client.get(f"/api/v1/tax/rates/{uuid.uuid4()}", headers=admin_auth_headers)
    assert resp.status_code == 404


def test_update_tax_rate(client, admin_auth_headers):
    created = client.post(
        "/api/v1/tax/rates",
        headers=admin_auth_headers,
        json={
            "country": "BR",
            "tax_name": "ICMS",
            "tax_percentage": 17.00,
            "effective_from": str(date.today()),
        },
    ).json()

    resp = client.patch(
        f"/api/v1/tax/rates/{created['id']}",
        headers=admin_auth_headers,
        json={"tax_percentage": 18.00},
    )
    assert resp.status_code == 200
    assert float(resp.json()["tax_percentage"]) == 18.00
    assert resp.json()["tax_name"] == "ICMS"  # unchanged


def test_deactivate_tax_rate(client, admin_auth_headers):
    created = client.post(
        "/api/v1/tax/rates",
        headers=admin_auth_headers,
        json={
            "country": "ZA",
            "tax_name": "VAT",
            "tax_percentage": 15.00,
            "effective_from": str(date.today()),
        },
    ).json()

    resp = client.patch(
        f"/api/v1/tax/rates/{created['id']}",
        headers=admin_auth_headers,
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_update_tax_rate_admin_only(client, auth_headers, admin_auth_headers):
    created = client.post(
        "/api/v1/tax/rates",
        headers=admin_auth_headers,
        json={
            "country": "KR",
            "tax_name": "VAT",
            "tax_percentage": 10.00,
            "effective_from": str(date.today()),
        },
    ).json()

    resp = client.patch(
        f"/api/v1/tax/rates/{created['id']}",
        headers=auth_headers,
        json={"tax_percentage": 20.00},
    )
    assert resp.status_code == 403


def test_update_tax_rate_not_found(client, admin_auth_headers):
    resp = client.patch(
        f"/api/v1/tax/rates/{uuid.uuid4()}",
        headers=admin_auth_headers,
        json={"tax_percentage": 5.00},
    )
    assert resp.status_code == 404


def test_tax_rate_audit_events_recorded(client, admin_auth_headers):
    created = client.post(
        "/api/v1/tax/rates",
        headers=admin_auth_headers,
        json={
            "country": "SG",
            "tax_name": "GST",
            "tax_percentage": 9.00,
            "effective_from": str(date.today()),
        },
    ).json()
    client.patch(
        f"/api/v1/tax/rates/{created['id']}",
        headers=admin_auth_headers,
        json={"tax_percentage": 9.50},
    )

    resp = client.get(
        f"/api/v1/audit-logs/tax_rate/{created['id']}", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    event_types = [e["event_type"] for e in resp.json()]
    assert "tax_rate_created" in event_types
    assert "tax_rate_updated" in event_types


def test_seeded_tax_rates_produce_identical_invoice_tax(
    client, auth_headers, admin_auth_headers, active_subscription_with_invoice
):
    """
    The core regression guarantee for this phase: an invoice generated
    for a customer in a seeded country (US) must produce the exact
    same tax amount as before Phase 2a's migration (settings.TAX_RATES
    had US at 8%).
    """
    fixture = active_subscription_with_invoice
    resp = client.get(f"/api/v1/invoices/{fixture['invoice_id']}", headers=auth_headers)
    invoice = resp.json()
    expected_tax = round(float(invoice["subtotal"]) * 0.08, 2)
    assert abs(float(invoice["tax_amount"]) - expected_tax) < 0.01
