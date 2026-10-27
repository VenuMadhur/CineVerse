"""
Billing Scheduler.

Contains the core logic executed periodically by Celery Beat:
    1. Check active subscriptions.
    2. Identify subscriptions/billing cycles due for renewal.
    3. Trigger invoice generation (via InvoiceService).
    4. Update the next billing date (advance the billing cycle).
    5. Apply any pending end-of-cycle cancellations.

Kept as a plain service (not a Celery task itself) so it can be unit
tested without a running Celery worker.
"""
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app.config.logging_config import get_logger
from app.models.enums import AuditEventType, SubscriptionStatus
from app.repositories.billing_cycle_repository import BillingCycleRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.services.audit_log_service import AuditLogService
from app.services.billing_cycle_service import BillingCycleService
from app.services.invoice_service import InvoiceService
from app.services.subscription_service import SubscriptionService

logger = get_logger(__name__)


class BillingSchedulerService:
    def __init__(self, db: Session):
        self.db = db
        self.subscription_repository = SubscriptionRepository(db)
        self.billing_cycle_repository = BillingCycleRepository(db)
        self.plan_repository = PlanRepository(db)
        self.customer_repository = CustomerRepository(db)
        self.billing_cycle_service = BillingCycleService(db)
        self.subscription_service = SubscriptionService(db)
        self.invoice_service = InvoiceService(db)
        self.audit_service = AuditLogService(db)

    def run(self, as_of: datetime | None = None) -> dict:
        """
        Executes one full scheduler pass. Returns a summary dict for
        logging / task result inspection.
        """
        as_of = as_of or datetime.now(timezone.utc)
        due_cycles = self.billing_cycle_repository.list_due(as_of)

        logger.info("Billing scheduler: found %d billing cycles due", len(due_cycles))

        processed = 0
        cancelled = 0
        invoices_created: List[str] = []

        for cycle in due_cycles:
            subscription = self.subscription_repository.get_by_id(cycle.subscription_id)
            if subscription is None:
                continue

            # Skip subscriptions that are not in a billable state.
            if subscription.status not in (
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.TRIAL,
            ):
                continue

            # If the customer requested end-of-cycle cancellation, finalize
            # the cancellation now instead of renewing.
            if subscription.cancel_at_period_end:
                cycle.is_billed = True
                self.db.flush()
                subscription.status = SubscriptionStatus.CANCELLED
                subscription.cancelled_at = as_of
                self.db.flush()
                self.audit_service.record(
                    event_type=AuditEventType.SUBSCRIPTION_CANCELLED,
                    entity_type="subscription",
                    entity_id=subscription.id,
                    description="Subscription cancelled at end of billing cycle",
                )
                cancelled += 1
                continue

            # Trial subscriptions past their trial-end billing cycle move
            # to active before being invoiced.
            if subscription.status == SubscriptionStatus.TRIAL:
                subscription.status = SubscriptionStatus.ACTIVE
                subscription.activated_at = as_of
                self.db.flush()
                self.audit_service.record(
                    event_type=AuditEventType.STATUS_CHANGED,
                    entity_type="subscription",
                    entity_id=subscription.id,
                    description="Trial ended, subscription activated by billing scheduler",
                )

            plan = self.plan_repository.get_by_id(subscription.plan_id)
            customer = self.customer_repository.get_by_id(subscription.customer_id)
            invoice = self.invoice_service.generate_billing_invoice(
                subscription=subscription, plan=plan, customer=customer, cycle=cycle
            )
            invoices_created.append(invoice.invoice_number)

            self.billing_cycle_service.advance_cycle(
                subscription_id=subscription.id,
                billing_interval=plan.billing_interval,
            )
            processed += 1

        self.db.commit()

        summary = {
            "as_of": as_of.isoformat(),
            "cycles_due": len(due_cycles),
            "subscriptions_processed": processed,
            "subscriptions_cancelled": cancelled,
            "invoices_created": invoices_created,
        }
        logger.info("Billing scheduler run complete: %s", summary)
        return summary
