"""
Integration tests for Customer Management APIs, including Phase 1C
ownership enforcement: a non-admin user may only view/edit their own
linked Customer; GET /customers (list) is admin-only.
"""
import uuid


def test_create_customer(client, auth_headers_no_customer):
    resp = client.post(
        "/api/v1/customers",
        headers=auth_headers_no_customer,
        json={
            "name": "Globex Corporation",
            "email": "billing@globex.com",
            "country": "us",
            "phone_number": "+1-555-0100",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Globex Corporation"
    assert body["country"] == "US"


def test_duplicate_customer_email_conflicts(client, auth_headers_no_customer):
    payload = {"name": "Dup Co", "email": "dup@company.com", "country": "gb"}
    first = client.post("/api/v1/customers", headers=auth_headers_no_customer, json=payload)
    assert first.status_code == 201
    second = client.post("/api/v1/customers", headers=auth_headers_no_customer, json=payload)
    assert second.status_code == 409


def test_invalid_email_rejected(client, auth_headers_no_customer):
    resp = client.post(
        "/api/v1/customers",
        headers=auth_headers_no_customer,
        json={"name": "Bad Email Co", "email": "not-an-email", "country": "us"},
    )
    assert resp.status_code == 422


def test_get_customer_by_id(client, auth_headers_no_customer):
    """A user fetching their own customer record by ID."""
    created = client.post(
        "/api/v1/customers",
        headers=auth_headers_no_customer,
        json={"name": "Lookup Co", "email": "lookup@company.com", "country": "de"},
    ).json()

    fetched = client.get(f"/api/v1/customers/{created['id']}", headers=auth_headers_no_customer)
    assert fetched.status_code == 200
    assert fetched.json()["email"] == "lookup@company.com"


def test_get_customer_now_requires_auth(client, auth_headers_no_customer):
    """Phase 1C: GET /customers/{id} is no longer publicly accessible."""
    created = client.post(
        "/api/v1/customers",
        headers=auth_headers_no_customer,
        json={"name": "Auth Required Co", "email": "auth_required@company.com", "country": "us"},
    ).json()

    resp = client.get(f"/api/v1/customers/{created['id']}")
    assert resp.status_code == 401


def test_update_customer(client, auth_headers_no_customer):
    created = client.post(
        "/api/v1/customers",
        headers=auth_headers_no_customer,
        json={"name": "Update Co", "email": "update@company.com", "country": "fr"},
    ).json()

    updated = client.patch(
        f"/api/v1/customers/{created['id']}",
        headers=auth_headers_no_customer,
        json={"name": "Updated Co Name"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Co Name"


def test_list_customers_is_admin_only(client, admin_auth_headers):
    client.post(
        "/api/v1/customers",
        headers=admin_auth_headers,
        json={"name": "List Co", "email": "list@company.com", "country": "jp"},
    )
    resp = client.get("/api/v1/customers", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def _create_customer_via_registration(client, name, email):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": name, "password": "SuperSecret123", "country": "US"},
    )


def test_list_customers_search_matches_name(client, admin_auth_headers):
    unique = uuid.uuid4().hex[:8]
    _create_customer_via_registration(client, f"Zephyr {unique}", f"zephyr_{unique}@company.com")
    resp = client.get(f"/api/v1/customers?search=Zephyr%20{unique}", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == f"Zephyr {unique}"


def test_list_customers_search_matches_email_case_insensitively(client, admin_auth_headers):
    unique = uuid.uuid4().hex[:8]
    _create_customer_via_registration(client, "Case Test", f"MixedCase_{unique}@company.com")
    resp = client.get(f"/api/v1/customers?search=mixedcase_{unique}", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_list_customers_search_no_match_returns_empty_not_error(client, admin_auth_headers):
    """
    The confirmed bug this fixes: the old frontend workaround sent
    page_size=200 while searching, which the backend's pagination
    validation (le=100) always rejected with a 422. A genuine search
    with no matches must return an empty, successful result -- never
    an error.
    """
    resp = client.get(
        "/api/v1/customers?search=zzz_definitely_does_not_exist_zzz", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_list_customers_search_respects_page_size_up_to_100(client, admin_auth_headers):
    """
    Directly proves the fix: a search request at the documented
    maximum page_size succeeds (previously the frontend requested 200,
    always exceeding this and always failing).
    """
    resp = client.get(
        "/api/v1/customers?search=a&page=1&page_size=100", headers=admin_auth_headers
    )
    assert resp.status_code == 200

    resp_over_limit = client.get(
        "/api/v1/customers?search=a&page=1&page_size=200", headers=admin_auth_headers
    )
    assert resp_over_limit.status_code == 422


def test_list_customers_without_search_param_is_unchanged(client, admin_auth_headers):
    """Backward compatibility: omitting `search` behaves exactly as before."""
    resp = client.get("/api/v1/customers?page=1&page_size=20", headers=admin_auth_headers)
    assert resp.status_code == 200


def test_list_customers_forbidden_for_regular_customer(client, auth_headers_no_customer):
    """Phase 1C: a regular (non-admin) user cannot list all customers."""
    resp = client.get("/api/v1/customers", headers=auth_headers_no_customer)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_list_customers_requires_auth(client):
    resp = client.get("/api/v1/customers")
    assert resp.status_code == 401


# ---------------------------------------------------------------------
# GET /customers/me (Phase 1B: ownership lookup layer)
# ---------------------------------------------------------------------


def test_get_my_customer_returns_404_when_none_linked(client, auth_headers_no_customer):
    """A freshly registered user with no customer created yet."""
    resp = client.get("/api/v1/customers/me", headers=auth_headers_no_customer)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_get_my_customer_returns_linked_customer(client, auth_headers_no_customer):
    created = client.post(
        "/api/v1/customers",
        headers=auth_headers_no_customer,
        json={"name": "Me Co", "email": "me_endpoint@company.com", "country": "US"},
    ).json()

    resp = client.get("/api/v1/customers/me", headers=auth_headers_no_customer)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["email"] == "me_endpoint@company.com"


def test_get_my_customer_requires_auth(client):
    resp = client.get("/api/v1/customers/me")
    assert resp.status_code == 401


def test_get_my_customer_is_scoped_to_the_caller(client, auth_headers_no_customer):
    """One user's /customers/me must never return another user's customer."""
    client.post(
        "/api/v1/customers",
        headers=auth_headers_no_customer,
        json={"name": "Owner Co", "email": "owner_scope@company.com", "country": "US"},
    )

    other_email = f"other_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": other_email, "full_name": "Other User", "password": "SuperSecret123", "country": "US"},
    )
    other_token = client.post(
        "/api/v1/auth/login", json={"email": other_email, "password": "SuperSecret123"}
    ).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # The second user has a customer created automatically via registration.
    # It should return their own customer, NOT the first user's customer.
    resp = client.get("/api/v1/customers/me", headers=other_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == other_email


def test_creating_a_second_customer_for_the_same_user_conflicts(client, auth_headers_no_customer):
    client.post(
        "/api/v1/customers",
        headers=auth_headers_no_customer,
        json={"name": "First Co", "email": "first_dup@company.com", "country": "US"},
    )
    second = client.post(
        "/api/v1/customers",
        headers=auth_headers_no_customer,
        json={"name": "Second Co", "email": "second_dup@company.com", "country": "US"},
    )
    assert second.status_code == 409


# ---------------------------------------------------------------------
# Ownership enforcement (Phase 1C)
# ---------------------------------------------------------------------


def _register_and_login(client, email):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Second User", "password": "SuperSecret123", "country": "US"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_cannot_view_another_users_customer_by_id(client, auth_headers_no_customer):
    owner_customer = client.post(
        "/api/v1/customers",
        headers=auth_headers_no_customer,
        json={"name": "Owner Only Co", "email": "owner_only@company.com", "country": "US"},
    ).json()

    other_headers = _register_and_login(client, f"other_view_{uuid.uuid4().hex[:8]}@test.com")

    resp = client.get(f"/api/v1/customers/{owner_customer['id']}", headers=other_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_cannot_update_another_users_customer(client, auth_headers_no_customer):
    owner_customer = client.post(
        "/api/v1/customers",
        headers=auth_headers_no_customer,
        json={"name": "Owner Update Co", "email": "owner_update@company.com", "country": "US"},
    ).json()

    other_headers = _register_and_login(client, f"other_update_{uuid.uuid4().hex[:8]}@test.com")

    resp = client.patch(
        f"/api/v1/customers/{owner_customer['id']}",
        headers=other_headers,
        json={"name": "Hijacked Name"},
    )
    assert resp.status_code == 403

    # Confirm the record was genuinely untouched.
    check = client.get(f"/api/v1/customers/{owner_customer['id']}", headers=auth_headers_no_customer)
    assert check.json()["name"] == "Owner Update Co"


def test_admin_can_view_any_customer(client, auth_headers_no_customer, admin_auth_headers):
    owner_customer = client.post(
        "/api/v1/customers",
        headers=auth_headers_no_customer,
        json={"name": "Admin View Co", "email": "admin_view@company.com", "country": "US"},
    ).json()

    resp = client.get(f"/api/v1/customers/{owner_customer['id']}", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == owner_customer["id"]


def test_admin_can_update_any_customer(client, auth_headers_no_customer, admin_auth_headers):
    owner_customer = client.post(
        "/api/v1/customers",
        headers=auth_headers_no_customer,
        json={"name": "Admin Update Co", "email": "admin_update@company.com", "country": "US"},
    ).json()

    resp = client.patch(
        f"/api/v1/customers/{owner_customer['id']}",
        headers=admin_auth_headers,
        json={"name": "Updated By Admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated By Admin"
