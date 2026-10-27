"""
Tests for the Retry Configuration API (Module 3, Phase 1a).

Covers Configuration CRUD only -- no retry execution/scheduler exists
yet, so there is nothing to test there in this phase.
"""
import uuid


def test_create_retry_configuration_admin_only(client, auth_headers, admin_auth_headers):
    resp = client.post(
        "/api/v1/retry/configuration",
        headers=auth_headers,
        json={"retry_attempt": 1, "retry_after_days": 1, "is_active": True},
    )
    assert resp.status_code == 403

    resp = client.post(
        "/api/v1/retry/configuration",
        headers=admin_auth_headers,
        json={"retry_attempt": 1, "retry_after_days": 1, "is_active": True},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["retry_attempt"] == 1
    assert body["retry_after_days"] == 1
    assert body["is_active"] is True
    assert "id" in body


def test_create_retry_configuration_requires_auth(client):
    resp = client.post(
        "/api/v1/retry/configuration",
        json={"retry_attempt": 1, "retry_after_days": 1},
    )
    assert resp.status_code == 401


def test_cannot_create_duplicate_retry_attempt(client, admin_auth_headers):
    client.post(
        "/api/v1/retry/configuration",
        headers=admin_auth_headers,
        json={"retry_attempt": 2, "retry_after_days": 3},
    )
    resp = client.post(
        "/api/v1/retry/configuration",
        headers=admin_auth_headers,
        json={"retry_attempt": 2, "retry_after_days": 5},
    )
    assert resp.status_code == 409


def test_default_retry_schedule_matches_spec_example(client, admin_auth_headers):
    """
    The Module 3 spec's example schedule: attempt 1 after 1 day,
    attempt 2 after 3 days, attempt 3 after 7 days. Not a hardcoded
    default in this system -- confirms an admin can configure exactly
    this schedule via the API.
    """
    schedule = [(1, 1), (2, 3), (3, 7)]
    for attempt, days in schedule:
        resp = client.post(
            "/api/v1/retry/configuration",
            headers=admin_auth_headers,
            json={"retry_attempt": attempt, "retry_after_days": days},
        )
        assert resp.status_code == 201

    resp = client.get("/api/v1/retry/configuration", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    ordered = [(item["retry_attempt"], item["retry_after_days"]) for item in body["items"]]
    assert ordered == schedule  # ordered by attempt number


def test_list_retry_configurations_admin_only(client, auth_headers, admin_auth_headers):
    resp = client.get("/api/v1/retry/configuration", headers=auth_headers)
    assert resp.status_code == 403

    resp = client.get("/api/v1/retry/configuration", headers=admin_auth_headers)
    assert resp.status_code == 200


def test_get_retry_configuration_by_id(client, admin_auth_headers):
    created = client.post(
        "/api/v1/retry/configuration",
        headers=admin_auth_headers,
        json={"retry_attempt": 1, "retry_after_days": 1},
    ).json()

    resp = client.get(f"/api/v1/retry/configuration/{created['id']}", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_retry_configuration_not_found(client, admin_auth_headers):
    resp = client.get(
        f"/api/v1/retry/configuration/{uuid.uuid4()}", headers=admin_auth_headers
    )
    assert resp.status_code == 404


def test_update_retry_configuration(client, admin_auth_headers):
    created = client.post(
        "/api/v1/retry/configuration",
        headers=admin_auth_headers,
        json={"retry_attempt": 1, "retry_after_days": 1},
    ).json()

    resp = client.patch(
        f"/api/v1/retry/configuration/{created['id']}",
        headers=admin_auth_headers,
        json={"retry_after_days": 2},
    )
    assert resp.status_code == 200
    assert resp.json()["retry_after_days"] == 2
    assert resp.json()["retry_attempt"] == 1  # unchanged


def test_deactivate_retry_configuration(client, admin_auth_headers):
    created = client.post(
        "/api/v1/retry/configuration",
        headers=admin_auth_headers,
        json={"retry_attempt": 1, "retry_after_days": 1},
    ).json()

    resp = client.patch(
        f"/api/v1/retry/configuration/{created['id']}",
        headers=admin_auth_headers,
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_update_retry_configuration_admin_only(client, auth_headers, admin_auth_headers):
    created = client.post(
        "/api/v1/retry/configuration",
        headers=admin_auth_headers,
        json={"retry_attempt": 1, "retry_after_days": 1},
    ).json()

    resp = client.patch(
        f"/api/v1/retry/configuration/{created['id']}",
        headers=auth_headers,
        json={"retry_after_days": 9},
    )
    assert resp.status_code == 403


def test_update_retry_configuration_not_found(client, admin_auth_headers):
    resp = client.patch(
        f"/api/v1/retry/configuration/{uuid.uuid4()}",
        headers=admin_auth_headers,
        json={"retry_after_days": 2},
    )
    assert resp.status_code == 404


def test_retry_configuration_audit_events_recorded(client, admin_auth_headers, db_session):
    created = client.post(
        "/api/v1/retry/configuration",
        headers=admin_auth_headers,
        json={"retry_attempt": 1, "retry_after_days": 1},
    ).json()
    client.patch(
        f"/api/v1/retry/configuration/{created['id']}",
        headers=admin_auth_headers,
        json={"retry_after_days": 4},
    )

    resp = client.get(
        f"/api/v1/audit-logs/retry_configuration/{created['id']}", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    event_types = [e["event_type"] for e in resp.json()]
    assert "retry_configuration_created" in event_types
    assert "retry_configuration_updated" in event_types
