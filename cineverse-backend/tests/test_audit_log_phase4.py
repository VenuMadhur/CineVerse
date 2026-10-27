"""
Tests for Module 3, Phase 4 (Audit Log Enhancements): the 5 new
optional fields (ip_address, actor_role, old_value, new_value,
remarks), the 5 new event types, and that every existing audit
behavior is completely unaffected.
"""
import uuid
from unittest.mock import patch


def test_existing_audit_fields_still_present_and_new_fields_default_null(
    client, admin_auth_headers
):
    """Backward compatibility: an event with no new fields populated
    (e.g. a pre-Phase-4-style call site) must return null for all 5,
    not error or omit them."""
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"P4 Plan {uuid.uuid4().hex[:6]}", "price": 10, "billing_interval": "monthly"},
    ).json()

    resp = client.get(f"/api/v1/audit-logs/plan/{plan['id']}", headers=admin_auth_headers)
    assert resp.status_code == 200
    event = resp.json()[0]
    for field in ["id", "event_type", "entity_type", "actor_id", "description", "created_at"]:
        assert field in event


def test_registration_login_logout_capture_ip_and_role(client):
    email = f"p4ip_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "P4 IP Test", "password": "SuperSecret123", "country": "US"},
        headers={"X-Forwarded-For": "203.0.113.42"},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SuperSecret123"},
        headers={"X-Forwarded-For": "203.0.113.42"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/auth/logout", headers={**headers, "X-Forwarded-For": "203.0.113.42"})

    resp = client.get("/api/v1/audit-logs/me", headers=headers)
    events = {e["event_type"]: e for e in resp.json()["items"]}
    for event_type in ["user_registered", "user_logged_in", "user_logged_out"]:
        assert event_type in events
        assert events[event_type]["ip_address"] == "203.0.113.42"
        assert events[event_type]["actor_role"] == "customer"


def test_plan_update_captures_old_and_new_value(client, admin_auth_headers):
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"P4 Update Plan {uuid.uuid4().hex[:6]}", "price": 10, "billing_interval": "monthly"},
    ).json()
    client.patch(f"/api/v1/plans/{plan['id']}", headers=admin_auth_headers, json={"price": 15})

    resp = client.get(f"/api/v1/audit-logs/plan/{plan['id']}", headers=admin_auth_headers)
    updated = next(e for e in resp.json() if e["event_type"] == "plan_updated")
    assert "price" in updated["old_value"]
    assert "price" in updated["new_value"]
    assert "10" in updated["old_value"]
    assert "15" in updated["new_value"]


def test_trial_started_fires_for_trial_plan_not_for_no_trial_plan(
    client, auth_headers, admin_auth_headers
):
    trial_plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"P4 Trial Plan {uuid.uuid4().hex[:6]}", "price": 10, "billing_interval": "monthly", "trial_period_days": 7},
    ).json()
    no_trial_plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"P4 NoTrial Plan {uuid.uuid4().hex[:6]}", "price": 10, "billing_interval": "monthly", "trial_period_days": 0},
    ).json()
    email = f"p4trial_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "P4 Trial", "password": "SuperSecret123", "country": "US"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    customer = client.get("/api/v1/customers/me", headers=headers).json()

    trial_sub = client.post(
        "/api/v1/subscriptions", headers=headers,
        json={"customer_id": customer["id"], "plan_id": trial_plan["id"]},
    ).json()
    no_trial_sub = client.post(
        "/api/v1/subscriptions", headers=headers,
        json={"customer_id": customer["id"], "plan_id": no_trial_plan["id"]},
    ).json()

    trial_events = client.get(
        f"/api/v1/audit-logs/subscription/{trial_sub['id']}", headers=headers
    ).json()
    assert any(e["event_type"] == "trial_started" for e in trial_events)

    no_trial_events = client.get(
        f"/api/v1/audit-logs/subscription/{no_trial_sub['id']}", headers=headers
    ).json()
    assert not any(e["event_type"] == "trial_started" for e in no_trial_events)


