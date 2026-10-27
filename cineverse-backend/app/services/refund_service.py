"""
Refund Processing (Module 2).

Handles:
  * Manually requested refunds (full or partial) against a paid
    invoice, via RefundService.create_refund.
  * Automatic unused-period refunds when a customer cancels an active
    (already-paid) subscription immediately, via
    RefundService.refund_unused_period_on_cancellation.

Phase 1D: create/read operations accept an optional `requesting_user`
and enforce that a non-admin may only access refunds belonging to
their own linked Customer (see app/services/ownership.py).
"""
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config.logging_config import get_logger
from app.exceptions.custom_exceptions import ConflictException, NotFoundException, ValidationException
from app.models.enums import AuditEventType, InvoiceStatus, PaymentStatus, RefundStatus
from app.models.plan import Plan
from app.models.refund import Refund
from app.models.subscription import Subscription
from app.models.user import User
from app.repositories.billing_cycle_repository import BillingCycleRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.refund_repository import RefundRepository
from app.services.audit_log_service import AuditLogService
from app.services.invoice_service import InvoiceService
from app.services.notification_dispatch import notify
from app.services.ownership import assert_owns_customer, effective_customer_filter

logger = get_logger(__name__)


class RefundService:
    def __init__(self, db: Session):
        self.db = db
        self.invoice_repository = InvoiceRepository(db)
        self.payment_repository = PaymentRepository(db)
        self.refund_repository = RefundRepository(db)
        self.billing_cycle_repository = BillingCycleRepository(db)
        self.invoice_service = InvoiceService(db)
        self.audit_service = AuditLogService(db)

    # ------------------------------------------------------------------
    # Manually requested refunds
    # ------------------------------------------------------------------
    def create_refund(
        self,
        invoice_id: uuid.UUID,
        reason: str,
        amount: Optional[Decimal] = None,
        actor_id: Optional[uuid.UUID] = None,
        requesting_user: Optional[User] = None,
    ) -> Refund:
        invoice = self.invoice_repository.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundException(f"Invoice {invoice_id} not found")
        assert_owns_customer(invoice.customer_id, requesting_user, self.db)
        if invoice.status not in (InvoiceStatus.PAID,):
            raise ConflictException(
                f"Only paid invoices can be refunded (invoice is '{invoice.status.value}')"
            )

        refund_amount = amount if amount is not None else invoice.total_amount
        if refund_amount <= 0:
            raise ValidationException("Refund amount must be greater than zero")
        if refund_amount > invoice.total_amount:
            raise ValidationException(
                "Refund amount cannot exceed the invoice's total amount"
            )

        return self._apply_refund(invoice, refund_amount, reason, actor_id)

    # ------------------------------------------------------------------
    # Automatic unused-period refund on immediate cancellation
    # ------------------------------------------------------------------
    def calculate_unused_period_amount(
        self, plan_price: Decimal, cycle_start: datetime, cycle_end: datetime, as_of: datetime
    ) -> Decimal:
        """Same remaining-time-proportion math as ProrationService, applied to a refund."""
        if cycle_end <= cycle_start or as_of >= cycle_end:
            return Decimal("0.00")
        if as_of < cycle_start:
            as_of = cycle_start
        total_days = (cycle_end - cycle_start).days or 1
        remaining_days = max((cycle_end - as_of).days, 0)
        proportion = Decimal(remaining_days) / Decimal(total_days)
        return (plan_price * proportion).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def refund_unused_period_on_cancellation(
        self,
        subscription: Subscription,
        plan: Plan,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Optional[Refund]:
        """
        Called when an active, already-paid subscription is cancelled
        immediately. Finds the most recent paid invoice for the
        subscription's current billing cycle and refunds the unused
        portion of it. Returns None (no-op) if:
          * the subscription is still in trial (nothing was charged), or
          * there is no paid invoice to refund against, or
          * there is no unused time left in the cycle.
        """
        cycle = self.billing_cycle_repository.get_current_for_subscription(subscription.id)
        if cycle is None:
            return None

        paid_invoices = [
            inv
            for inv in self.invoice_repository.list_all(subscription_id=subscription.id)
            if inv.status == InvoiceStatus.PAID and inv.billing_cycle_id == cycle.id
        ]
        if not paid_invoices:
            return None

        latest_invoice = paid_invoices[0]  # list_all orders by created_at desc
        now = datetime.now(timezone.utc)
        refund_amount = self.calculate_unused_period_amount(
            plan.price, cycle.cycle_start_date, cycle.cycle_end_date, now
        )
        if refund_amount <= 0:
            return None
        refund_amount = min(refund_amount, latest_invoice.total_amount)

        return self._apply_refund(
            latest_invoice,
            refund_amount,
            reason="Unused subscription period refunded on cancellation",
            actor_id=actor_id,
        )

    # ------------------------------------------------------------------
    # Shared refund application logic
    # ------------------------------------------------------------------
    def _apply_refund(
        self,
        invoice,
        refund_amount: Decimal,
        reason: str,
        actor_id: Optional[uuid.UUID],
    ) -> Refund:
        now = datetime.now(timezone.utc)
        refund = Refund(
            invoice_id=invoice.id,
            customer_id=invoice.customer_id,
            amount=refund_amount,
            currency=invoice.currency,
            reason=reason,
            status=RefundStatus.COMPLETED,
            processed_at=now,
        )
        self.refund_repository.add(refund)

        self.invoice_service.add_refund_line_item(
            invoice, refund_amount, description=f"Refund: {reason}"
        )
        old_total_amount = invoice.total_amount
        old_status = invoice.status
        old_tax_amount = invoice.tax_amount
        old_subtotal = invoice.subtotal

        # QA fix (confirmed via live test): tax_amount was never
        # reduced on refund, only total_amount. Tax reports sum
        # tax_amount for PAID invoices -- a *full* refund already
        # self-corrects there, since status flips away from PAID, but
        # a *partial* refund leaves status PAID with the invoice's
        # full original tax_amount still counted, overstating tax
        # actually retained. Reduce tax_amount and subtotal in the
        # same proportion as the refund, so subtotal + tax_amount
        # stays consistent with total_amount and tax reports reflect
        # what was genuinely kept.
        if old_total_amount > 0:
            tax_reduction = (old_tax_amount * refund_amount / old_total_amount).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            tax_reduction = Decimal("0.00")
        subtotal_reduction = refund_amount - tax_reduction

        invoice.tax_amount = max(invoice.tax_amount - tax_reduction, Decimal("0.00"))
        invoice.subtotal = max(invoice.subtotal - subtotal_reduction, Decimal("0.00"))
        invoice.total_amount = invoice.total_amount - refund_amount
        if invoice.total_amount <= 0:
            invoice.status = InvoiceStatus.REFUNDED
        self.db.flush()

        # Module 3, Phase 4: the invoice itself was genuinely mutated
        # here (total_amount, and conditionally status) -- previously
        # only REFUND_CREATED fired, filed against the refund entity,
        # so this change never appeared in the invoice's own audit
        # trail. Reuses this exact, pre-existing mutation point rather
        # than inventing a new one.
        self.audit_service.record(
            event_type=AuditEventType.INVOICE_UPDATED,
            entity_type="invoice",
            entity_id=invoice.id,
            description=f"Invoice {invoice.invoice_number} updated by refund",
            actor_id=actor_id,
            old_value=(
                f"total_amount={old_total_amount}, status={old_status.value}, "
                f"tax_amount={old_tax_amount}, subtotal={old_subtotal}"
            ),
            new_value=(
                f"total_amount={invoice.total_amount}, status={invoice.status.value}, "
                f"tax_amount={invoice.tax_amount}, subtotal={invoice.subtotal}"
            ),
            remarks=f"Refund of {refund_amount} {invoice.currency}: {reason}",
        )

        # Mark the most recent successful payment as refunded when the
        # invoice is fully refunded.
        if invoice.status == InvoiceStatus.REFUNDED:
            payments = self.payment_repository.list_for_invoice(invoice.id)
            for payment in payments:
                if payment.status == PaymentStatus.SUCCEEDED:
                    payment.status = PaymentStatus.REFUNDED
            self.db.flush()

        self.audit_service.record(
            event_type=AuditEventType.REFUND_CREATED,
            entity_type="refund",
            entity_id=refund.id,
            description=f"Refund of {refund_amount} {invoice.currency} issued: {reason}",
            actor_id=actor_id,
            metadata={"invoice_id": str(invoice.id), "amount": str(refund_amount)},
        )
        self.db.commit()
        self.db.refresh(refund)

        # Module 2 "Notifications" requirement: notify the customer a
        # refund completed. This is the actual refund-creation path
        # (both manual POST /refunds and the auto unused-period refund
        # on cancellation funnel through here), so it's dispatched from
        # here rather than only from the payment webhook handler, which
        # this application's refund flow doesn't route through.
        notify(
            "refund_completed",
            invoice.customer_id,
            {
                "invoice_number": invoice.invoice_number,
                "amount": str(refund_amount),
                "currency": invoice.currency,
            },
        )
        return refund

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------
    def get_refund(self, refund_id: uuid.UUID, requesting_user: Optional[User] = None) -> Refund:
        refund = self.refund_repository.get_by_id(refund_id)
        if refund is None:
            raise NotFoundException(f"Refund {refund_id} not found")
        assert_owns_customer(refund.customer_id, requesting_user, self.db)
        return refund

    def list_refunds(
        self,
        customer_id: Optional[uuid.UUID] = None,
        invoice_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 100,
        requesting_user: Optional[User] = None,
    ) -> List[Refund]:
        effective_customer_id = effective_customer_filter(customer_id, requesting_user, self.db)
        return self.refund_repository.list_all(effective_customer_id, invoice_id, skip, limit)

    def count_refunds(
        self,
        customer_id: Optional[uuid.UUID] = None,
        invoice_id: Optional[uuid.UUID] = None,
        requesting_user: Optional[User] = None,
    ) -> int:
        effective_customer_id = effective_customer_filter(customer_id, requesting_user, self.db)
        return self.refund_repository.count_all(effective_customer_id, invoice_id)
