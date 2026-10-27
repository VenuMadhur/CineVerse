"""
Payment Webhook Handler (Module 2).

Processes incoming payment gateway events (paid / failed / refunded):
updates the Payment and Invoice records, and drives the subscription
state machine (past_due <-> active) accordingly. Idempotent: replaying
the same event for a payment already in its target state is a no-op.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config.logging_config import get_logger
from app.exceptions.custom_exceptions import NotFoundException
from app.models.enums import AuditEventType, InvoiceStatus, PaymentStatus, SubscriptionStatus
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.webhook import PaymentWebhookPayload, WebhookAcknowledgement
from app.services.audit_log_service import AuditLogService
from app.services.notification_dispatch import notify
from app.services.retry_service import RetryService
from app.services.subscription_state_machine import SubscriptionStateMachine

logger = get_logger(__name__)


class PaymentWebhookHandlerService:
    def __init__(self, db: Session):
        self.db = db
        self.invoice_repository = InvoiceRepository(db)
        self.payment_repository = PaymentRepository(db)
        self.subscription_repository = SubscriptionRepository(db)
        self.audit_service = AuditLogService(db)
        self.retry_service = RetryService(db)

    def handle_event(self, payload: PaymentWebhookPayload) -> WebhookAcknowledgement:
        payment = self.payment_repository.get_by_gateway_reference(payload.transaction_id)
        if payment is None:
            raise NotFoundException(
                f"No payment found for transaction '{payload.transaction_id}'"
            )

        invoice = self.invoice_repository.get_by_id(payment.invoice_id)
        if invoice is None:
            raise NotFoundException(f"Invoice {payment.invoice_id} not found")

        self.audit_service.record(
            event_type=AuditEventType.WEBHOOK_RECEIVED,
            entity_type="payment",
            entity_id=payment.id,
            description=f"Payment webhook received: {payload.status}",
            metadata={"transaction_id": payload.transaction_id, "status": payload.status},
        )

        if payload.status == "paid":
            ack = self._handle_paid(payment, invoice)
        elif payload.status == "failed":
            ack = self._handle_failed(payment, invoice, payload.message)
        else:
            ack = self._handle_refunded(payment, invoice)

        self.db.commit()
        return ack

    # ------------------------------------------------------------------
    def _handle_paid(self, payment, invoice) -> WebhookAcknowledgement:
        if payment.status == PaymentStatus.SUCCEEDED and invoice.status == InvoiceStatus.PAID:
            return WebhookAcknowledgement(
                event_processed=False, detail="Payment already marked as succeeded (idempotent no-op)"
            )

        now = datetime.now(timezone.utc)
        payment.status = PaymentStatus.SUCCEEDED
        payment.processed_at = payment.processed_at or now
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = now
        self.db.flush()

        subscription = self.subscription_repository.get_by_id(invoice.subscription_id)
        if subscription is not None and subscription.status == SubscriptionStatus.PAST_DUE:
            if SubscriptionStateMachine.can_transition(
                subscription.status, SubscriptionStatus.ACTIVE
            ):
                subscription.status = SubscriptionStatus.ACTIVE
                subscription.activated_at = now
                self.db.flush()
                self.audit_service.record(
                    event_type=AuditEventType.STATUS_CHANGED,
                    entity_type="subscription",
                    entity_id=subscription.id,
                    description="Subscription reactivated after successful payment",
                )

        self.audit_service.record(
            event_type=AuditEventType.INVOICE_PAID,
            entity_type="invoice",
            entity_id=invoice.id,
            description=f"Invoice {invoice.invoice_number} marked as paid",
            metadata={"payment_id": str(payment.id)},
        )
        self.audit_service.record(
            event_type=AuditEventType.PAYMENT_SUCCEEDED,
            entity_type="payment",
            entity_id=payment.id,
            description="Payment succeeded",
        )
        notify(
            "payment_succeeded",
            invoice.customer_id,
            {
                "invoice_number": invoice.invoice_number,
                "amount": str(invoice.total_amount),
                "currency": invoice.currency,
                "transaction_id": payment.gateway_reference,
            },
        )
        return WebhookAcknowledgement(event_processed=True, detail="Invoice marked as paid")

    def _handle_failed(self, payment, invoice, message: str | None) -> WebhookAcknowledgement:
        if payment.status == PaymentStatus.FAILED and invoice.status == InvoiceStatus.FAILED:
            return WebhookAcknowledgement(
                event_processed=False, detail="Payment already marked as failed (idempotent no-op)"
            )

        payment.status = PaymentStatus.FAILED
        payment.failure_reason = message or "Payment failed"
        invoice.status = InvoiceStatus.FAILED
        self.db.flush()

        subscription = self.subscription_repository.get_by_id(invoice.subscription_id)
        if subscription is not None and subscription.status == SubscriptionStatus.ACTIVE:
            if SubscriptionStateMachine.can_transition(
                subscription.status, SubscriptionStatus.PAST_DUE
            ):
                subscription.status = SubscriptionStatus.PAST_DUE
                subscription.past_due_at = datetime.now(timezone.utc)
                self.db.flush()
                self.audit_service.record(
                    event_type=AuditEventType.STATUS_CHANGED,
                    entity_type="subscription",
                    entity_id=subscription.id,
                    description=(
                        "Subscription marked past_due after failed payment "
                        "(prepared for retry process in Module 3)"
                    ),
                )

        self.audit_service.record(
            event_type=AuditEventType.INVOICE_FAILED,
            entity_type="invoice",
            entity_id=invoice.id,
            description=f"Invoice {invoice.invoice_number} marked as failed",
            metadata={"payment_id": str(payment.id), "reason": message},
        )
        self.audit_service.record(
            event_type=AuditEventType.PAYMENT_FAILED,
            entity_type="payment",
            entity_id=payment.id,
            description="Payment failed",
            metadata={"reason": message},
        )
        notify(
            "payment_failed",
            invoice.customer_id,
            {
                "invoice_number": invoice.invoice_number,
                "amount": str(invoice.total_amount),
                "currency": invoice.currency,
                "reason": message,
            },
        )
        # Module 3, Phase 1b: single additive call after the existing
        # failure-handling flow above (payment/invoice/subscription
        # status, audit events, notification) has fully completed.
        # Does not change any of that flow's own logic -- purely adds
        # one new side effect on top of it.
        self.retry_service.enqueue_initial_retry(invoice, payment)
        return WebhookAcknowledgement(event_processed=True, detail="Invoice marked as failed")

    def _handle_refunded(self, payment, invoice) -> WebhookAcknowledgement:
        if payment.status == PaymentStatus.REFUNDED:
            return WebhookAcknowledgement(
                event_processed=False, detail="Payment already marked as refunded (idempotent no-op)"
            )

        payment.status = PaymentStatus.REFUNDED
        old_status = invoice.status
        invoice.status = InvoiceStatus.REFUNDED
        self.db.flush()

        self.audit_service.record(
            event_type=AuditEventType.PAYMENT_REFUNDED,
            entity_type="payment",
            entity_id=payment.id,
            description="Payment marked as refunded via webhook",
        )
        # Module 3, Phase 4: the invoice itself was genuinely mutated
        # here too (status), previously only tracked against the
        # payment entity above -- reuses this exact mutation point.
        self.audit_service.record(
            event_type=AuditEventType.INVOICE_UPDATED,
            entity_type="invoice",
            entity_id=invoice.id,
            description=f"Invoice {invoice.invoice_number} marked as refunded via webhook",
            old_value=f"status={old_status.value}",
            new_value=f"status={invoice.status.value}",
        )
        notify(
            "refund_completed",
            invoice.customer_id,
            {"invoice_number": invoice.invoice_number},
        )
        return WebhookAcknowledgement(event_processed=True, detail="Invoice marked as refunded")
