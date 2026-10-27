import uuid
import sys
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import engine, Base

Base.metadata.create_all(bind=engine)
client = TestClient(app)

def _create_plan(client, admin_auth_headers, price=10.0, name=None):
    return client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={
            "name": name or f"Analytics Plan {uuid.uuid4().hex[:8]}",
            "price": price,
            "billing_interval": "monthly",
            "trial_period_days": 0,
        },
    ).json()

def _create_customer(client, auth_headers):
    return client.get(
        "/api/v1/customers/me",
        headers=auth_headers,
    ).json()

# Admin Auth
admin_email = f"admin_{uuid.uuid4().hex[:8]}@test.com"
client.post("/api/v1/auth/register", json={"email": admin_email, "full_name": "Admin", "password": "SuperSecret123", "country": "US"})
from app.core.database import SessionLocal
from app.models.user import User
with SessionLocal() as db:
    user = db.query(User).filter(User.email == admin_email).first()
    user.is_superuser = True
    db.commit()
admin_login = client.post("/api/v1/auth/login", json={"email": admin_email, "password": "SuperSecret123"}).json()
admin_headers = {"Authorization": f"Bearer {admin_login['access_token']}"}

# User Auth
user_email = f"user_{uuid.uuid4().hex[:8]}@test.com"
client.post("/api/v1/auth/register", json={"email": user_email, "full_name": "User", "password": "SuperSecret123", "country": "US"})
user_login = client.post("/api/v1/auth/login", json={"email": user_email, "password": "SuperSecret123"}).json()
user_headers = {"Authorization": f"Bearer {user_login['access_token']}"}

plan = _create_plan(client, admin_headers, name=f"Solo Plan {uuid.uuid4().hex[:8]}")
print("Plan:", plan)

customer = _create_customer(client, user_headers)
print("Customer:", customer)

sub_resp = client.post(
    "/api/v1/subscriptions",
    headers=user_headers,
    json={"customer_id": customer.get("id"), "plan_id": plan.get("id")},
)
print("Sub Status:", sub_resp.status_code)
print("Sub Body:", sub_resp.json())

resp = client.get("/api/v1/analytics/subscribers-by-plan", headers=admin_headers)
print("Analytics Status:", resp.status_code)
try:
    row = next(r for r in resp.json() if r.get("plan_id") == plan.get("id"))
    print("Row:", row)
    assert row["subscriber_count"] == 1
    assert row["plan_name"] == plan["name"]
    print("SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()
