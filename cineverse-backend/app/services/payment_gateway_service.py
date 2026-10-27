"""
Mock Payment Gateway (Module 2).

Simulates a real payment gateway (e.g. Stripe/Razorpay) without any
external network calls: given an invoice, it "charges" the
configured amount and randomly succeeds or fails according to
`settings.PAYMENT_GATEWAY_SUCCESS_RATE`, then fires a payment webhook
event (see WebhookSenderService) exactly as a real gateway would.

Phase 1D: enforces that a non-admin may only pay an invoice belonging
to their own linked Customer.
"""
import random
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.config.logging_config import get_logger
from app.config.settings import settings
from app.exceptions.custom_exceptions import ConflictException, NotFoundException
from app.models.enums import AuditEventType, InvoiceStatus, PaymentStatus
from app.models.payment import Payment
from app.models.user import User
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.payment import PaymentResponse
from app.services.audit_log_service import AuditLogService
from app.services.ownership import assert_owns_customer
from app.services.webhook_sender_service import WebhookSenderService

logger = get_logger(__name__)


class PaymentGatewayService:
    def __init__(self, db: Session):
        self.db = db
        self.invoice_repository = InvoiceRepository(db)
        self.payment_repository = PaymentRepository(db)
        self.audit_service = AuditLogService(db)
        self.webhook_sender = WebhookSenderService(db)

    def process_payment(
        self,
        invoice_id: uuid.UUID,
        amount: Optional[Decimal] = None,
        actor_id: Optional[uuid.UUID] = None,
        requesting_user: Optional[User] = None,
    ) -> PaymentResponse:
        invoice = self.invoice_repository.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundException(f"Invoice {invoice_id} not found")
        assert_owns_customer(invoice.customer_id, requesting_user, self.db)
        if invoice.status in (InvoiceStatus.PAID, InvoiceStatus.VOID):
            raise ConflictException(
                f"Invoice is already '{invoice.status.value}' and cannot be charged again"
            )

        charge_amount = amount if amount is not None else invoice.total_amount
        attempt_number = self.payment_repository.count_for_invoice(invoice_id) + 1
        now = datetime.now(timezone.utc)

        succeeded = random.random() < settings.PAYMENT_GATEWAY_SUCCESS_RATE
        transaction_id = f"MOCKTXN-{uuid.uuid4().hex[:16].upper()}"

        gateway_response = {
            "gateway": "mock_gateway",
            "transaction_id": transaction_id,
            "requested_amount": str(charge_amount),
            "currency": invoice.currency,
            "simulated_outcome": "success" if succeeded else "failure",
        }

        payment = Payment(
            invoice_id=invoice.id,
            amount=charge_amount,
            currency=invoice.currency,
            status=PaymentStatus.SUCCEEDED if succeeded else PaymentStatus.FAILED,
            payment_method="mock_gateway",
            gateway_reference=transaction_id,
            gateway_response=gateway_response,
            attempt_number=attempt_number,
            processed_at=now,
            failure_reason=None if succeeded else "Simulated gateway decline",
        )
        self.payment_repository.add(payment)

        self.audit_service.record(
            event_type=AuditEventType.PAYMENT_PROCESSED,
            entity_type="payment",
            entity_id=payment.id,
            description=(
                f"Mock payment {'succeeded' if succeeded else 'failed'} "
                f"for invoice {invoice.invoice_number}"
            ),
            actor_id=actor_id,
            metadata={
                "invoice_id": str(invoice.id),
                "transaction_id": transaction_id,
                "amount": str(charge_amount),
                "attempt_number": attempt_number,
            },
        )
        self.db.commit()
        self.db.refresh(payment)

        # Fire the webhook event exactly as a real gateway would after
        # settling the charge (paid or failed).
        self.webhook_sender.send_payment_event(
            event_type="paid" if succeeded else "failed",
            invoice_id=invoice.id,
            customer_id=invoice.customer_id,
            transaction_id=transaction_id,
            amount=charge_amount,
            event_time=now,
            message="Payment processed successfully" if succeeded else "Payment declined by gateway",
        )

        return PaymentResponse(
            transaction_id=transaction_id,
            invoice_id=invoice.id,
            amount=charge_amount,
            status=payment.status,
            processed_at=payment.processed_at,
            message=(
                "Payment processed successfully"
                if succeeded
                else "Payment declined by gateway"
            ),
        )
