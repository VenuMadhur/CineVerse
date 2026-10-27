"""
Email Notifications (Module 2 + Phase 6B).

Module 2 originally required notifications for Payment Successful,
Payment Failed, and Refund Successful. Phase 6B extends this to the
rest of the customer lifecycle (welcome, profile updates, subscription
started/activated/paused/resumed/cancelled, plan upgrade/downgrade,
invoice generated) using the same dispatch mechanism, and upgrades
every email (including the original three) to a proper HTML template
with a plain-text fallback.

If `settings.SMTP_HOST` is unset (the default), notifications are
logged instead of sent over real SMTP -- so this works out of the box
for local/dev/demo use without requiring a mail provider. Point
SMTP_HOST/USERNAME/PASSWORD at any provider's SMTP relay (SendGrid,
Amazon SES, Resend, etc. all expose one) to send real email -- no
provider-specific SDK integration needed.
"""
import smtplib
import uuid
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from sqlalchemy.orm import Session

from app.config.logging_config import get_logger
from app.config.settings import settings
from app.repositories.customer_repository import CustomerRepository
from app.services.email_templates import detail_table, render_email

logger = get_logger(__name__)

NotificationEvent = str


class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.customer_repository = CustomerRepository(db)

    def dispatch(
        self,
        event_type: NotificationEvent,
        customer_id: uuid.UUID,
        extra: Optional[dict] = None,
    ) -> None:
        """
        `extra` carries whatever event-specific values the calling
        service already has in hand (invoice_number, amount, plan
        names, etc.) -- this method never re-queries Invoice/
        Subscription/Plan itself, only Customer (needed for every
        email's name + destination address). Keeps this service from
        needing to know the internals of every other domain.
        """
        if not settings.NOTIFICATIONS_ENABLED:
            return

        customer = self.customer_repository.get_by_id(customer_id)
        if customer is None:
            logger.warning(
                "Notification skipped: customer not found (event=%s, customer_id=%s)",
                event_type, customer_id,
            )
            return

        subject, html_body, text_body = self._build_message(event_type, customer, extra or {})
        self._send(customer.email, subject, html_body, text_body)

    def send_invoice_attachment(self, invoice, pdf_bytes: bytes) -> None:
        """
        Phase 6C "Email Invoice": a separate method from dispatch()
        rather than a 13th entry in _EVENT_BUILDERS, since this one
        carries a binary PDF attachment, not just string/number
        `extra` values -- the generic dispatch() dict interface isn't
        a good fit for that. Reuses the same render_email shell and
        the same customer lookup + NOTIFICATIONS_ENABLED / delivery-
        failure-never-breaks-the-caller guarantees as every other
        notification.
        """
        if not settings.NOTIFICATIONS_ENABLED:
            return

        customer = self.customer_repository.get_by_id(invoice.customer_id)
        if customer is None:
            logger.warning(
                "Invoice email skipped: customer not found (invoice_id=%s)", invoice.id
            )
            return

        subject = f"Your invoice {invoice.invoice_number}"
        rows = [
            ("Invoice Number", invoice.invoice_number),
            ("Amount", f"{invoice.total_amount} {invoice.currency}"),
            ("Status", invoice.status.value.replace("_", " ").title()),
        ]
        body_html = (
            f"<p>Hi {customer.name},</p>"
            f"<p>Your invoice <b>{invoice.invoice_number}</b> is attached to this email as a PDF.</p>"
            f"{detail_table(rows)}"
        )
        html = render_email(preheader="Your invoice is attached", heading="Invoice", body_html=body_html)
        text = (
            f"Hi {customer.name},\n\nYour invoice {invoice.invoice_number} "
            f"({invoice.total_amount} {invoice.currency}) is attached as a PDF.\n\n"
            f"\u2014 {settings.COMPANY_NAME}"
        )
        self._send(
            customer.email,
            subject,
            html,
            text,
            attachment=(f"{invoice.invoice_number}.pdf", pdf_bytes, "application/pdf"),
        )

    # ------------------------------------------------------------------
    # Message templates
    # ------------------------------------------------------------------
    def _build_message(self, event_type: str, customer, extra: dict) -> tuple[str, str, str]:
        name = customer.name
        builder = _EVENT_BUILDERS.get(event_type, _fallback)
        return builder(name, extra)

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------
    def _send(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
        attachment: Optional[tuple[str, bytes, str]] = None,
    ) -> None:
        """
        `attachment`, if given, is (filename, bytes, mime_type) -- used
        only by send_invoice_attachment() above.
        """
        if not settings.SMTP_HOST:
            logger.info(
                "Notification (simulated, no SMTP_HOST configured) to=%s subject=%r%s\n%s",
                to_email, subject,
                f" [attachment: {attachment[0]}, {len(attachment[1])} bytes]" if attachment else "",
                text_body,
            )
            return

        alternative = MIMEMultipart("alternative")
        alternative.attach(MIMEText(text_body, "plain"))
        alternative.attach(MIMEText(html_body, "html"))

        if attachment:
            message = MIMEMultipart("mixed")
            message.attach(alternative)
            filename, file_bytes, mime_type = attachment
            maintype, subtype = mime_type.split("/", 1)
            part = MIMEApplication(file_bytes, _subtype=subtype)
            part.add_header("Content-Disposition", "attachment", filename=filename)
            message.attach(part)
        else:
            message = alternative

        message["Subject"] = subject
        message["From"] = settings.NOTIFICATION_FROM_EMAIL
        message["To"] = to_email

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.sendmail(settings.NOTIFICATION_FROM_EMAIL, [to_email], message.as_string())
            logger.info("Notification sent to=%s subject=%r", to_email, subject)
        except Exception:
            # Notification delivery must never break billing/subscription
            # processing -- log and move on, same philosophy as the
            # webhook sender's HTTP delivery failures.
            logger.exception("Failed to send notification email to=%s", to_email)