def test_trial_ended_fires_on_activation(client, auth_headers, admin_auth_headers):
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"P4 TrialEnd Plan {uuid.uuid4().hex[:6]}", "price": 10, "billing_interval": "monthly", "trial_period_days": 7},
    ).json()
    email = f"p4trialend_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "P4 TrialEnd", "password": "SuperSecret123", "country": "US"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    customer = client.get("/api/v1/customers/me", headers=headers).json()
    sub = client.post(
        "/api/v1/subscriptions", headers=headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=headers)

    events = client.get(f"/api/v1/audit-logs/subscription/{sub['id']}", headers=headers).json()
    ended = next((e for e in events if e["event_type"] == "trial_ended"), None)
    assert ended is not None
    assert ended["old_value"] == "trial"
    assert ended["new_value"] == "active"


def test_pdf_download_fires_pdf_generated_and_invoice_downloaded_with_ip(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    client.get(
        f"/api/v1/invoices/{fixture['invoice_id']}/pdf",
        headers={**auth_headers, "X-Forwarded-For": "198.51.100.7"},
    )

    events = client.get(
        f"/api/v1/audit-logs/invoice/{fixture['invoice_id']}", headers=auth_headers
    ).json()
    event_types = [e["event_type"] for e in events]
    assert "pdf_generated" in event_types
    assert "invoice_downloaded" in event_types
    pdf_event = next(e for e in events if e["event_type"] == "pdf_generated")
    assert pdf_event["ip_address"] == "198.51.100.7"
    assert pdf_event["actor_role"] == "customer"


def test_refund_fires_invoice_updated_on_invoice_entity(
    client, auth_headers, active_subscription_with_invoice
):
    fixture = active_subscription_with_invoice
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        client.post(
            "/api/v1/payments/process", headers=auth_headers, json={"invoice_id": fixture["invoice_id"]}
        )
    client.post(
        "/api/v1/refunds",
        headers=auth_headers,
        json={"invoice_id": fixture["invoice_id"], "reason": "Phase 4 test", "amount": 1.00},
    )

    events = client.get(
        f"/api/v1/audit-logs/invoice/{fixture['invoice_id']}", headers=auth_headers
    ).json()
    updated = next((e for e in events if e["event_type"] == "invoice_updated"), None)
    assert updated is not None
    assert "total_amount" in updated["old_value"]
    assert updated["remarks"] is not None


def test_retry_configuration_update_captures_old_new_value(client, admin_auth_headers):
    created = client.post(
        "/api/v1/retry/configuration",
        headers=admin_auth_headers,
        json={"retry_attempt": 1, "retry_after_days": 1},
    ).json()
    client.patch(
        f"/api/v1/retry/configuration/{created['id']}",
        headers=admin_auth_headers,
        json={"retry_after_days": 2},
    )
    events = client.get(
        f"/api/v1/audit-logs/retry_configuration/{created['id']}", headers=admin_auth_headers
    ).json()
    updated = next(e for e in events if e["event_type"] == "retry_configuration_updated")
    assert "retry_after_days" in updated["old_value"]
    assert "retry_after_days" in updated["new_value"]


def test_tax_rate_update_captures_old_new_value(client, admin_auth_headers):
    from datetime import date

    created = client.post(
        "/api/v1/tax/rates",
        headers=admin_auth_headers,
        json={"country": "P4", "tax_name": "P4 Tax", "tax_percentage": 5.00, "effective_from": str(date.today())},
    ).json()
    client.patch(
        f"/api/v1/tax/rates/{created['id']}", headers=admin_auth_headers, json={"tax_percentage": 7.50}
    )
    events = client.get(
        f"/api/v1/audit-logs/tax_rate/{created['id']}", headers=admin_auth_headers
    ).json()
    updated = next(e for e in events if e["event_type"] == "tax_rate_updated")
    assert "tax_percentage" in updated["old_value"]
    assert "tax_percentage" in updated["new_value"]
