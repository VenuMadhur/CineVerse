"""
Pytest fixtures: an isolated test database (transaction-per-test
rollback pattern) and a FastAPI TestClient wired to it.
"""
import os
import uuid

# Force the test database unconditionally.
# If running inside docker (where DATABASE_URL is billing_db), rewrite it to billing_test_db.
# If running on host, default to localhost test db.
if "DATABASE_URL" in os.environ and os.environ["DATABASE_URL"].endswith("/billing_db"):
    os.environ["DATABASE_URL"] = os.environ["DATABASE_URL"].replace("/billing_db", "/billing_test_db")
elif "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "postgresql+psycopg2://billing_user:billing_pass@127.0.0.1:5432/billing_test_db"
os.environ.setdefault("SECRET_KEY", "test-secret-key")
# REDIS_HOST defaults to "redis" (the Docker Compose service hostname);
# the test suite runs directly on the host, not inside that network,
# so it needs to reach Redis via localhost instead -- same reasoning
# as the DATABASE_URL override above.
os.environ.setdefault("REDIS_HOST", "localhost")
# The test suite legitimately makes far more auth requests per minute
# than any real client would (hundreds of register/login calls across
# the full suite); rate limiting is a production/security concern
# tested in its own dedicated test file (test_rate_limiting.py), not
# something that should interfere with the rest of the suite.
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings
from app.core.database import Base, get_db
from app.main import app

engine = create_engine(settings.DATABASE_URL, future=True)

if str(engine.url).endswith("billing_db"):
    raise RuntimeError("CRITICAL SAFETY CHECK FAILED: Pytest is configured to use the production database (billing_db) instead of the test database. Aborting to prevent data loss.")

TestingSessionLocal = sessionmaker(
    bind=engine, 
    autocommit=False, 
    autoflush=False, 
    future=True,
    join_transaction_mode="create_savepoint"
)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    email = f"user_{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Test User", "password": "SuperSecret123", "country": "US"},
    )
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def auth_headers_no_customer(client, db_session):
    """
    Creates a user directly in the database without going through
    /auth/register, which would atomically create a customer.
    Useful for testing independent Customer creation via /api/v1/customers.
    """
    from app.models.user import User
    from app.core.security import hash_password
    
    email = f"user_nocust_{uuid.uuid4().hex[:8]}@test.com"
    user = User(
        email=email, 
        full_name="Test No Customer", 
        hashed_password=hash_password("SuperSecret123")
    )
    db_session.add(user)
    db_session.commit()
    
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_auth_headers(client, db_session):
    """
    A logged-in user with is_superuser=True. There's no API to promote
    a user to admin (by design -- see Phase 1C), so this fixture
    registers a normal user via the API and then flips the flag
    directly in the DB, exactly as a real deployment's one-time admin
    bootstrap would (a manual DB update, not a self-service endpoint).
    """
    from app.models.user import User
    from app.core.security import hash_password

    email = f"admin_{uuid.uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name="Admin User",
        hashed_password=hash_password("SuperSecret123"),
        is_superuser=True
    )
    db_session.add(user)
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def active_subscription_with_invoice(client, auth_headers, admin_auth_headers, db_session):
    """
    Creates a plan (no trial, via an admin token -- plan creation is
    admin-only since Phase 1C), a US customer, an active subscription,
    and an OPEN invoice for its current billing cycle -- the common
    starting point for Module 2 payment/webhook/refund tests.
    """
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": f"Payment Test Plan {uuid.uuid4().hex[:6]}",
            "price": 50.00,
            "billing_interval": "monthly",
            "trial_period_days": 0,
        },
    ).json()
    customer = client.get(
        "/api/v1/customers/me",
        headers=auth_headers,
    ).json()
    subscription = client.post(
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{subscription['id']}/activate", headers=auth_headers)

    from app.models.customer import Customer
    from app.models.plan import Plan
    from app.models.subscription import Subscription
    from app.services.billing_cycle_service import BillingCycleService
    from app.services.invoice_service import InvoiceService

    subscription_obj = db_session.get(Subscription, uuid.UUID(subscription["id"]))
    plan_obj = db_session.get(Plan, uuid.UUID(plan["id"]))
    customer_obj = db_session.get(Customer, uuid.UUID(customer["id"]))
    cycle = BillingCycleService(db_session).get_current_cycle(subscription_obj.id)
    invoice = InvoiceService(db_session).generate_billing_invoice(
        subscription=subscription_obj, plan=plan_obj, customer=customer_obj, cycle=cycle
    )
    db_session.commit()
    db_session.refresh(invoice)

    return {
        "plan": plan,
        "customer": customer,
        "subscription": subscription,
        "invoice_id": str(invoice.id),
        "invoice_total": float(invoice.total_amount),
    }