# ----------------------------------------------------------------------
# Per-event message builders: each returns (subject, html_body, text_body)
# ----------------------------------------------------------------------


def _welcome(name: str, extra: dict) -> tuple[str, str, str]:
    subject = f"Welcome to {settings.COMPANY_NAME}!"
    body_html = (
        f"<p>Hi {name},</p>"
        f"<p>Welcome aboard! Your account is ready to go. Explore our plans "
        f"whenever you're ready to start streaming.</p>"
    )
    html = render_email(
        preheader="Welcome!",
        heading="Welcome to " + settings.COMPANY_NAME,
        body_html=body_html,
        accent="success",
        accent_label="Account Created",
        cta_label="Browse Plans",
        cta_url=f"{settings.FRONTEND_BASE_URL}/plans",
    )
    text = f"Hi {name},\n\nWelcome to {settings.COMPANY_NAME}! Your account is ready to go.\n\n\u2014 {settings.COMPANY_NAME}"
    return subject, html, text


def _profile_updated(name: str, extra: dict) -> tuple[str, str, str]:
    subject = "Your profile was updated"
    body_html = f"<p>Hi {name},</p><p>Your profile details were just updated. If this wasn't you, please contact support immediately.</p>"
    html = render_email(preheader="Profile updated", heading="Profile Updated", body_html=body_html)
    text = f"Hi {name},\n\nYour profile details were just updated. If this wasn't you, please contact support immediately.\n\n\u2014 {settings.COMPANY_NAME}"
    return subject, html, text


