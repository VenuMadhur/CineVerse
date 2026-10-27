"""
Regression tests for:
  * POST /auth/token (OAuth2 Password Flow, used by Swagger's Authorize
    button) issuing a usable access token.
  * The validation exception handler no longer crashing with
    "TypeError: Object of type bytes is not JSON serializable" when a
    validation error's `input` value is raw bytes (as can occur with
    form/multipart bodies).
"""
import uuid

from app.middleware.exception_handlers import _safe_validation_details


def test_oauth2_token_endpoint_issues_valid_token(client):
    email = f"oauth_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "OAuth Tester", "password": "SuperSecret123", "country": "US"},
    )

    # Swagger's Authorize button posts application/x-www-form-urlencoded
    # with `username` + `password` fields, per OAuth2PasswordRequestForm.
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": email, "password": "SuperSecret123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"

    # The issued token must work against a protected endpoint (any
    # authenticated-user endpoint suffices here -- GET /customers/me,
    # not POST /plans, since plan creation became admin-only in Phase 1C
    # and this test's regular user isn't one).
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    protected = client.get(
        "/api/v1/customers/me",
        headers=headers,
    )
    assert protected.status_code == 200


def test_oauth2_token_endpoint_rejects_bad_credentials(client):
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": "nobody@nowhere.com", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_json_login_still_works_after_refactor(client):
    email = f"json_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "JSON Tester", "password": "SuperSecret123", "country": "US"},
    )
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_token_endpoint_missing_field_returns_422_not_500(client):
    resp = client.post("/api/v1/auth/token", data={"username": "someone@test.com"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"


def test_safe_validation_details_handles_raw_bytes_input():
    """
    Directly reproduces the reported crash: a validation error dict
    whose 'input' is bytes (not str) must serialize cleanly instead of
    raising TypeError.
    """
    fake_errors = [
        {
            "type": "string_type",
            "loc": ("body", "password"),
            "msg": "Input should be a valid string",
            "input": b"raw-bytes-value",
        }
    ]
    safe = _safe_validation_details(fake_errors)
    assert safe[0]["input"] == "raw-bytes-value"
    assert isinstance(safe[0]["input"], str)
