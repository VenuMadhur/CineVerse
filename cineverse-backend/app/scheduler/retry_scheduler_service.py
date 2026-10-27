"""
Failed Payment Retry Scheduler (Module 3, Phase 1b).

Executed periodically by Celery Beat, alongside (but separately from)
the existing billing and reminder schedulers. Purely event-driven:
this scheduler only processes RetryQueue rows that already exist and
are due (scheduled_retry_date <= as_of) -- it never scans Invoice or
Payment tables looking for new failures. Initial queue entries are
created elsewhere, by PaymentWebhookHandlerService calling
RetryService.enqueue_initial_retry() once, right after its own
existing failure-handling flow completes.

Reuses, rather than duplicates:
  - PaymentGatewayService.process_payment() for the actual retry
    charge -- the exact same gateway/webhook flow a manual "Pay Now"
    retry already goes through, so a successful retry payment
    automatically reactivates a past_due subscription via the
    existing _handle_paid webhook logic, with no new code for that.
  - SubscriptionService.cancel_subscription() when the configured
    retry attempts are exhausted, rather than mutating subscription
    status directly.
  - AuditLogService for every event recorded here.

Kept as a plain service (not a Celery task itself), matching
BillingSchedulerService/ReminderSchedulerService, so it can be unit
tested without a running Celery worker.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.config.logging_config import get_logger
from app.models.enums import AuditEventType, CancellationType, PaymentStatus, RetryStatus
from app.models.retry_queue import RetryQueue
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.retry_configuration_repository import RetryConfigurationRepository
from app.repositories.retry_queue_repository import RetryQueueRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.subscription import SubscriptionCancel
from app.services.audit_log_service import AuditLogService
from app.services.payment_gateway_service import PaymentGatewayService
from app.services.subscription_service import SubscriptionService

logger = get_logger(__name__)


class RetrySchedulerService:
    def __init__(self, db: Session):
        self.db = db
        self.retry_queue_repository = RetryQueueRepository(db)
        self.retry_configuration_repository = RetryConfigurationRepository(db)
        self.invoice_repository = InvoiceRepository(db)
        self.subscription_repository = SubscriptionRepository(db)
        self.audit_service = AuditLogService(db)
        self.payment_gateway_service = PaymentGatewayService(db)
        self.subscription_service = SubscriptionService(db)

    def run(self, as_of: Optional[datetime] = None) -> dict:
        """
        Executes one full retry-processing pass: every PENDING queue
        entry whose scheduled_retry_date has arrived. Returns a
        summary dict (also used by tests and for logging).
        """
        as_of = as_of or datetime.now(timezone.utc)
        due_entries = self.retry_queue_repository.list_due(as_of)

        succeeded, failed_and_rescheduled, exhausted = 0, 0, 0
        for entry in due_entries:
            outcome = self._process_entry(entry)
            if outcome == "succeeded":
                succeeded += 1
            elif outcome == "rescheduled":
                failed_and_rescheduled += 1
            elif outcome == "exhausted":
                exhausted += 1

        summary = {
            "as_of": as_of.isoformat(),
            "processed": len(due_entries),
            "succeeded": succeeded,
            "rescheduled": failed_and_rescheduled,
            "exhausted": exhausted,
        }
        logger.info("Retry scheduler run complete: %s", summary)
        return summary

    def _process_entry(self, entry) -> str:
        entry.actual_retry_date = datetime.now(timezone.utc)
        self.db.flush()

        self.audit_service.record(
            event_type=AuditEventType.RETRY_ATTEMPTED,
            entity_type="invoice",
            entity_id=entry.invoice_id,
            description=f"Retry attempt {entry.retry_attempt} executed",
            metadata={"retry_queue_id": str(entry.id)},
        )

        result = self.payment_gateway_service.process_payment(invoice_id=entry.invoice_id)

        if result.status == PaymentStatus.SUCCEEDED:
            return self._handle_success(entry)
        return self._handle_failure(entry, result.message)

    def _handle_success(self, entry) -> str:
        entry.retry_status = RetryStatus.SUCCEEDED
        self.db.flush()

        self.audit_service.record(
            event_type=AuditEventType.RETRY_SUCCEEDED,
            entity_type="invoice",
            entity_id=entry.invoice_id,
            description=f"Retry attempt {entry.retry_attempt} succeeded",
        )
        self._cancel_remaining_pending_retries(entry.invoice_id, reason="a retry already succeeded")
        self.db.commit()
        return "succeeded"

    def _handle_failure(self, entry, failure_reason: Optional[str]) -> str:
        entry.retry_status = RetryStatus.FAILED
        entry.failure_reason = failure_reason or "Payment declined"
        self.db.flush()

        self.audit_service.record(
            event_type=AuditEventType.RETRY_FAILED,
            entity_type="invoice",
            entity_id=entry.invoice_id,
            description=f"Retry attempt {entry.retry_attempt} failed",
            metadata={"reason": failure_reason},
        )

        next_config = self.retry_configuration_repository.get_next_active(entry.retry_attempt)
        if next_config is not None:
            self._schedule_next_retry(entry, next_config)
            self.db.commit()
            return "rescheduled"

        self._exhaust_retries(entry)
        self.db.commit()
        return "exhausted"

    def _schedule_next_retry(self, entry, next_config) -> None:
        scheduled_retry_date = datetime.now(timezone.utc) + timedelta(
            days=next_config.retry_after_days
        )
        next_entry = RetryQueue(
            invoice_id=entry.invoice_id,
            payment_id=entry.payment_id,
            customer_id=entry.customer_id,
            retry_attempt=next_config.retry_attempt,
            scheduled_retry_date=scheduled_retry_date,
            retry_status=RetryStatus.PENDING,
        )
        self.retry_queue_repository.add(next_entry)

        self.audit_service.record(
            event_type=AuditEventType.RETRY_SCHEDULED,
            entity_type="invoice",
            entity_id=entry.invoice_id,
            description=(
                f"Retry attempt {next_config.retry_attempt} scheduled for "
                f"{scheduled_retry_date.strftime('%Y-%m-%d')}"
            ),
            metadata={
                "retry_attempt": next_config.retry_attempt,
                "scheduled_retry_date": scheduled_retry_date.isoformat(),
            },
        )

    def _exhaust_retries(self, entry) -> None:
        """
        All configured retry attempts have failed: cancel the
        subscription (reusing the existing cancel_subscription(),
        never mutating status directly). The invoice stays FAILED --
        Module 3's spec defines only Pending/Paid/Failed, and FAILED
        is already its correct, accurate state throughout the entire
        retry process; no further invoice transition is called for.
        """
        invoice = self.invoice_repository.get_by_id(entry.invoice_id)
        if invoice is not None and invoice.subscription_id is not None:
            self.subscription_service.cancel_subscription(
                invoice.subscription_id,
                SubscriptionCancel(
                    cancellation_type=CancellationType.IMMEDIATE,
                    reason="All configured payment retry attempts failed",
                ),
                actor_id=None,
                requesting_user=None,
            )

        self.audit_service.record(
            event_type=AuditEventType.RETRY_CANCELLED,
            entity_type="invoice",
            entity_id=entry.invoice_id,
            description="Retry attempts exhausted; subscription cancelled",
        )

    def _cancel_remaining_pending_retries(self, invoice_id: uuid.UUID, reason: str) -> None:
        for pending_entry in self.retry_queue_repository.list_pending_for_invoice(invoice_id):
            pending_entry.retry_status = RetryStatus.CANCELLED
            self.db.flush()
            self.audit_service.record(
                event_type=AuditEventType.RETRY_CANCELLED,
                entity_type="invoice",
                entity_id=invoice_id,
                description=f"Remaining scheduled retry attempt {pending_entry.retry_attempt} "
                f"cancelled: {reason}",
            )
