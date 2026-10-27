"""
Integration tests for audit log creation and retrieval.
"""
import uuid


def test_plan_creation_generates_audit_log(client, auth_headers, admin_auth_headers):
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Audited Plan", "price": 12.00, "billing_interval": "monthly"},
    ).json()

    trail = client.get(f"/api/v1/audit-logs/plan/{plan['id']}", headers=auth_headers)
    assert trail.status_code == 200
    events = trail.json()
    assert len(events) == 1
    assert events[0]["event_type"] == "plan_created"


def test_customer_creation_generates_audit_log(client, auth_headers):
    customer = client.get("/api/v1/customers/me", headers=auth_headers).json()

    trail = client.get(
        f"/api/v1/audit-logs/customer/{customer['id']}", headers=auth_headers
    )
    assert trail.status_code == 200
    events = trail.json()
    assert len(events) == 1
    assert events[0]["event_type"] == "customer_created"


def test_subscription_lifecycle_generates_multiple_audit_events(client, auth_headers, admin_auth_headers):
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Audit Lifecycle Plan", "price": 20, "billing_interval": "monthly"},
    ).json()
    customer = client.get("/api/v1/customers/me", headers=auth_headers).json()
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=auth_headers)
    client.post(f"/api/v1/subscriptions/{sub['id']}/pause", headers=auth_headers)

    trail = client.get(
        f"/api/v1/audit-logs/subscription/{sub['id']}", headers=auth_headers
    )
    assert trail.status_code == 200
    event_types = {e["event_type"] for e in trail.json()}
    assert "subscription_created" in event_types
    assert "billing_cycle_created" in event_types
    assert "status_changed" in event_types
    assert "subscription_paused" in event_types


def test_list_all_audit_logs_filtered_by_entity_type(client, auth_headers, admin_auth_headers):
    client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Filter Audit Plan", "price": 5, "billing_interval": "monthly"},
    )
    resp = client.get(
        "/api/v1/audit-logs", params={"entity_type": "plan"}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(item["entity_type"] == "plan" for item in body["items"])


def test_audit_logs_require_auth(client):
    resp = client.get("/api/v1/audit-logs")
    assert resp.status_code == 401


# ---------------------------------------------------------------------
# Final production review: audit-logs predates Phase 1D and had no
# ownership enforcement at all. These prove the fix.
# ---------------------------------------------------------------------


def _other_customer(client):
    email = f"audit_other_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Audit Other", "password": "SuperSecret123", "country": "US"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_cannot_view_another_customers_audit_trail(client, auth_headers):
    customer = client.get(
        "/api/v1/customers/me",
        headers=auth_headers,
    ).json()
    other_headers = _other_customer(client)

    resp = client.get(f"/api/v1/audit-logs/customer/{customer['id']}", headers=other_headers)
    assert resp.status_code == 403


def test_cannot_view_another_customers_subscription_audit_trail(
    client, auth_headers, admin_auth_headers
):
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"Audit Owner Plan {uuid.uuid4().hex[:6]}", "price": 10, "billing_interval": "monthly"},
    ).json()
    customer = client.get(
        "/api/v1/customers/me",
        headers=auth_headers,
    ).json()
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    other_headers = _other_customer(client)

    resp = client.get(f"/api/v1/audit-logs/subscription/{sub['id']}", headers=other_headers)
    assert resp.status_code == 403


def test_admin_can_view_any_customers_audit_trail(client, auth_headers, admin_auth_headers):
    customer = client.get(
        "/api/v1/customers/me",
        headers=auth_headers,
    ).json()

    resp = client.get(f"/api/v1/audit-logs/customer/{customer['id']}", headers=admin_auth_headers)
    assert resp.status_code == 200


def test_list_all_audit_logs_forbidden_for_non_admin_without_plan_filter(client, auth_headers):
    resp = client.get("/api/v1/audit-logs", headers=auth_headers)
    assert resp.status_code == 403


def test_list_all_audit_logs_forbidden_for_non_admin_filtered_by_customer(client, auth_headers):
    """
    Even filtered, this endpoint mixes every customer's rows together
    (no per-row scoping) -- only entity_type=plan is safe for a
    non-admin, since plans are public data.
    """
    resp = client.get(
        "/api/v1/audit-logs", params={"entity_type": "customer"}, headers=auth_headers
    )
    assert resp.status_code == 403


def test_list_all_audit_logs_admin_can_see_everything(client, auth_headers, admin_auth_headers):
    resp = client.get("/api/v1/audit-logs", headers=admin_auth_headers)
    assert resp.status_code == 200


def test_plan_audit_trail_viewable_by_any_authenticated_user(
    client, auth_headers, admin_auth_headers
):
    """Plans are public data (GET /plans needs no auth); their audit
    trail shouldn't be locked down more than the resource itself."""
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"Public Trail Plan {uuid.uuid4().hex[:6]}", "price": 8, "billing_interval": "monthly"},
    ).json()
    other_headers = _other_customer(client)

    resp = client.get(f"/api/v1/audit-logs/plan/{plan['id']}", headers=other_headers)
    assert resp.status_code == 200


