"""
Phase 4: tests for GET /invoices/{invoice_id}/pdf -- successful
generation, unauthorized/forbidden/admin access, and invalid invoice
ID. Reuses Phase 1D's ownership enforcement (own invoice, or admin).
"""
import uuid

from unittest.mock import patch

from app.scheduler.billing_scheduler_service import BillingSchedulerService


def _register_and_login(client, email):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "PDF Test User", "password": "SuperSecret123", "country": "US"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _paid_invoice(client, admin_auth_headers, db_session):
    """
    Independent customer with a real paid invoice (via an upgrade),
    so the PDF has real line items, a real payment, and a real due
    date/paid_at to render. Returns (invoice_id, headers).
    """
    email = f"pdf_{uuid.uuid4().hex[:8]}@test.com"
    headers = _register_and_login(client, email)
    plan_a = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"PDF Plan A {uuid.uuid4().hex[:6]}", "price": 20, "billing_interval": "monthly", "trial_period_days": 0},
    ).json()
    plan_b = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"PDF Plan B {uuid.uuid4().hex[:6]}", "price": 45, "billing_interval": "monthly"},
    ).json()
    customer = client.get("/api/v1/customers/me", headers=headers).json()
    sub = client.post(
        "/api/v1/subscriptions",
        headers=headers,
        json={"customer_id": customer["id"], "plan_id": plan_a["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=headers)
    client.post(
        f"/api/v1/subscriptions/{sub['id']}/change-plan",
        headers=headers,
        json={"new_plan_id": plan_b["id"]},
    )
    BillingSchedulerService(db_session).run()
    invoice_id = client.get(
        "/api/v1/invoices", params={"customer_id": customer["id"]}, headers=headers
    ).json()["items"][0]["id"]
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        client.post("/api/v1/payments/process", headers=headers, json={"invoice_id": invoice_id})
    return invoice_id, headers


def test_pdf_generation_succeeds_for_owner(client, admin_auth_headers, db_session):
    invoice_id, headers = _paid_invoice(client, admin_auth_headers, db_session)

    resp = client.get(f"/api/v1/invoices/{invoice_id}/pdf", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    assert len(resp.content) > 500  # a genuine multi-element PDF, not an empty stub
    assert "attachment" in resp.headers["content-disposition"]
    assert ".pdf" in resp.headers["content-disposition"]


def test_pdf_contains_expected_invoice_data(client, admin_auth_headers, db_session):
    """
    Doesn't just check it's *a* PDF -- extracts the actual text to
    confirm the required fields are genuinely present.
    """
    pytest_importorskip = __import__("pytest").importorskip
    pdfminer_high_level = pytest_importorskip("pdfminer.high_level")

    invoice_id, headers = _paid_invoice(client, admin_auth_headers, db_session)
    invoice = client.get(f"/api/v1/invoices/{invoice_id}", headers=headers).json()

    resp = client.get(f"/api/v1/invoices/{invoice_id}/pdf", headers=headers)
    assert resp.status_code == 200

    import io
    text = pdfminer_high_level.extract_text(io.BytesIO(resp.content))

    assert "CineVerse" in text
    assert invoice["invoice_number"] in text
    assert "PDF Test User" in text
    assert "Paid" in text
    assert "Succeeded" in text


def test_pdf_contains_phase_5a_professional_fields(client, admin_auth_headers, db_session):
    """
    Module 3, Phase 5a: company contact details (from settings, not
    hardcoded), customer phone/address/state, billing period,
    subscription ID, renewal date, transaction ID, payment terms, and
    refund policy -- all previously missing from the PDF.
    """
    from app.config.settings import settings

    pytest_importorskip = __import__("pytest").importorskip
    pdfminer_high_level = pytest_importorskip("pdfminer.high_level")
    import io
    import uuid

    email = f"pdf5a_{uuid.uuid4().hex[:8]}@test.com"
    headers = _register_and_login(client, email)
    plan = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"PDF5a Plan {uuid.uuid4().hex[:6]}", "price": 30, "billing_interval": "monthly", "trial_period_days": 0},
    ).json()
    customer = client.get("/api/v1/customers/me", headers=headers).json()
    customer = client.patch(
        f"/api/v1/customers/{customer['id']}",
        headers=headers,
        json={"phone_number": "+1-555-0142", "address": "500 Test Ave", "state": "California"},
    ).json()
    sub = client.post(
        "/api/v1/subscriptions",
        headers=headers,
        json={"customer_id": customer["id"], "plan_id": plan["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=headers)
    # Issue 2 fix: same reasoning as test_analytics_revenue_invoice_api.py
    # and test_customer_insights_api.py -- /activate is now a no-op for
    # a trial_period_days=0 plan, so the scheduler is what invoices it.
    BillingSchedulerService(db_session).run()
    invoice_id = client.get(
        "/api/v1/invoices", params={"customer_id": customer["id"]}, headers=headers
    ).json()["items"][0]["id"]
    with patch("app.services.payment_gateway_service.random.random", return_value=0.0):
        client.post("/api/v1/payments/process", headers=headers, json={"invoice_id": invoice_id})

    resp = client.get(f"/api/v1/invoices/{invoice_id}/pdf", headers=headers)
    assert resp.status_code == 200
    text = pdfminer_high_level.extract_text(io.BytesIO(resp.content))

    # Company details, sourced from settings, not hardcoded.
    assert settings.COMPANY_ADDRESS in text
    assert settings.COMPANY_PHONE in text
    assert settings.COMPANY_EMAIL in text
    assert settings.COMPANY_TAX_ID in text
    # Customer details, already on the model, now actually rendered.
    assert "+1-555-0142" in text
    assert "500 Test Ave" in text
    assert "California" in text
    # New summary fields.
    assert "Billing Period" in text
    assert "Subscription ID" in text
    assert "Renewal Date" in text
    assert "Transaction ID" in text
    # Footer boilerplate, from settings.
    assert "Payment Terms" in text
    assert "Refund Policy" in text
    assert settings.SUPPORT_PHONE in text


def test_pdf_generation_never_makes_a_network_request(client, admin_auth_headers, db_session):
    """
    Phase 5a's core safety requirement: with no local logo file
    configured (the default), PDF generation must never attempt a
    network call for a remote logo -- confirmed by patching
    urlopen/requests to raise if ever invoked, and generation still
    succeeding via the graceful text-header fallback.
    """
    from app.config.settings import settings

    invoice_id, headers = _paid_invoice(client, admin_auth_headers, db_session)
    assert settings.COMPANY_LOGO_PATH == ""  # default: no local file configured

    with patch("urllib.request.urlopen", side_effect=AssertionError("must not make network calls")):
        resp = client.get(f"/api/v1/invoices/{invoice_id}/pdf", headers=headers)
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_pdf_download_requires_auth(client, admin_auth_headers, db_session):
    invoice_id, _headers = _paid_invoice(client, admin_auth_headers, db_session)
    resp = client.get(f"/api/v1/invoices/{invoice_id}/pdf")
    assert resp.status_code == 401


def test_pdf_download_forbidden_for_other_customer(client, admin_auth_headers, db_session):
    invoice_id, _owner_headers = _paid_invoice(client, admin_auth_headers, db_session)
    other_headers = _register_and_login(client, f"pdf_other_{uuid.uuid4().hex[:8]}@test.com")

    resp = client.get(f"/api/v1/invoices/{invoice_id}/pdf", headers=other_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_pdf_download_succeeds_for_admin(client, admin_auth_headers, db_session):
    invoice_id, _owner_headers = _paid_invoice(client, admin_auth_headers, db_session)

    resp = client.get(f"/api/v1/invoices/{invoice_id}/pdf", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_pdf_download_invalid_invoice_id_returns_404(client, admin_auth_headers):
    resp = client.get(
        "/api/v1/invoices/00000000-0000-0000-0000-000000000000/pdf",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_pdf_generation_succeeds_for_unpaid_invoice(client, admin_auth_headers):
    """
    An invoice that's never been paid (no payment record, no paid_at)
    must still render cleanly -- Payment Status / Payment Date should
    gracefully show placeholders, not crash.
    """
    email = f"pdf_unpaid_{uuid.uuid4().hex[:8]}@test.com"
    headers = _register_and_login(client, email)
    plan_a = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"Unpaid Plan A {uuid.uuid4().hex[:6]}", "price": 10, "billing_interval": "monthly", "trial_period_days": 0},
    ).json()
    plan_b = client.post(
        "/api/v1/plans",
        headers=admin_auth_headers,
        json={"name": f"Unpaid Plan B {uuid.uuid4().hex[:6]}", "price": 25, "billing_interval": "monthly"},
    ).json()
    customer = client.get("/api/v1/customers/me", headers=headers).json()
    sub = client.post(
        "/api/v1/subscriptions",
        headers=headers,
        json={"customer_id": customer["id"], "plan_id": plan_a["id"]},
    ).json()
    client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=headers)
    client.post(
        f"/api/v1/subscriptions/{sub['id']}/change-plan",
        headers=headers,
        json={"new_plan_id": plan_b["id"]},
    )
    invoice_id = client.get(
        "/api/v1/invoices", params={"customer_id": customer["id"]}, headers=headers
    ).json()["items"][0]["id"]

    resp = client.get(f"/api/v1/invoices/{invoice_id}/pdf", headers=headers)
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"
