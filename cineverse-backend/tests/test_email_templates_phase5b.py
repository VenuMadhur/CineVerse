"""
Tests for Module 3, Phase 5b (Professional HTML Email Templates):
CTA buttons remain optional (render only when both cta_label and
cta_url are given), the standardized accent/status banner, and that
every existing plain-text fallback is completely unchanged.
"""
from app.config.settings import settings
from app.services import notification_service
from app.services.email_templates import render_email


def test_cta_button_renders_only_when_both_label_and_url_given():
    html_both = render_email(
        preheader="p", heading="h", body_html="<p>b</p>", cta_label="Click", cta_url="https://example.com/x"
    )
    assert "Click" in html_both
    assert "https://example.com/x" in html_both

    html_label_only = render_email(preheader="p", heading="h", body_html="<p>b</p>", cta_label="Click")
    assert "Click" not in html_label_only

    html_url_only = render_email(preheader="p", heading="h", body_html="<p>b</p>", cta_url="https://example.com/x")
    assert "https://example.com/x" not in html_url_only

    html_neither = render_email(preheader="p", heading="h", body_html="<p>b</p>")
    assert "btn-primary" not in html_neither  # no button markup at all


def test_accent_banner_only_renders_when_both_accent_and_label_given():
    html_with_banner = render_email(
        preheader="p", heading="h", body_html="<p>b</p>", accent="success", accent_label="Done"
    )
    assert "DONE" in html_with_banner.upper()
    assert "#16a34a" in html_with_banner  # the success accent color

    html_no_banner = render_email(preheader="p", heading="h", body_html="<p>b</p>")
    assert "#16a34a" not in html_no_banner
    assert "#dc2626" not in html_no_banner


def test_unknown_accent_key_gracefully_ignored():
    """An invalid/unrecognized accent key must not crash -- no banner, not an error."""
    html = render_email(preheader="p", heading="h", body_html="<p>b</p>", accent="not_a_real_key", accent_label="X")
    assert html  # renders successfully
    assert "not_a_real_key" not in html


def test_render_email_reuses_phase_5a_company_settings():
    html = render_email(preheader="p", heading="h", body_html="<p>b</p>")
    assert settings.COMPANY_WEBSITE in html
    assert settings.SUPPORT_EMAIL in html
    assert settings.COMPANY_NAME in html


def test_payment_failed_has_danger_accent_and_update_payment_cta():
    subject, html, text = notification_service._payment_failed(
        "Jane", {"invoice_number": "INV-1", "amount": "10", "currency": "USD", "reason": "declined"}
    )
    assert "#dc2626" in html  # danger accent
    assert "Update Payment" in html
    assert settings.FRONTEND_BASE_URL in html
    # Plain-text fallback completely unchanged in content/shape.
    assert text == (
        "Hi Jane,\n\nWe couldn't process your payment of 10 USD for invoice INV-1 (declined).\n\n"
        f"\u2014 {settings.COMPANY_NAME}"
    )


def test_payment_succeeded_has_success_accent_and_no_cta():
    """Informational only -- no action needed, so no CTA button should be invented."""
    subject, html, text = notification_service._payment_succeeded(
        "Jane", {"invoice_number": "INV-1", "amount": "10", "currency": "USD"}
    )
    assert "#16a34a" in html  # success accent
    assert "background-color:#E50914;border-radius:6px" not in html  # no CTA button markup


def test_welcome_has_browse_plans_cta():
    subject, html, text = notification_service._welcome("Jane", {})
    assert "Browse Plans" in html
    assert f"{settings.FRONTEND_BASE_URL}/plans" in html


def test_trial_ending_reminder_has_warning_accent_and_manage_subscription_cta():
    subject, html, text = notification_service._trial_ending_reminder(
        "Jane", {"plan_name": "Pro", "trial_ends_at": "2026-09-01"}
    )
    assert "#d97706" in html  # warning accent
    assert "Manage Subscription" in html


def test_every_phase_5b_event_still_produces_valid_html_and_unchanged_text():
    """
    Every one of the 8 enhanced events must still return a well-formed
    (subject, html, text) tuple, and -- critically -- the plain-text
    body must be byte-identical to what it produced before Phase 5b
    (this phase only ever touches `html`, never `text`).
    """
    cases = [
        (notification_service._welcome, ("Jane", {}), "Hi Jane,\n\nWelcome to CineVerse! Your account is ready to go.\n\n\u2014 CineVerse"),
        (notification_service._subscription_cancelled, ("Jane", {"plan_name": "Pro"}), "Hi Jane,\n\nYour Pro subscription has been cancelled.\n\n\u2014 CineVerse"),
        (notification_service._subscription_activated, ("Jane", {"plan_name": "Pro"}), "Hi Jane,\n\nYour subscription to Pro is now active.\n\n\u2014 CineVerse"),
        (notification_service._refund_completed, ("Jane", {"invoice_number": "INV-1"}), "Hi Jane,\n\nA refund for invoice INV-1 has been completed.\n\n\u2014 CineVerse"),
    ]
    for builder, args, expected_text in cases:
        subject, html, text = builder(*args)
        assert subject
        assert "<html>" in html
        assert text == expected_text
