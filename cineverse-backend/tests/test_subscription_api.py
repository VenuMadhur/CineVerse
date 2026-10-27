"""
Integration tests for Subscription Management APIs: creation, plan
change, pause/resume, cancellation (immediate and end-of-cycle), and
status transition enforcement.
"""
import uuid
from unittest.mock import patch

import pytest


@pytest.fixture()
def plan_and_customer(client, auth_headers, admin_auth_headers):
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": "Subscription Test Plan",
            "price": 49.00,
            "billing_interval": "monthly",
            "trial_period_days": 14,
        },
    ).json()
    customer = client.get("/api/v1/customers/me", headers=auth_headers).json()
    return plan, customer


def test_create_subscription_starts_in_trial(client, auth_headers, plan_and_customer):
    plan, customer = plan_and_customer
    resp = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "trial"
    assert body["trial_started_at"] is not None
    assert body["trial_ends_at"] is not None


def test_create_subscription_with_zero_trial_days_starts_active(client, auth_headers, admin_auth_headers):
    """
    Issue 2 fix: a plan with trial_period_days=0 must start the
    subscription directly in ACTIVE status, not TRIAL -- previously
    every subscription started in TRIAL unconditionally, even with a
    zero-length trial, which only ever produced a trial that had
    already technically ended rather than genuinely skipping it.
    """
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": f"No Trial Plan {uuid.uuid4().hex[:8]}",
            "price": 15,
            "billing_interval": "monthly",
            "trial_period_days": 0,
        },
    ).json()
    email = f"notrial_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "No Trial Customer", "email": email, "password": "SuperSecret123", "country": "US"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}).json()["access_token"]
    test_headers = {"Authorization": f"Bearer {token}"}
    customer = client.get("/api/v1/customers/me", headers=test_headers).json()

    resp = client.post(
        "/api/v1/subscriptions",
        headers=test_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "active"
    assert body["activated_at"] is not None

    # A subscription that's already active has nothing left for
    # /activate to do -- confirms this doesn't leave it in some
    # in-between state that a manual activate call could still affect.
    activate_resp = client.post(f"/api/v1/subscriptions/{body['id']}/activate", headers=test_headers)
    assert activate_resp.status_code == 409


def test_create_subscription_for_archived_plan_fails(client, auth_headers, admin_auth_headers, plan_and_customer):
    plan, customer = plan_and_customer
    client.post(f"/api/v1/plans/{plan['id']}/archive", headers=admin_auth_headers)

    resp = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    )
    assert resp.status_code == 409


