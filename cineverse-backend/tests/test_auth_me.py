"""
Tests for GET /auth/me (Phase 1C) -- returns the authenticated user's
own account details, including is_superuser status, which the
frontend uses to decide whether to show admin-only UI.
"""
import uuid


def test_get_me_returns_current_user(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
    assert "email" in body
    assert body["is_active"] is True
    assert body["is_superuser"] is False


def test_get_me_reflects_superuser_status(client, admin_auth_headers):
    resp = client.get("/api/v1/auth/me", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_superuser"] is True


def test_get_me_requires_auth(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_get_me_matches_the_registered_email(client):
    email = f"me_check_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Me Check", "password": "SuperSecret123", "country": "US"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]

    resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == email
    assert resp.json()["full_name"] == "Me Check"


def test_get_me_rejects_invalid_token(client):
    resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401
