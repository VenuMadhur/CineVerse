"""
Shared notification dispatch helper (Phase 6B).

Every service that needs to fire a notification email calls
`notify(event_type, customer_id, extra)` instead of duplicating the
try/except + lazy Celery import boilerplate that existed independently
in `payment_webhook_handler_service.py` and `refund_service.py` before
this phase. Centralizing it here means the "never let a notification
failure break the actual business action" guarantee is enforced in
exactly one place, not copy-pasted at every call site.
"""
import uuid

from app.config.logging_config import get_logger

logger = get_logger(__name__)


def notify(event_type: str, customer_id: uuid.UUID, extra: dict | None = None) -> None:
    """
    Fires a notification email asynchronously via the existing
    Celery + Redis infrastructure. Never raises -- a broker outage or
    any other dispatch failure is logged and swallowed, since email
    delivery must never break the billing/subscription action that
    triggered it.
    """
    try:
        from app.tasks.notification_tasks import send_notification_email

        send_notification_email.delay(event_type, str(customer_id), extra or {})
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to dispatch notification task for event=%s customer=%s",
            event_type, customer_id,
        )