def test_activate_pause_resume_cancel_flow(client, auth_headers, plan_and_customer):
    plan, customer = plan_and_customer
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    sub_id = sub["id"]

    activated = client.post(f"/api/v1/subscriptions/{sub_id}/activate", headers=auth_headers)
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"

    paused = client.post(f"/api/v1/subscriptions/{sub_id}/pause", headers=auth_headers)
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert paused.json()["paused_at"] is not None

    resumed = client.post(f"/api/v1/subscriptions/{sub_id}/resume", headers=auth_headers)
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "active"

    cancelled = client.post(
        f"/api/v1/subscriptions/{sub_id}/cancel",
        headers=auth_headers,
        json={"cancellation_type": "immediate", "reason": "customer request"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancelled_at"] is not None


def test_get_by_id_for_update_returns_the_correct_subscription(client, auth_headers, plan_and_customer, db_session):
    """
    Correctness check for the new locking repository method (added as
    the fix for a confirmed duplicate-refund bug -- see
    test_repeated_immediate_cancel_never_creates_more_than_one_refund
    and the live concurrent-request proof in the engineering notes).
    This test only verifies the method returns the right row; it
    cannot exercise genuine multi-connection concurrency, since this
    suite's client/db_session fixture shares one connection and
    transaction across every request in a test (see conftest.py) --
    a real race requires separate connections, which is why the
    concurrency behavior itself was proven against a live running
    server instead.
    """
    from app.repositories.subscription_repository import SubscriptionRepository

    plan, customer = plan_and_customer
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()

    locked = SubscriptionRepository(db_session).get_by_id_for_update(sub["id"])
    assert locked is not None
    assert str(locked.id) == sub["id"]


def test_repeated_immediate_cancel_never_creates_more_than_one_refund(
    client, admin_auth_headers, auth_headers, plan_and_customer
):
    """
    Confirms the application-level half of the duplicate-refund fix:
    once a subscription is cancelled, CANCELLED is a terminal state
    with no outgoing transitions (see SubscriptionStateMachine), so a
    second cancel attempt is rejected outright and never reaches the
    refund logic a second time -- deterministic and reliable to test,
    unlike the genuine-concurrency half of the fix (see the test
    above for why that part is proven live instead).
    """
    plan, customer = plan_and_customer
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    sub_id = sub["id"]
    client.post(f"/api/v1/subscriptions/{sub_id}/activate", headers=auth_headers)

    invoice_id = client.get(
        "/api/v1/invoices", params={"customer_id": customer["id"]}, headers=auth_headers
    ).json()["items"][0]["id"]
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        client.post("/api/v1/payments/process", headers=auth_headers, json={"invoice_id": invoice_id})

    first = client.post(
        f"/api/v1/subscriptions/{sub_id}/cancel",
        headers=auth_headers,
        json={"cancellation_type": "immediate", "reason": "first attempt"},
    )
    assert first.status_code == 200

    # Simulates a retried/duplicated request after the subscription is
    # already cancelled.
    second = client.post(
        f"/api/v1/subscriptions/{sub_id}/cancel",
        headers=auth_headers,
        json={"cancellation_type": "immediate", "reason": "duplicate attempt"},
    )
    assert second.status_code in (400, 409)

    refunds = client.get(
        "/api/v1/refunds", params={"customer_id": customer["id"]}, headers=admin_auth_headers
    ).json()
    matching = [r for r in refunds["items"] if r["invoice_id"] == invoice_id]
    assert len(matching) == 1


def test_invalid_transition_returns_409(client, auth_headers, plan_and_customer):
    plan, customer = plan_and_customer
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    sub_id = sub["id"]

    # trial -> past_due is not a valid direct transition; there is no
    # public endpoint for it, so we validate via cancel then re-activate.
    client.post(
        f"/api/v1/subscriptions/{sub_id}/cancel",
        headers=auth_headers,
        json={"cancellation_type": "immediate"},
    )
    resp = client.post(f"/api/v1/subscriptions/{sub_id}/activate", headers=auth_headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "invalid_state_transition"


def test_end_of_cycle_cancellation_sets_flag_without_immediate_cancel(
    client, auth_headers, plan_and_customer
):
    plan, customer = plan_and_customer
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    sub_id = sub["id"]
    client.post(f"/api/v1/subscriptions/{sub_id}/activate", headers=auth_headers)

    resp = client.post(
        f"/api/v1/subscriptions/{sub_id}/cancel",
        headers=auth_headers,
        json={"cancellation_type": "end_of_cycle", "reason": "downgrade path"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Status remains active; cancellation is deferred to the billing scheduler
    assert body["status"] == "active"
    assert body["cancel_at_period_end"] is True
    assert body["cancellation_type"] == "end_of_cycle"


def test_undo_scheduled_cancellation(client, auth_headers, plan_and_customer):
    """
    QA fix (Finding #8): a not-yet-executed end-of-cycle cancellation
    can be reversed. Subscription status is untouched throughout --
    only the flag/type are reset.
    """
    plan, customer = plan_and_customer
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    sub_id = sub["id"]
    client.post(f"/api/v1/subscriptions/{sub_id}/activate", headers=auth_headers)
    client.post(
        f"/api/v1/subscriptions/{sub_id}/cancel",
        headers=auth_headers,
        json={"cancellation_type": "end_of_cycle"},
    )

    resp = client.post(f"/api/v1/subscriptions/{sub_id}/undo-cancellation", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "active"
    assert body["cancel_at_period_end"] is False
    assert body["cancellation_type"] is None

    # The subscription is fully back to normal -- a second cancel
    # request is accepted again (proves it isn't stuck in a broken
    # in-between state).
    resp2 = client.post(
        f"/api/v1/subscriptions/{sub_id}/cancel",
        headers=auth_headers,
        json={"cancellation_type": "end_of_cycle"},
    )
    assert resp2.status_code == 200


def test_undo_scheduled_cancellation_requires_one_to_exist(
    client, auth_headers, plan_and_customer
):
    plan, customer = plan_and_customer
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    sub_id = sub["id"]
    client.post(f"/api/v1/subscriptions/{sub_id}/activate", headers=auth_headers)

    # No cancellation was ever requested -- nothing to undo.
    resp = client.post(f"/api/v1/subscriptions/{sub_id}/undo-cancellation", headers=auth_headers)
    assert resp.status_code == 409


def test_undo_scheduled_cancellation_records_audit_event(
    client, auth_headers, plan_and_customer
):
    plan, customer = plan_and_customer
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    sub_id = sub["id"]
    client.post(f"/api/v1/subscriptions/{sub_id}/activate", headers=auth_headers)
    client.post(
        f"/api/v1/subscriptions/{sub_id}/cancel",
        headers=auth_headers,
        json={"cancellation_type": "end_of_cycle"},
    )
    client.post(f"/api/v1/subscriptions/{sub_id}/undo-cancellation", headers=auth_headers)

    resp = client.get(f"/api/v1/audit-logs/subscription/{sub_id}", headers=auth_headers)
    assert resp.status_code == 200
    event_types = [e["event_type"] for e in resp.json()]
    assert "subscription_cancellation_undone" in event_types


def test_change_plan(client, auth_headers, admin_auth_headers, plan_and_customer):
    plan, customer = plan_and_customer
    new_plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": "Upgraded Plan", "price": 99.00, "billing_interval": "monthly"},
    ).json()

    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()

    resp = client.post(
        f"/api/v1/subscriptions/{sub['id']}/change-plan",
        headers=auth_headers,
        json={"new_plan_id": new_plan["id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["plan_id"] == new_plan["id"]


def test_subscription_detail_includes_status_history(client, auth_headers, plan_and_customer):
    plan, customer = plan_and_customer
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=auth_headers)

    detail = client.get(f"/api/v1/subscriptions/{sub['id']}", headers=auth_headers)
    assert detail.status_code == 200
    history = detail.json()["status_history"]
    assert len(history) >= 2
    assert history[0]["to_status"] == "trial"
    assert history[-1]["to_status"] == "active"


def test_subscription_billing_cycles_created(client, auth_headers, plan_and_customer):
    plan, customer = plan_and_customer
    sub = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()

    cycles = client.get(f"/api/v1/subscriptions/{sub['id']}/billing-cycles", headers=auth_headers)
    assert cycles.status_code == 200
    body = cycles.json()
    assert len(body) == 1
    assert body[0]["is_billed"] is False
