"""
Celery task for email notifications (Module 2 + Phase 6B).

Dispatched via app.services.notification_dispatch.notify() from every
service that needs to fire a lifecycle email, so delivery never
blocks or can break the triggering action.
"""
from celery.utils.log import get_task_logger

from app.core.database import SessionLocal
from app.services.notification_service import NotificationService
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(
    name="app.tasks.notification_tasks.send_notification_email",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    ignore_result=True,
)
def send_notification_email(self, event_type: str, customer_id: str, extra: dict | None = None):
    """
    customer_id is passed as a string since Celery task args must be
    JSON-serializable; converted back to UUID here.
    """
    import uuid

    db = SessionLocal()
    try:
        NotificationService(db).dispatch(
            event_type=event_type,
            customer_id=uuid.UUID(customer_id),
            extra=extra or {},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Notification task failed for event=%s customer=%s", event_type, customer_id)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.notification_tasks.send_invoice_email",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    ignore_result=True,
)
def send_invoice_email(self, invoice_id: str):
    """
    Phase 6C "Email Invoice": regenerates the PDF fresh inside the
    task (Celery task args must be JSON-serializable, so the PDF
    bytes can't be passed in directly -- only the invoice_id) via the
    existing InvoicePdfService (Phase 4), then emails it as an
    attachment via NotificationService.send_invoice_attachment.
    """
    import uuid

    from app.models.enums import AuditEventType
    from app.repositories.invoice_repository import InvoiceRepository
    from app.services.audit_log_service import AuditLogService
    from app.services.invoice_pdf_service import InvoicePdfService

    db = SessionLocal()
    try:
        invoice = InvoiceRepository(db).get_by_id(uuid.UUID(invoice_id))
        if invoice is None:
            logger.warning("send_invoice_email skipped: invoice %s not found", invoice_id)
            return
        pdf_bytes = InvoicePdfService(db).generate(invoice)
        # Module 3, Phase 4: no INVOICE_DOWNLOADED here -- nothing was
        # downloaded through a browser, this is a backend->email flow.
        AuditLogService(db).record(
            event_type=AuditEventType.PDF_GENERATED,
            entity_type="invoice",
            entity_id=invoice.id,
            description=f"PDF generated for invoice {invoice.invoice_number} (email delivery)",
        )
        db.commit()
        NotificationService(db).send_invoice_attachment(invoice, pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.exception("send_invoice_email task failed for invoice=%s", invoice_id)
        raise self.retry(exc=exc)
    finally:
        db.close()