def _subscription_started(name: str, extra: dict) -> tuple[str, str, str]:
    plan_name = extra.get("plan_name", "your plan")
    trial_ends_at = extra.get("trial_ends_at")
    subject = f"Your {plan_name} trial has started"
    rows = [("Plan", plan_name)]
    if trial_ends_at:
        rows.append(("Trial Ends", trial_ends_at))
    body_html = f"<p>Hi {name},</p><p>Your subscription to <b>{plan_name}</b> has started, and your free trial is active.</p>{detail_table(rows)}"
    html = render_email(preheader="Trial started", heading="Trial Started", body_html=body_html)
    text = f"Hi {name},\n\nYour subscription to {plan_name} has started. Trial ends: {trial_ends_at or 'N/A'}\n\n\u2014 {settings.COMPANY_NAME}"
    return subject, html, text


def _subscription_activated(name: str, extra: dict) -> tuple[str, str, str]:
    plan_name = extra.get("plan_name", "your plan")
    subject = f"Your {plan_name} subscription is now active"
    body_html = f"<p>Hi {name},</p><p>Your subscription to <b>{plan_name}</b> is now active. Thanks for being a customer!</p>"
    html = render_email(
        preheader="Subscription active",
        heading="Subscription Activated",
        body_html=body_html,
        accent="success",
        accent_label="Active",
        cta_label="View Subscription",
        cta_url=f"{settings.FRONTEND_BASE_URL}/subscriptions",
    )
    text = f"Hi {name},\n\nYour subscription to {plan_name} is now active.\n\n\u2014 {settings.COMPANY_NAME}"
    return subject, html, text


def _subscription_paused(name: str, extra: dict) -> tuple[str, str, str]:
    plan_name = extra.get("plan_name", "your plan")
    subject = "Your subscription has been paused"
    body_html = f"<p>Hi {name},</p><p>Your <b>{plan_name}</b> subscription has been paused. Resume anytime to keep watching.</p>"
    html = render_email(preheader="Subscription paused", heading="Subscription Paused", body_html=body_html)
    text = f"Hi {name},\n\nYour {plan_name} subscription has been paused.\n\n\u2014 {settings.COMPANY_NAME}"
    return subject, html, text


def _subscription_resumed(name: str, extra: dict) -> tuple[str, str, str]:
    plan_name = extra.get("plan_name", "your plan")
    subject = "Your subscription has been resumed"
    body_html = f"<p>Hi {name},</p><p>Your <b>{plan_name}</b> subscription is active again. Welcome back!</p>"
    html = render_email(preheader="Subscription resumed", heading="Subscription Resumed", body_html=body_html)
    text = f"Hi {name},\n\nYour {plan_name} subscription has been resumed.\n\n\u2014 {settings.COMPANY_NAME}"
    return subject, html, text


def _subscription_cancelled(name: str, extra: dict) -> tuple[str, str, str]:
    plan_name = extra.get("plan_name", "your plan")
    subject = "Your subscription has been cancelled"
    body_html = (
        f"<p>Hi {name},</p>"
        f"<p>Your <b>{plan_name}</b> subscription has been cancelled. We're sorry to see you go. "
        f"You're welcome back anytime.</p>"
    )
    html = render_email(
        preheader="Subscription cancelled",
        heading="Subscription Cancelled",
        body_html=body_html,
        accent="danger",
        accent_label="Cancelled",
        cta_label="Browse Plans",
        cta_url=f"{settings.FRONTEND_BASE_URL}/plans",
    )
    text = f"Hi {name},\n\nYour {plan_name} subscription has been cancelled.\n\n\u2014 {settings.COMPANY_NAME}"
    return subject, html, text


def _plan_changed(name: str, extra: dict) -> tuple[str, str, str]:
    direction = extra.get("direction", "changed")  # "upgraded" or "downgraded"
    old_plan = extra.get("old_plan_name", "your previous plan")
    new_plan = extra.get("new_plan_name", "your new plan")
    subject = f"Your plan was {direction}"
    rows = [("Previous Plan", old_plan), ("New Plan", new_plan)]
    body_html = f"<p>Hi {name},</p><p>Your subscription was {direction} from <b>{old_plan}</b> to <b>{new_plan}</b>.</p>{detail_table(rows)}"
    html = render_email(preheader=f"Plan {direction}", heading=f"Plan {direction.title()}", body_html=body_html)
    text = f"Hi {name},\n\nYour plan was {direction} from {old_plan} to {new_plan}.\n\n\u2014 {settings.COMPANY_NAME}"
    return subject, html, text


