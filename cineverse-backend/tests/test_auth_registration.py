import uuid
from unittest.mock import patch
import pytest

from sqlalchemy import select

from app.models.customer import Customer
from app.models.user import User


def test_successful_registration(client, db_session):
    email = f"user_{uuid.uuid4().hex[:8]}@test.com"
    payload = {
        "email": email,
        "full_name": "Atomic User",
        "password": "SuperSecret123",
        "country": "US"
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201

    # Verify both User and Customer exist
    user = db_session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    assert user is not None
    assert user.full_name == "Atomic User"

    customer = db_session.execute(select(Customer).where(Customer.email == email)).scalar_one_or_none()
    assert customer is not None
    assert customer.name == "Atomic User"
    assert customer.country == "US"
    assert customer.user_id == user.id


def test_customer_failure_rollback(client, db_session):
    email = f"fail_{uuid.uuid4().hex[:8]}@test.com"
    payload = {
        "email": email,
        "full_name": "Fail User",
        "password": "SuperSecret123",
        "country": "US"
    }
    
    # Mock CustomerService._create_customer_record to raise an Exception
    with patch("app.services.customer_service.CustomerService._create_customer_record", side_effect=Exception("Intentional failure")):
        with pytest.raises(Exception, match="Intentional failure"):
            client.post("/api/v1/auth/register", json=payload)

    # Verify atomic rollback: neither User nor Customer should exist
    user = db_session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    assert user is None, "User should have been rolled back"

    customer = db_session.execute(select(Customer).where(Customer.email == email)).scalar_one_or_none()
    assert customer is None, "Customer should not exist"


def test_duplicate_registration(client):
    email = f"dup_{uuid.uuid4().hex[:8]}@test.com"
    payload = {
        "email": email,
        "full_name": "Dup User",
        "password": "SuperSecret123",
        "country": "CA"
    }
    
    resp1 = client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409
    assert "already exists" in resp2.text


def test_authentication_compatibility(client):
    email = f"auth_{uuid.uuid4().hex[:8]}@test.com"
    payload = {
        "email": email,
        "full_name": "Auth User",
        "password": "Password123!",
        "country": "GB"
    }
    
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()
