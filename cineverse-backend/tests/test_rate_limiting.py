"""
Tests for the Redis-backed auth rate limiter (app/core/rate_limiter.py).

Rate limiting is disabled for the rest of the suite (see conftest.py --
the full test suite legitimately makes far more auth requests per
minute than any real client would). These tests explicitly re-enable
it via patch.object, and each test uses its own unique synthetic
client IP (via X-Forwarded-For) so tests never share a Redis counter
with each other or with a prior run.

The real configured limit (RATE_LIMIT_AUTH_MAX_ATTEMPTS=10,
RATE_LIMIT_AUTH_WINDOW_SECONDS=60) is baked into the auth router's
dependencies at import time, so these tests exercise the real default
values rather than a patched-down limit -- patching
settings.RATE_LIMIT_AUTH_MAX_ATTEMPTS after import wouldn't actually
change the already-constructed dependency closures.
"""
import uuid
from unittest.mock import patch

from app.config.settings import settings


def _unique_ip():
    # A syntactically-valid-looking IPv4 address that's unique per
    # test, so each test's rate-limit counter is fully independent.
    return f"203.0.113.{uuid.uuid4().int % 250 + 1}"


def test_login_allows_up_to_the_configured_limit(client):
    ip = _unique_ip()
    with patch.object(settings, "RATE_LIMIT_ENABLED", True):
        for _ in range(settings.RATE_LIMIT_AUTH_MAX_ATTEMPTS):
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@test.com", "password": "wrong"},
                headers={"X-Forwarded-For": ip},
            )
            # Wrong credentials -- 401, not 429 -- confirms the limit
            # hasn't been hit yet for any of the allowed attempts.
            assert resp.status_code == 401


def test_login_blocked_after_exceeding_the_limit(client):
    ip = _unique_ip()
    with patch.object(settings, "RATE_LIMIT_ENABLED", True):
        for _ in range(settings.RATE_LIMIT_AUTH_MAX_ATTEMPTS):
            client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@test.com", "password": "wrong"},
                headers={"X-Forwarded-For": ip},
            )
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "wrong"},
            headers={"X-Forwarded-For": ip},
        )
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["code"] == "rate_limit_exceeded"
        assert "Retry-After" in resp.headers
        assert int(resp.headers["Retry-After"]) > 0


def test_register_and_login_have_independent_rate_limit_scopes(client):
    ip = _unique_ip()
    with patch.object(settings, "RATE_LIMIT_ENABLED", True):
        for _ in range(settings.RATE_LIMIT_AUTH_MAX_ATTEMPTS):
            client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"scopetest_{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "Scope Test",
                    "password": "SuperSecret123", "country": "US",
                },
                headers={"X-Forwarded-For": ip},
            )
        # Register's own limit is now exhausted for this IP...
        exhausted = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"scopetest_{uuid.uuid4().hex[:8]}@test.com",
                "full_name": "Scope Test",
                "password": "SuperSecret123", "country": "US",
            },
            headers={"X-Forwarded-For": ip},
        )
        assert exhausted.status_code == 429

        # ...but login, a different scope, is completely unaffected
        # for the very same IP.
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "wrong"},
            headers={"X-Forwarded-For": ip},
        )
        assert login_resp.status_code == 401


def test_different_clients_have_independent_counters(client):
    ip_a = _unique_ip()
    ip_b = _unique_ip()
    with patch.object(settings, "RATE_LIMIT_ENABLED", True):
        for _ in range(settings.RATE_LIMIT_AUTH_MAX_ATTEMPTS):
            client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@test.com", "password": "wrong"},
                headers={"X-Forwarded-For": ip_a},
            )
        # Client A is now exhausted...
        exhausted = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "wrong"},
            headers={"X-Forwarded-For": ip_a},
        )
        assert exhausted.status_code == 429

        # ...but a different client IP is unaffected.
        other_client = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "wrong"},
            headers={"X-Forwarded-For": ip_b},
        )
        assert other_client.status_code == 401


def test_rate_limiting_disabled_by_setting(client):
    ip = _unique_ip()
    with patch.object(settings, "RATE_LIMIT_ENABLED", False):
        for _ in range(settings.RATE_LIMIT_AUTH_MAX_ATTEMPTS + 5):
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@test.com", "password": "wrong"},
                headers={"X-Forwarded-For": ip},
            )
            assert resp.status_code == 401  # never 429, however many attempts
