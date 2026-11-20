
"""
Pytest fixtures: isolated test database and FastAPI TestClient.
"""

import os
import uuid

from sqlalchemy.engine import make_url

# --------------------------------------------------
# 1. Test Database Configuration
# --------------------------------------------------

# Always use a dedicated local test database.
# Never inherit the production/Neon DATABASE_URL.

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://billing_user:billing_pass@db:5432/billing_test_db",
)

# Validate database name before importing application modules.
parsed_url = make_url(TEST_DATABASE_URL)

if parsed_url.database != "billing_test_db":
    raise RuntimeError(
        "Unsafe test database configuration. "
        "The database name must be billing_test_db."
    )

# Only allow local Docker or localhost database connections.
if parsed_url.host not in ("db", "localhost", "127.0.0.1"):
    raise RuntimeError(
        "Unsafe test database host. Tests must use a local database."
    )

# Override environment BEFORE importing application settings.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key")

# Redis configuration for tests.
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ["REDIS_URL"] = ""

# Rate limiting is tested separately.
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["SMTP_HOST"] = ""
os.environ["SUPPORT_EMAIL"] = "support@cineverse.example.com"

# --------------------------------------------------
# 2. Imports
# --------------------------------------------------

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings
from app.core.database import Base, get_db
from app.main import app


# --------------------------------------------------
# 3. Create Test Database Engine
# --------------------------------------------------

engine = create_engine(
    settings.DATABASE_URL,
    future=True,
)

# Final safety checks on the actual SQLAlchemy engine.
if engine.url.database != "billing_test_db":
    raise RuntimeError(
        "CRITICAL: Pytest is not connected to billing_test_db."
    )

if engine.url.host not in ("db", "localhost", "127.0.0.1"):
    raise RuntimeError(
        "CRITICAL: Pytest is connected to an unsafe database host."
    )


# --------------------------------------------------
# 4. Test Session Factory
# --------------------------------------------------

TestingSessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
    join_transaction_mode="create_savepoint",
)


# --------------------------------------------------
# 5. Database Setup Fixture
# --------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """
    Create a clean database before the test session
    and remove test tables after the session.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)


# --------------------------------------------------
# 6. Database Session Fixture
# --------------------------------------------------

@pytest.fixture()
def db_session():
    """
    Each test gets its own transaction.
    Changes are rolled back after the test.
    """
    connection = engine.connect()
    transaction = connection.begin()

    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# --------------------------------------------------
# 7. FastAPI Test Client Fixture
# --------------------------------------------------

@pytest.fixture()
def client(db_session):
    """
    Override the application's database dependency
    so API requests use the test database session.
    """

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# --------------------------------------------------
# 8. Authentication Fixture
# --------------------------------------------------

@pytest.fixture()
def auth_headers(client):
    """
    Register and log in a normal test user.
    Return the authentication headers.
    """

    email = f"user_{uuid.uuid4().hex[:8]}@test.com"

    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Test User",
            "password": "SuperSecret123",
            "country": "US",
        },
    )

    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "SuperSecret123",
        },
    )

    token = resp.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}"
    }


# --------------------------------------------------
# 9. Authentication Without Customer Fixture
# --------------------------------------------------

@pytest.fixture()
def auth_headers_no_customer(client, db_session):
    """
    Create a user directly in the database without
    automatically creating a customer.
    """

    from app.models.user import User
    from app.core.security import hash_password

    email = f"user_nocust_{uuid.uuid4().hex[:8]}@test.com"

    user = User(
        email=email,
        full_name="Test No Customer",
        hashed_password=hash_password("SuperSecret123"),
    )

    db_session.add(user)
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "SuperSecret123",
        },
    )

    token = resp.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}"
    }


# --------------------------------------------------
# 10. Admin Authentication Fixture
# --------------------------------------------------

@pytest.fixture()
def admin_auth_headers(client, db_session):
    """
    Create an admin user directly in the database
    and return the authentication headers.
    """

    from app.models.user import User
    from app.core.security import hash_password

    email = f"admin_{uuid.uuid4().hex[:8]}@test.com"

    user = User(
        email=email,
        full_name="Admin User",
        hashed_password=hash_password("SuperSecret123"),
        is_superuser=True,
    )

    db_session.add(user)
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "SuperSecret123",
        },
    )

    token = resp.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}"
    }


# --------------------------------------------------
# 11. Active Subscription With Invoice Fixture
# --------------------------------------------------

@pytest.fixture()
def active_subscription_with_invoice(
    client,
    auth_headers,
    admin_auth_headers,
    db_session,
):
    """
    Create a plan, customer, active subscription,
    billing cycle and invoice for payment tests.
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
        json={
            "customer_id": customer["id"],
            "plan_id": plan["id"],
        },
    ).json()

    client.post(
        f"/api/v1/subscriptions/{subscription['id']}/activate",
        headers=auth_headers,
    )

    from app.models.customer import Customer
    from app.models.plan import Plan
    from app.models.subscription import Subscription

    from app.services.billing_cycle_service import BillingCycleService
    from app.services.invoice_service import InvoiceService

    subscription_obj = db_session.get(
        Subscription,
        uuid.UUID(subscription["id"]),
    )

    plan_obj = db_session.get(
        Plan,
        uuid.UUID(plan["id"]),
    )

    customer_obj = db_session.get(
        Customer,
        uuid.UUID(customer["id"]),
    )

    cycle = BillingCycleService(
        db_session
    ).get_current_cycle(subscription_obj.id)

    invoice = InvoiceService(
        db_session
    ).generate_billing_invoice(
        subscription=subscription_obj,
        plan=plan_obj,
        customer=customer_obj,
        cycle=cycle,
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