def _invoice_generated(name: str, extra: dict) -> tuple[str, str, str]:
    invoice_number = extra.get("invoice_number", "")
    amount = extra.get("amount", "")
    currency = extra.get("currency", "")
    due_date = extra.get("due_date", "")
    subject = f"New invoice {invoice_number}"
    rows = [("Invoice Number", invoice_number), ("Amount", f"{amount} {currency}".strip())]
    if due_date:
        rows.append(("Due Date", due_date))
    body_html = f"<p>Hi {name},</p><p>A new invoice has been generated for your subscription.</p>{detail_table(rows)}"
    html = render_email(
        preheader="New invoice",
        heading="Invoice Generated",
        body_html=body_html,
        accent="info",
        accent_label="New Invoice",
        cta_label="View Invoice",
        cta_url=f"{settings.FRONTEND_BASE_URL}/invoices",
    )
    text = f"Hi {name},\n\nA new invoice ({invoice_number}) for {amount} {currency} has been generated. Due: {due_date}\n\n\u2014 {settings.COMPANY_NAME}"
    return subject, html, text


def _payment_succeeded(name: str, extra: dict) -> tuple[str, str, str]:
    invoice_number = extra.get("invoice_number", "")
    amount = extra.get("amount", "")
    currency = extra.get("currency", "")
    transaction_id = extra.get("transaction_id", "")
    subject = f"Payment received for invoice {invoice_number}"
    rows = [("Invoice Number", invoice_number), ("Amount", f"{amount} {currency}".strip())]
    if transaction_id:
        rows.append(("Transaction ID", transaction_id))
    body_html = f"<p>Hi {name},</p><p>We've received your payment for invoice <b>{invoice_number}</b>. Thank you!</p>{detail_table(rows)}"
    html = render_email(
        preheader="Payment received",
        heading="Payment Successful",
        body_html=body_html,
        accent="success",
        accent_label="Payment Received",
    )
    text = f"Hi {name},\n\nWe've received your payment of {amount} {currency} for invoice {invoice_number}. Thank you!\n\n\u2014 {settings.COMPANY_NAME}"
    return subject, html, text


def _payment_failed(name: str, extra: dict) -> tuple[str, str, str]:
    invoice_number = extra.get("invoice_number", "")
    amount = extra.get("amount", "")
    currency = extra.get("currency", "")
    reason = extra.get("reason") or "the payment was declined"
    subject = f"Payment failed for invoice {invoice_number}"
    rows = [("Invoice Number", invoice_number), ("Amount", f"{amount} {currency}".strip()), ("Reason", reason)]
    body_html = f"<p>Hi {name},</p><p>We couldn't process your payment for invoice <b>{invoice_number}</b>. Please update your payment details or try again.</p>{detail_table(rows)}"
    html = render_email(
        preheader="Payment failed",
        heading="Payment Failed",
        body_html=body_html,
        accent="danger",
        accent_label="Action Needed",
        cta_label="Update Payment",
        cta_url=f"{settings.FRONTEND_BASE_URL}/invoices",
    )
    text = f"Hi {name},\n\nWe couldn't process your payment of {amount} {currency} for invoice {invoice_number} ({reason}).\n\n\u2014 {settings.COMPANY_NAME}"
    return subject, html, text


