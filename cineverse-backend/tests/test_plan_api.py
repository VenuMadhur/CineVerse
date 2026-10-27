"""
Integration tests for Plan Management APIs.

Plan creation/update/archive became admin-only in Phase 1C; list/get
remain public. Tests below use `admin_auth_headers` for mutations and
add explicit coverage that a regular (non-admin) user is rejected.
"""


def test_create_plan(client, admin_auth_headers):
    resp = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": "Starter Monthly",
            "description": "Entry-level plan",
            "price": 9.99,
            "currency": "usd",
            "billing_interval": "monthly",
            "trial_period_days": 7,
            "feature_entitlements": {"seats": 1},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Starter Monthly"
    assert body["currency"] == "USD"
    assert body["status"] == "active"


def test_create_plan_as_regular_customer_is_forbidden(client, auth_headers):
    """Phase 1C: plan creation is admin-only."""
    resp = client.post(
        "/api/v1/plans",
        headers=auth_headers,
        json={"name": "Should Not Be Created", "price": 9.99, "billing_interval": "monthly"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_create_duplicate_plan_name_conflicts(client, admin_auth_headers):
    payload = {
        "name": "Duplicate Plan",
        "price": 19.99,
        "billing_interval": "monthly",
        "trial_period_days": 0,
    }
    first = client.post("/api/v1/plans", headers=admin_auth_headers, json=payload)
    assert first.status_code == 201

    second = client.post("/api/v1/plans", headers=admin_auth_headers, json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


def test_create_plan_requires_auth(client):
    resp = client.post(
        "/api/v1/plans",
        json={"name": "No Auth Plan", "price": 5, "billing_interval": "monthly"},
    )
    assert resp.status_code == 401


def test_update_plan(client, admin_auth_headers):
    created = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Update Me", "price": 15, "billing_interval": "monthly"},
    ).json()

    updated = client.patch(
        f"/api/v1/plans/{created['id']}",
        headers=admin_auth_headers,
        json={"price": 25.50, "trial_period_days": 10},
    )
    assert updated.status_code == 200
    assert float(updated.json()["price"]) == 25.50
    assert updated.json()["trial_period_days"] == 10


def test_update_plan_as_regular_customer_is_forbidden(client, admin_auth_headers, auth_headers):
    created = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Update Me Forbidden", "price": 15, "billing_interval": "monthly"},
    ).json()

    resp = client.patch(
        f"/api/v1/plans/{created['id']}", headers=auth_headers, json={"price": 1.00}
    )
    assert resp.status_code == 403


def test_archive_plan(client, admin_auth_headers):
    created = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Archive Me", "price": 15, "billing_interval": "annual"},
    ).json()

    archived = client.post(f"/api/v1/plans/{created['id']}/archive", headers=admin_auth_headers)
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    # Archiving again should conflict
    second = client.post(f"/api/v1/plans/{created['id']}/archive", headers=admin_auth_headers)
    assert second.status_code == 409


def test_archive_plan_as_regular_customer_is_forbidden(client, admin_auth_headers, auth_headers):
    created = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Archive Me Forbidden", "price": 15, "billing_interval": "annual"},
    ).json()

    resp = client.post(f"/api/v1/plans/{created['id']}/archive", headers=auth_headers)
    assert resp.status_code == 403


def test_unarchive_plan(client, admin_auth_headers):
    created = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Unarchive Me", "price": 12, "billing_interval": "monthly"},
    ).json()
    client.post(f"/api/v1/plans/{created['id']}/archive", headers=admin_auth_headers)

    unarchived = client.post(f"/api/v1/plans/{created['id']}/unarchive", headers=admin_auth_headers)
    assert unarchived.status_code == 200
    assert unarchived.json()["status"] == "active"

    # Now visible again to the customer-facing active-only list.
    active_list = client.get("/api/v1/plans", params={"status": "active"})
    assert any(p["id"] == created["id"] for p in active_list.json()["items"])

    # Unarchiving an already-active plan should conflict.
    second = client.post(f"/api/v1/plans/{created['id']}/unarchive", headers=admin_auth_headers)
    assert second.status_code == 409


def test_unarchive_plan_as_regular_customer_is_forbidden(client, admin_auth_headers, auth_headers):
    created = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Unarchive Forbidden", "price": 12, "billing_interval": "monthly"},
    ).json()
    client.post(f"/api/v1/plans/{created['id']}/archive", headers=admin_auth_headers)

    resp = client.post(f"/api/v1/plans/{created['id']}/unarchive", headers=auth_headers)
    assert resp.status_code == 403


def test_delete_plan_with_no_subscriptions_succeeds(client, admin_auth_headers):
    created = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Safe To Delete", "price": 9, "billing_interval": "monthly"},
    ).json()

    resp = client.delete(f"/api/v1/plans/{created['id']}", headers=admin_auth_headers)
    assert resp.status_code == 204

    follow_up = client.get(f"/api/v1/plans/{created['id']}")
    assert follow_up.status_code == 404


def test_delete_plan_with_active_subscription_is_blocked(
    client, admin_auth_headers, auth_headers
):
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "In Use Plan", "price": 20, "billing_interval": "monthly"},
    ).json()
    customer = client.get("/api/v1/customers/me", headers=auth_headers).json()
    client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    )

    resp = client.delete(f"/api/v1/plans/{plan['id']}", headers=admin_auth_headers)
    assert resp.status_code == 409
    assert "subscription" in resp.json()["error"]["message"].lower()

    # The plan must still exist, untouched.
    still_there = client.get(f"/api/v1/plans/{plan['id']}")
    assert still_there.status_code == 200


def test_delete_plan_is_blocked_even_after_the_subscription_is_cancelled(
    client, admin_auth_headers, auth_headers
):
    """
    Confirms the safety check isn't limited to *active* subscriptions
    -- a plan that was ever used (even by a now-cancelled subscription,
    which is exactly when historical invoices/payments/refunds would
    exist) must stay protected too.
    """
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Formerly In Use Plan", "price": 18, "billing_interval": "monthly"},
    ).json()
    customer = client.get("/api/v1/customers/me", headers=auth_headers).json()
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

    resp = client.delete(f"/api/v1/plans/{plan['id']}", headers=admin_auth_headers)
    assert resp.status_code == 409


def test_delete_plan_as_regular_customer_is_forbidden(client, admin_auth_headers, auth_headers):
    created = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Delete Forbidden", "price": 9, "billing_interval": "monthly"},
    ).json()

    resp = client.delete(f"/api/v1/plans/{created['id']}", headers=auth_headers)
    assert resp.status_code == 403


def test_list_plans_filter_by_status(client, admin_auth_headers):
    client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Filter Test Plan", "price": 5, "billing_interval": "monthly"},
    )
    # Listing plans remains public -- no auth needed.
    resp = client.get("/api/v1/plans", params={"status": "active"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(p["status"] == "active" for p in body["items"])


def test_get_plan_not_found(client):
    resp = client.get("/api/v1/plans/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
