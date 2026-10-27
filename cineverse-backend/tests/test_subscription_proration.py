"""
Integration tests for proration on subscription plan changes
(Module 2): the /proration-preview endpoint and the auto-applied
proration invoice on /change-plan.
"""


def _create_active_subscription(client, auth_headers, admin_auth_headers, plan_price=40.00):
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": "Proration Basic Plan",
            "price": plan_price,
            "billing_interval": "monthly",
            "trial_period_days": 0,
        },
    ).json()
    customer = client.get("/api/v1/customers/me", headers=auth_headers).json()
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=auth_headers)
    return plan, customer, sub


def test_proration_preview_upgrade_shows_net_charge(client, auth_headers, admin_auth_headers):
    plan, customer, sub = _create_active_subscription(client, auth_headers, admin_auth_headers, plan_price=30.00)
    premium_plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Proration Premium Plan", "price": 90.00, "billing_interval": "monthly"},
    ).json()

    resp = client.post(
        f"/api/v1/subscriptions/{sub['id']}/proration-preview",
        headers=auth_headers,
        json={"new_plan_id": premium_plan["id"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["applicable"] is True
    assert float(body["net_amount"]) > 0  # upgrade => customer owes more


def test_proration_preview_downgrade_shows_net_credit(client, auth_headers, admin_auth_headers):
    plan, customer, sub = _create_active_subscription(client, auth_headers, admin_auth_headers, plan_price=90.00)
    basic_plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Proration Downgrade Plan", "price": 30.00, "billing_interval": "monthly"},
    ).json()

    resp = client.post(
        f"/api/v1/subscriptions/{sub['id']}/proration-preview",
        headers=auth_headers,
        json={"new_plan_id": basic_plan["id"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["applicable"] is True
    assert float(body["net_amount"]) < 0  # downgrade => customer owed credit


def test_proration_preview_not_applicable_during_trial(client, auth_headers, admin_auth_headers):
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Trial Preview Plan", "price": 20, "billing_interval": "monthly", "trial_period_days": 14},
    ).json()
    customer = client.get("/api/v1/customers/me", headers=auth_headers).json()
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    other_plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Trial Preview Plan 2", "price": 40, "billing_interval": "monthly"},
    ).json()

    resp = client.post(
        f"/api/v1/subscriptions/{sub['id']}/proration-preview",
        headers=auth_headers,
        json={"new_plan_id": other_plan["id"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["applicable"] is False


def test_change_plan_upgrade_generates_proration_invoice(client, auth_headers, admin_auth_headers):
    plan, customer, sub = _create_active_subscription(client, auth_headers, admin_auth_headers, plan_price=30.00)
    premium_plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Upgrade Target Plan", "price": 90.00, "billing_interval": "monthly"},
    ).json()

    resp = client.post(
        f"/api/v1/subscriptions/{sub['id']}/change-plan",
        headers=auth_headers,
        json={"new_plan_id": premium_plan["id"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan_id"] == premium_plan["id"]
    assert body["proration"] is not None
    assert body["proration"]["applicable"] is True
    assert float(body["proration"]["net_amount"]) > 0

    # A proration invoice should now exist for this subscription.
    invoices = client.get(
        "/api/v1/invoices",
        params={"subscription_id": sub["id"]},
        headers=auth_headers,
    ).json()
    assert invoices["total"] == 1
    invoice_detail = client.get(
        f"/api/v1/invoices/{invoices['items'][0]['id']}", headers=auth_headers
    ).json()
    item_types = {li["item_type"] for li in invoice_detail["line_items"]}
    assert "proration_credit" in item_types
    assert "proration_debit" in item_types


def test_change_plan_downgrade_generates_no_invoice(client, auth_headers, admin_auth_headers):
    plan, customer, sub = _create_active_subscription(client, auth_headers, admin_auth_headers, plan_price=90.00)
    basic_plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Downgrade Target Plan", "price": 30.00, "billing_interval": "monthly"},
    ).json()

    resp = client.post(
        f"/api/v1/subscriptions/{sub['id']}/change-plan",
        headers=auth_headers,
        json={"new_plan_id": basic_plan["id"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["proration"]["applicable"] is True
    assert float(body["proration"]["net_amount"]) < 0

    # No invoice should be generated since there's nothing to charge.
    invoices = client.get(
        "/api/v1/invoices",
        params={"subscription_id": sub["id"]},
        headers=auth_headers,
    ).json()
    assert invoices["total"] == 0


def test_change_plan_during_trial_has_no_proration(client, auth_headers, admin_auth_headers):
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Trial Change Plan", "price": 20, "billing_interval": "monthly", "trial_period_days": 14},
    ).json()
    customer = client.get("/api/v1/customers/me", headers=auth_headers).json()
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    other_plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Trial Change Plan 2", "price": 40, "billing_interval": "monthly"},
    ).json()

    resp = client.post(
        f"/api/v1/subscriptions/{sub['id']}/change-plan",
        headers=auth_headers,
        json={"new_plan_id": other_plan["id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["proration"] is None
