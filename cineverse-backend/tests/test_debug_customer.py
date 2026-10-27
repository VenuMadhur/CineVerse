import uuid
from fastapi.testclient import TestClient

def test_debug_customer_creation(client: TestClient):
    email = f"user_debug_{uuid.uuid4().hex[:8]}@test.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Test User", "password": "SuperSecret123", "country": "US"},
    )
    print("Reg Status:", reg.status_code)
    print("Reg JSON:", reg.json())
    
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    )
    print("Login Status:", login.status_code)
    print("Login JSON:", login.json())
    
    token = login.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    cust = client.get("/api/v1/customers/me", headers=headers)
    print("Cust Status:", cust.status_code)
    print("Cust JSON:", cust.json())
    
    assert cust.status_code == 200, f"Customer fetch failed: {cust.json()}"
