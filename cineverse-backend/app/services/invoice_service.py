"""
Invoice Generation Engine (Module 2).

Centralizes invoice + line-item creation so both the Celery Beat
billing scheduler (regular renewal invoices) and the subscription
plan-change flow (proration invoices) build invoices the same way,
with consistent invoice numbering and tax calculation.

Phase 1D: read operations accept an optional `requesting_user` and
enforce that a non-admin may only access invoices belonging to their
own linked Customer (see app/services/ownership.py). Generation
methods (called only from internal scheduler/subscription-service
code, never directly from a request) are unaffected.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config.logging_config import get_logger
from app.exceptions.custom_exceptions import NotFoundException
from app.models.billing_cycle import BillingCycle
from app.models.customer import Customer
from app.models.enums import AuditEventType, InvoiceLineItemType, InvoiceStatus
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.refund_repository import RefundRepository
from app.services.audit_log_service import AuditLogService
from app.services.notification_dispatch import notify
from app.services.ownership import assert_owns_customer, effective_customer_filter
from app.services.proration_service import ProrationCalculation
from app.services.tax_service import TaxService

logger = get_logger(__name__)


def _generate_invoice_number(reference_date: datetime) -> str:
    return f"INV-{reference_date.strftime('%Y%m')}-{uuid.uuid4().hex[:8].upper()}"


class InvoiceService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = InvoiceRepository(db)
        self.customer_repository = CustomerRepository(db)
        self.payment_repository = PaymentRepository(db)
        self.refund_repository = RefundRepository(db)
        self.audit_service = AuditLogService(db)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------
    def get_invoice(
        self, invoice_id: uuid.UUID, requesting_user: Optional[User] = None
    ) -> Invoice:
        invoice = self.repository.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundException(f"Invoice {invoice_id} not found")
        assert_owns_customer(invoice.customer_id, requesting_user, self.db)
        return invoice

    def get_invoice_with_details(
        self, invoice_id: uuid.UUID, requesting_user: Optional[User] = None
    ) -> Invoice:
        """
        Phase 6C: the same ownership-checked Invoice as get_invoice(),
        with a handful of denormalized, request-only fields attached
        as plain attributes (picked up by InvoiceDetailResponse via
        Pydantic's from_attributes) -- customer name/email/country/
        address, the payment method from the most recent payment
        attempt, a computed discount total (0 unless a future
        discount/coupon feature ever populates DISCOUNT line items),
        and a refund_status summary ("none"/"partial"/"full") that
        isn't otherwise derivable from `status` alone -- a partial
        refund leaves an invoice's status as `paid`, just with a
        reduced total_amount, so there's no existing way to tell "this
        was refunded a bit" from "this was never refunded" without
        this. Reuses PaymentRepository/RefundRepository/
        CustomerRepository exactly as-is -- no new queries beyond
        what `GET /invoices/{id}/payments` and `/refunds` already run.
        """
        invoice = self.get_invoice(invoice_id, requesting_user=requesting_user)
        customer = self.customer_repository.get_by_id(invoice.customer_id)
        payments = self.payment_repository.list_for_invoice(invoice.id)
        refunds = self.refund_repository.list_for_invoice(invoice.id)

        invoice.customer_name = customer.name if customer else None
        invoice.customer_email = customer.email if customer else None
        invoice.customer_country = customer.country if customer else None
        invoice.billing_address = customer.address if customer else None
        invoice.payment_method = payments[0].payment_method if payments else None
        invoice.discount_amount = sum(
            (li.amount for li in invoice.line_items if li.item_type == InvoiceLineItemType.DISCOUNT),
            Decimal("0"),
        )
        if invoice.status == InvoiceStatus.REFUNDED:
            invoice.refund_status = "full"
        elif refunds:
            invoice.refund_status = "partial"
        else:
            invoice.refund_status = "none"
        return invoice

    def list_invoices(
        self,
        customer_id: Optional[uuid.UUID] = None,
        subscription_id: Optional[uuid.UUID] = None,
        status: Optional[InvoiceStatus] = None,
        skip: int = 0,
        limit: int = 100,
        requesting_user: Optional[User] = None,
    ) -> List[Invoice]:
        effective_customer_id = effective_customer_filter(customer_id, requesting_user, self.db)
        return self.repository.list_all(
            effective_customer_id, subscription_id, status, skip, limit
        )

    def count_invoices(
        self,
        customer_id: Optional[uuid.UUID] = None,
        subscription_id: Optional[uuid.UUID] = None,
        status: Optional[InvoiceStatus] = None,
        requesting_user: Optional[User] = None,
    ) -> int:
        effective_customer_id = effective_customer_filter(customer_id, requesting_user, self.db)
        return self.repository.count_all(effective_customer_id, subscription_id, status)

    # ------------------------------------------------------------------
    # Generation: regular billing-cycle invoice
    # ------------------------------------------------------------------
    def generate_billing_invoice(
        self,
        subscription: Subscription,
        plan: Plan,
        customer: Customer,
        cycle: BillingCycle,
    ) -> Invoice:
        """
        Creates the invoice for a subscription's billing cycle renewal:
        one PLAN_FEE line item plus a TAX line item (if the customer's
        country has a configured tax rate).
        """
        tax_amount = TaxService(self.db).calculate_tax(plan.price, customer.country)
        total_amount = plan.price + tax_amount

        invoice = Invoice(
            invoice_number=_generate_invoice_number(cycle.cycle_start_date),
            subscription_id=subscription.id,
            billing_cycle_id=cycle.id,
            customer_id=subscription.customer_id,
            subtotal=plan.price,
            tax_amount=tax_amount,
            total_amount=total_amount,
            currency=plan.currency,
            status=InvoiceStatus.OPEN,
            due_date=cycle.cycle_end_date,
        )
        self.repository.add(invoice)

        self.repository.add_line_item(
            InvoiceLineItem(
                invoice_id=invoice.id,
                item_type=InvoiceLineItemType.PLAN_FEE,
                description=f"{plan.name} ({plan.billing_interval.value})",
                quantity=1,
                unit_price=plan.price,
                amount=plan.price,
            )
        )
        if tax_amount > 0:
            self.repository.add_line_item(
                InvoiceLineItem(
                    invoice_id=invoice.id,
                    item_type=InvoiceLineItemType.TAX,
                    description=f"Tax ({customer.country})",
                    quantity=1,
                    unit_price=tax_amount,
                    amount=tax_amount,
                )
            )

        self.audit_service.record(
            event_type=AuditEventType.INVOICE_GENERATED,
            entity_type="invoice",
            entity_id=invoice.id,
            description=f"Invoice {invoice.invoice_number} generated for billing cycle renewal",
            metadata={
                "subscription_id": str(subscription.id),
                "subtotal": str(plan.price),
                "tax_amount": str(tax_amount),
                "total_amount": str(total_amount),
            },
        )
        notify(
            "invoice_generated",
            subscription.customer_id,
            {
                "invoice_number": invoice.invoice_number,
                "amount": str(total_amount),
                "currency": invoice.currency,
                "due_date": cycle.cycle_end_date.strftime("%Y-%m-%d"),
            },
        )
        return invoice

    # ------------------------------------------------------------------
    # Generation: proration invoice (plan upgrade/downgrade mid-cycle)
    # ------------------------------------------------------------------
    def generate_proration_invoice(
        self,
        subscription: Subscription,
        customer: Customer,
        old_plan: Plan,
        new_plan: Plan,
        cycle: BillingCycle,
        calculation: ProrationCalculation,
    ) -> Optional[Invoice]:
        """
        Creates an invoice reflecting a mid-cycle plan change: a
        PRORATION_CREDIT line item for the unused portion of the old
        plan, a PRORATION_DEBIT line item for the new plan's remaining
        cost, and tax on the net positive amount (if any).

        Returns None if there is nothing to charge (net_amount <= 0);
        the unused credit in that case is not currently banked/carried
        forward as an account credit — see README known limitations.
        """
        if not calculation.applicable:
            return None

        # Void any existing OPEN/FAILED proration invoice for the same
        # subscription + billing cycle before creating the replacement.
        # This prevents a customer from accumulating multiple outstanding
        # proration invoices when they change plan more than once in the
        # same billing cycle (upgrade then downgrade, or repeated changes).
        stale = self.repository.get_open_proration_invoices(
            subscription.id, cycle.id
        )
        for stale_invoice in stale:
            stale_invoice.status = InvoiceStatus.VOID
            self.db.flush()
            self.audit_service.record(
                event_type=AuditEventType.PRORATION_APPLIED,
                entity_type="invoice",
                entity_id=stale_invoice.id,
                description=(
                    f"Stale proration invoice {stale_invoice.invoice_number} "
                    f"voided — superseded by new plan change"
                ),
                metadata={
                    "subscription_id": str(subscription.id),
                    "voided_by": "generate_proration_invoice",
                },
            )

        net_amount = calculation.net_amount
        if net_amount <= 0:
            # Downgrade / credit scenario: no invoice is generated, since
            # there is nothing to charge. Carrying the credit forward as
            # an account balance is out of scope for this module.
            self.audit_service.record(
                event_type=AuditEventType.PRORATION_APPLIED,
                entity_type="subscription",
                entity_id=subscription.id,
                description=(
                    "Proration calculated with no amount due "
                    f"(net credit of {abs(net_amount)}); no invoice generated"
                ),
                metadata={
                    "old_plan_id": str(old_plan.id),
                    "new_plan_id": str(new_plan.id),
                    "net_amount": str(net_amount),
                },
            )
            return None

        tax_amount = TaxService(self.db).calculate_tax(net_amount, customer.country)
        total_amount = net_amount + tax_amount

        invoice = Invoice(
            invoice_number=_generate_invoice_number(cycle.cycle_start_date),
            subscription_id=subscription.id,
            billing_cycle_id=cycle.id,
            customer_id=subscription.customer_id,
            subtotal=net_amount,
            tax_amount=tax_amount,
            total_amount=total_amount,
            currency=new_plan.currency,
            status=InvoiceStatus.OPEN,
            due_date=cycle.cycle_end_date,
        )
        self.repository.add(invoice)

        self.repository.add_line_item(
            InvoiceLineItem(
                invoice_id=invoice.id,
                item_type=InvoiceLineItemType.PRORATION_CREDIT,
                description=f"Unused credit: {old_plan.name}",
                quantity=1,
                unit_price=calculation.old_plan_unused_credit,
                amount=-calculation.old_plan_unused_credit,
            )
        )
        self.repository.add_line_item(
            InvoiceLineItem(
                invoice_id=invoice.id,
                item_type=InvoiceLineItemType.PRORATION_DEBIT,
                description=f"Remaining cost: {new_plan.name}",
                quantity=1,
                unit_price=calculation.new_plan_remaining_cost,
                amount=calculation.new_plan_remaining_cost,
            )
        )
        if tax_amount > 0:
            self.repository.add_line_item(
                InvoiceLineItem(
                    invoice_id=invoice.id,
                    item_type=InvoiceLineItemType.TAX,
                    description=f"Tax ({customer.country})",
                    quantity=1,
                    unit_price=tax_amount,
                    amount=tax_amount,
                )
            )

        self.audit_service.record(
            event_type=AuditEventType.PRORATION_APPLIED,
            entity_type="subscription",
            entity_id=subscription.id,
            description=(
                f"Proration invoice {invoice.invoice_number} generated for plan "
                f"change ({old_plan.name} -> {new_plan.name})"
            ),
            metadata={
                "old_plan_id": str(old_plan.id),
                "new_plan_id": str(new_plan.id),
                "net_amount": str(net_amount),
                "invoice_id": str(invoice.id),
            },
        )
        notify(
            "invoice_generated",
            subscription.customer_id,
            {
                "invoice_number": invoice.invoice_number,
                "amount": str(total_amount),
                "currency": invoice.currency,
                "due_date": cycle.cycle_end_date.strftime("%Y-%m-%d"),
            },
        )
        return invoice

    # ------------------------------------------------------------------
    # Line item / refund support
    # ------------------------------------------------------------------
    def add_refund_line_item(self, invoice: Invoice, amount: Decimal, description: str) -> InvoiceLineItem:
        line_item = InvoiceLineItem(
            invoice_id=invoice.id,
            item_type=InvoiceLineItemType.REFUND,
            description=description,
            quantity=1,
            unit_price=amount,
            amount=-amount,
        )
        return self.repository.add_line_item(line_item)