def _refund_completed(name: str, extra: dict) -> tuple[str, str, str]:
    invoice_number = extra.get("invoice_number", "")
    amount = extra.get("amount", "")
    currency = extra.get("currency", "")
    subject = f"Refund issued for invoice {invoice_number}"
    rows = [("Invoice Number", invoice_number)]
    if amount:
        rows.append(("Amount Refunded", f"{amount} {currency}".strip()))
    body_html = f"<p>Hi {name},</p><p>A refund for invoice <b>{invoice_number}</b> has been completed. It may take a few business days to reflect on your original payment method.</p>{detail_table(rows)}"
    html = render_email(
        preheader="Refund completed",
        heading="Refund Completed",
        body_html=body_html,
        accent="info",
        accent_label="Refund Issued",
    )
    text = f"Hi {name},\n\nA refund for invoice {invoice_number} has been completed.\n\n\u2014 {settings.COMPANY_NAME}"
    return subject, html, text


def _trial_ending_reminder(name: str, extra: dict) -> tuple[str, str, str]:
    plan_name = extra.get("plan_name", "your plan")
    trial_ends_at = extra.get("trial_ends_at", "soon")
    subject = f"Your {plan_name} trial ends {trial_ends_at}"
    rows = [("Plan", plan_name), ("Trial Ends", trial_ends_at)]
    body_html = (
        f"<p>Hi {name},</p><p>Just a heads up -- your free trial of <b>{plan_name}</b> "
        f"ends on <b>{trial_ends_at}</b>. After that, your subscription will continue "
        f"and billing will begin automatically.</p>{detail_table(rows)}"
    )
    html = render_email(
        preheader="Your trial is ending soon",
        heading="Trial Ending Soon",
        body_html=body_html,
        accent="warning",
        accent_label="Trial Ending",
        cta_label="Manage Subscription",
        cta_url=f"{settings.FRONTEND_BASE_URL}/subscriptions",
    )
    text = f"Hi {name},\n\nYour {plan_name} trial ends on {trial_ends_at}. Billing will begin automatically after that.\n\n\u2014 {settings.COMPANY_NAME}"
    return subject, html, text


def _renewal_reminder(name: str, extra: dict) -> tuple[str, str, str]:
    plan_name = extra.get("plan_name", "your plan")
    renewal_date = extra.get("renewal_date", "soon")
    amount = extra.get("amount", "")
    currency = extra.get("currency", "")
    subject = f"Your {plan_name} subscription renews {renewal_date}"
    rows = [("Plan", plan_name), ("Renewal Date", renewal_date)]
    if amount:
        rows.append(("Amount", f"{amount} {currency}".strip()))
    body_html = (
        f"<p>Hi {name},</p><p>This is a reminder that your <b>{plan_name}</b> subscription "
        f"will renew on <b>{renewal_date}</b>.</p>{detail_table(rows)}"
    )
    html = render_email(preheader="Upcoming renewal", heading="Upcoming Renewal", body_html=body_html)
    text = f"Hi {name},\n\nYour {plan_name} subscription renews on {renewal_date}.\n\n\u2014 {settings.COMPANY_NAME}"
    return subject, html, text


def _fallback(name: str, extra: dict) -> tuple[str, str, str]:
    subject = f"Update from {settings.COMPANY_NAME}"
    body_html = f"<p>Hi {name},</p><p>There's an update on your account.</p>"
    html = render_email(preheader="Account update", heading="Account Update", body_html=body_html)
    text = f"Hi {name},\n\nThere's an update on your account.\n\n\u2014 {settings.COMPANY_NAME}"
    return subject, html, text


_EVENT_BUILDERS = {
    "welcome": _welcome,
    "profile_updated": _profile_updated,
    "subscription_started": _subscription_started,
    "subscription_activated": _subscription_activated,
    "subscription_paused": _subscription_paused,
    "subscription_resumed": _subscription_resumed,
    "subscription_cancelled": _subscription_cancelled,
    "plan_changed": _plan_changed,
    "invoice_generated": _invoice_generated,
    "payment_succeeded": _payment_succeeded,
    "payment_failed": _payment_failed,
    "refund_completed": _refund_completed,
    "trial_ending_reminder": _trial_ending_reminder,
    "renewal_reminder": _renewal_reminder,
}
