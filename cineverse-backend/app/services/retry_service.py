"""
Business logic for the Failed Payment Retry module (Module 3).

Phase 1a: Retry Configuration CRUD.
Phase 1b: enqueue_initial_retry() -- called once, additively, by
PaymentWebhookHandlerService._handle_failed() after its existing
payment-failure flow completes (no change to that flow's own logic).
Retry *execution* itself lives in RetrySchedulerService
(app/scheduler/retry_scheduler_service.py), following the same
separation this codebase already uses for BillingSchedulerService and
ReminderSchedulerService: this module answers "what is the retry
schedule and how do entries get created," the scheduler answers "when
do queued entries actually get processed."
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config.logging_config import get_logger
from app.exceptions.custom_exceptions import ConflictException, NotFoundException
from app.models.enums import AuditEventType, RetryStatus
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.retry_configuration import RetryConfiguration
from app.models.retry_queue import RetryQueue
from app.repositories.retry_configuration_repository import RetryConfigurationRepository
from app.repositories.retry_queue_repository import RetryQueueRepository
from app.schemas.retry import RetryConfigurationCreate, RetryConfigurationUpdate
from app.services.audit_log_service import AuditLogService

logger = get_logger(__name__)


class RetryService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = RetryConfigurationRepository(db)
        self.queue_repository = RetryQueueRepository(db)
        self.audit_service = AuditLogService(db)

    def create_configuration(
        self, payload: RetryConfigurationCreate, actor_id: Optional[uuid.UUID] = None
    ) -> RetryConfiguration:
        existing = self.repository.get_by_retry_attempt(payload.retry_attempt)
        if existing is not None:
            raise ConflictException(
                f"A retry configuration for attempt {payload.retry_attempt} already exists"
            )

        config = RetryConfiguration(
            retry_attempt=payload.retry_attempt,
            retry_after_days=payload.retry_after_days,
            is_active=payload.is_active,
        )
        config = self.repository.add(config)

        self.audit_service.record(
            event_type=AuditEventType.RETRY_CONFIGURATION_CREATED,
            entity_type="retry_configuration",
            entity_id=config.id,
            description=(
                f"Retry configuration created: attempt {config.retry_attempt} "
                f"after {config.retry_after_days} day(s)"
            ),
            actor_id=actor_id,
            metadata={
                "retry_attempt": config.retry_attempt,
                "retry_after_days": config.retry_after_days,
            },
        )
        self.db.commit()
        self.db.refresh(config)
        return config

    def update_configuration(
        self,
        config_id: uuid.UUID,
        payload: RetryConfigurationUpdate,
        actor_id: Optional[uuid.UUID] = None,
    ) -> RetryConfiguration:
        config = self._get_configuration_or_404(config_id)

        update_data = payload.model_dump(exclude_unset=True)
        changed_fields = {}
        old_values = {}
        for field, value in update_data.items():
            current = getattr(config, field)
            if current != value:
                changed_fields[field] = value
                old_values[field] = current
                setattr(config, field, value)

        if changed_fields:
            self.db.flush()
            self.audit_service.record(
                event_type=AuditEventType.RETRY_CONFIGURATION_UPDATED,
                entity_type="retry_configuration",
                entity_id=config.id,
                description=f"Retry configuration for attempt {config.retry_attempt} updated",
                actor_id=actor_id,
                old_value=str(old_values),
                new_value=str(changed_fields),
                metadata={"changed_fields": list(changed_fields.keys())},
            )
        self.db.commit()
        self.db.refresh(config)
        return config

    def get_configuration(self, config_id: uuid.UUID) -> RetryConfiguration:
        return self._get_configuration_or_404(config_id)

    def list_configurations(self, skip: int = 0, limit: int = 100) -> List[RetryConfiguration]:
        return self.repository.list_all(skip, limit)

    def count_configurations(self) -> int:
        return self.repository.count()

    def _get_configuration_or_404(self, config_id: uuid.UUID) -> RetryConfiguration:
        config = self.repository.get_by_id(config_id)
        if config is None:
            raise NotFoundException(f"Retry configuration {config_id} not found")
        return config

    # ------------------------------------------------------------------
    # Phase 1b: single additive entry point called by
    # PaymentWebhookHandlerService._handle_failed(), after its existing
    # failure-handling flow (payment/invoice/subscription status,
    # audit events, notification) has already completed. Does not
    # commit -- flush only, so it participates in the caller's own
    # transaction rather than starting a second one.
    # ------------------------------------------------------------------
    def enqueue_initial_retry(self, invoice: Invoice, payment: Payment) -> Optional[RetryQueue]:
        """
        Creates the first RetryQueue entry for a newly-failed payment,
        using the lowest-numbered active retry configuration. A no-op
        (returns None) if no retry configuration has been set up at
        all -- a failed payment must never be blocked or broken by
        retries simply not being configured yet.
        """
        first_config = self.repository.get_first_active()
        if first_config is None:
            logger.info(
                "No active retry configuration exists; skipping retry enqueue for invoice %s",
                invoice.id,
            )
            return None

        scheduled_retry_date = datetime.now(timezone.utc) + timedelta(
            days=first_config.retry_after_days
        )
        retry_entry = RetryQueue(
            invoice_id=invoice.id,
            payment_id=payment.id,
            customer_id=invoice.customer_id,
            retry_attempt=first_config.retry_attempt,
            scheduled_retry_date=scheduled_retry_date,
            retry_status=RetryStatus.PENDING,
        )
        self.queue_repository.add(retry_entry)

        self.audit_service.record(
            event_type=AuditEventType.RETRY_SCHEDULED,
            entity_type="invoice",
            entity_id=invoice.id,
            description=(
                f"Retry attempt {first_config.retry_attempt} scheduled for "
                f"invoice {invoice.invoice_number} on "
                f"{scheduled_retry_date.strftime('%Y-%m-%d')}"
            ),
            metadata={
                "retry_attempt": first_config.retry_attempt,
                "scheduled_retry_date": scheduled_retry_date.isoformat(),
                "payment_id": str(payment.id),
            },
        )
        return retry_entry