def test_unrecognized_entity_type_fails_closed_for_non_admin(client, auth_headers):
    resp = client.get(
        f"/api/v1/audit-logs/something_unknown/{uuid.uuid4()}", headers=auth_headers
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------
# Account-wide Activity Timeline: registration/login/logout recording
# and GET /audit-logs/me
# ---------------------------------------------------------------------


def test_registration_is_recorded_in_the_activity_timeline(client):
    email = f"timeline_reg_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Timeline Reg", "password": "SuperSecret123", "country": "US"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/audit-logs/me", headers=headers)
    assert resp.status_code == 200
    event_types = [e["event_type"] for e in resp.json()["items"]]
    assert "user_registered" in event_types


def test_login_is_recorded_in_the_activity_timeline(client):
    email = f"timeline_login_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Timeline Login", "password": "SuperSecret123", "country": "US"},
    )
    # Log in twice -- both should show up.
    client.post("/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"})
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/audit-logs/me", headers=headers)
    event_types = [e["event_type"] for e in resp.json()["items"]]
    assert event_types.count("user_logged_in") == 2


def test_failed_login_is_not_recorded(client):
    """A wrong-password attempt should never appear as a successful login."""
    email = f"timeline_failedlogin_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Timeline Failed", "password": "SuperSecret123", "country": "US"},
    )
    client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPassword!"})
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/audit-logs/me", headers=headers)
    event_types = [e["event_type"] for e in resp.json()["items"]]
    # Exactly one successful login recorded, not two.
    assert event_types.count("user_logged_in") == 1


def test_logout_is_recorded_in_the_activity_timeline(client):
    email = f"timeline_logout_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Timeline Logout", "password": "SuperSecret123", "country": "US"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    logout_resp = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 204

    resp = client.get("/api/v1/audit-logs/me", headers=headers)
    event_types = [e["event_type"] for e in resp.json()["items"]]
    assert "user_logged_out" in event_types


def test_logout_requires_auth(client):
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 401


def test_activity_timeline_includes_subscription_invoice_payment_refund_events(
    client, admin_auth_headers
):
    """
    The core "account-wide" promise: events across every resource type
    that belongs to this account all show up in one place, not just
    the ones tied to a single subscription (the old, narrower
    RecentActivity behavior this endpoint supersedes).
    """
    email = f"timeline_full_{uuid.uuid4().hex[:8]}@test.com"
    headers = _register_and_login_for_timeline(client, email)

    plan_a = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"Timeline Plan A {uuid.uuid4().hex[:6]}", "price": 15, "billing_interval": "monthly", "trial_period_days": 0},
    ).json()
    plan_b = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"Timeline Plan B {uuid.uuid4().hex[:6]}", "price": 35, "billing_interval": "monthly"},
    ).json()
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
    from unittest.mock import patch

    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        client.post("/api/v1/payments/process", headers=headers, json={"invoice_id": invoice_id})
    client.post(
        "/api/v1/refunds",
        headers=headers,
        json={"invoice_id": invoice_id, "reason": "Timeline test refund", "amount": 2.0},
    )

    resp = client.get("/api/v1/audit-logs/me", headers=headers, params={"page_size": 100})
    assert resp.status_code == 200
    body = resp.json()
    entity_types = {e["entity_type"] for e in body["items"]}
    event_types = {e["event_type"] for e in body["items"]}

    # Spans every resource type this account touched, not just one subscription.
    assert "user" in entity_types
    assert "customer" in entity_types
    assert "subscription" in entity_types
    assert "invoice" in entity_types
    assert "refund" in entity_types
    assert "user_registered" in event_types
    assert "subscription_created" in event_types
    assert "proration_applied" in event_types  # this invoice came from an upgrade, not the scheduler
    assert "payment_succeeded" in event_types or "payment_processed" in event_types
    assert "refund_created" in event_types

    # Chronological (most recent first).
    timestamps = [e["created_at"] for e in body["items"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_activity_timeline_is_scoped_to_own_account_only(client, admin_auth_headers):
    """Someone else's registration/subscriptions must never appear in my timeline."""
    email_a = f"timeline_a_{uuid.uuid4().hex[:8]}@test.com"
    email_b = f"timeline_b_{uuid.uuid4().hex[:8]}@test.com"
    headers_a = _register_and_login_for_timeline(client, email_a)
    headers_b = _register_and_login_for_timeline(client, email_b)

    customer_a = client.get("/api/v1/customers/me", headers=headers_a).json()

    resp_b = client.get("/api/v1/audit-logs/me", headers=headers_b, params={"page_size": 100})
    descriptions_b = [e["description"] for e in resp_b.json()["items"]]
    assert not any("Timeline A" in d for d in descriptions_b)
    assert not any(email_a in d for d in descriptions_b)

    resp_a = client.get("/api/v1/audit-logs/me", headers=headers_a, params={"page_size": 100})
    descriptions_a = [e["description"] for e in resp_a.json()["items"]]
    assert any(customer_a["name"] in d for d in descriptions_a)


def test_activity_timeline_requires_auth(client):
    resp = client.get("/api/v1/audit-logs/me")
    assert resp.status_code == 401


def _register_and_login_for_timeline(client, email):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Timeline User", "password": "SuperSecret123", "country": "US"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
