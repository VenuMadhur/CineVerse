"""
Data access layer for the Invoice and InvoiceLineItem entities.
"""
import uuid
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.customer import Customer
from app.models.enums import InvoiceLineItemType, InvoiceStatus, PaymentStatus
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.repositories.base_repository import BaseRepository


class InvoiceRepository(BaseRepository[Invoice]):
    def __init__(self, db: Session):
        super().__init__(Invoice, db)

    def get_by_id(self, invoice_id: uuid.UUID) -> Optional[Invoice]:
        stmt = (
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .options(selectinload(Invoice.line_items))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_invoice_number(self, invoice_number: str) -> Optional[Invoice]:
        stmt = select(Invoice).where(Invoice.invoice_number == invoice_number)
        return self.db.execute(stmt).scalar_one_or_none()

    def _filtered_query(
        self,
        customer_id: Optional[uuid.UUID] = None,
        subscription_id: Optional[uuid.UUID] = None,
        status: Optional[InvoiceStatus] = None,
    ):
        stmt = select(Invoice)
        if customer_id is not None:
            stmt = stmt.where(Invoice.customer_id == customer_id)
        if subscription_id is not None:
            stmt = stmt.where(Invoice.subscription_id == subscription_id)
        if status is not None:
            stmt = stmt.where(Invoice.status == status)
        return stmt

    def list_all(
        self,
        customer_id: Optional[uuid.UUID] = None,
        subscription_id: Optional[uuid.UUID] = None,
        status: Optional[InvoiceStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Invoice]:
        stmt = (
            self._filtered_query(customer_id, subscription_id, status)
            .order_by(Invoice.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_all(
        self,
        customer_id: Optional[uuid.UUID] = None,
        subscription_id: Optional[uuid.UUID] = None,
        status: Optional[InvoiceStatus] = None,
    ) -> int:
        stmt = select(func.count()).select_from(
            self._filtered_query(customer_id, subscription_id, status).subquery()
        )
        return self.db.execute(stmt).scalar_one()

    def add_line_item(self, line_item: InvoiceLineItem) -> InvoiceLineItem:
        self.db.add(line_item)
        self.db.flush()
        return line_item

    def get_open_proration_invoices(
        self,
        subscription_id: uuid.UUID,
        billing_cycle_id: uuid.UUID,
    ) -> List[Invoice]:
        """
        Returns every OPEN or FAILED invoice for the given subscription
        and billing cycle that contains at least one PRORATION_DEBIT
        line item. Used by InvoiceService to void stale proration
        invoices before creating a replacement (the proration-bug fix).
        Using a subquery/EXISTS rather than a join avoids returning
        duplicate Invoice rows when an invoice has several proration
        line items.
        """
        proration_exists = (
            select(InvoiceLineItem.invoice_id)
            .where(
                InvoiceLineItem.invoice_id == Invoice.id,
                InvoiceLineItem.item_type == InvoiceLineItemType.PRORATION_DEBIT,
            )
            .correlate(Invoice)
            .exists()
        )
        stmt = (
            select(Invoice)
            .where(
                Invoice.subscription_id == subscription_id,
                Invoice.billing_cycle_id == billing_cycle_id,
                Invoice.status.in_([InvoiceStatus.OPEN, InvoiceStatus.FAILED]),
                proration_exists,
            )
            .options(selectinload(Invoice.line_items))
        )
        return list(self.db.execute(stmt).scalars().all())

    # ------------------------------------------------------------------
    # Analytics (Phase 2)
    # ------------------------------------------------------------------
    def sum_paid_amount(self, date_from=None, date_to=None) -> Decimal:
        """
        Total revenue recognized: the sum of `total_amount` across
        currently-`paid` invoices. Since a refund reduces
        `total_amount` directly (and flips status away from PAID once
        fully refunded), this always reflects the net amount actually
        retained -- not gross billings.
        """
        stmt = select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(
            Invoice.status == InvoiceStatus.PAID
        )
        if date_from is not None:
            stmt = stmt.where(Invoice.paid_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Invoice.paid_at <= date_to)
        return self.db.execute(stmt).scalar_one()

    def paid_amount_by_currency(self, date_from=None, date_to=None) -> List[tuple]:
        """
        Same figure as sum_paid_amount(), broken out by currency
        instead of blindly summed across all of them. Invoice.currency
        is per-invoice (ultimately from Plan.currency, which is
        unconstrained -- nothing stops an admin from creating a plan
        in a different currency), so a single blended total is
        potentially meaningless/misleading the moment more than one
        currency is genuinely in use. Mirrors revenue_by_country's
        exact shape, just grouped by currency instead of country.
        """
        stmt = (
            select(Invoice.currency, func.sum(Invoice.total_amount))
            .where(Invoice.status == InvoiceStatus.PAID)
            .group_by(Invoice.currency)
            .order_by(func.sum(Invoice.total_amount).desc())
        )
        if date_from is not None:
            stmt = stmt.where(Invoice.paid_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Invoice.paid_at <= date_to)
        return list(self.db.execute(stmt).all())

    def revenue_by_month(self, date_from=None, date_to=None) -> List[tuple]:
        """Returns (month, revenue) rows, ordered chronologically."""
        month_expr = func.date_trunc("month", Invoice.paid_at)
        stmt = (
            select(month_expr.label("month"), func.sum(Invoice.total_amount))
            .where(Invoice.status == InvoiceStatus.PAID)
            .group_by(month_expr)
            .order_by(month_expr)
        )
        if date_from is not None:
            stmt = stmt.where(Invoice.paid_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Invoice.paid_at <= date_to)
        return list(self.db.execute(stmt).all())

    def revenue_by_plan(self, date_from=None, date_to=None) -> List[tuple]:
        """Returns (plan_id, plan_name, revenue) rows, highest revenue first."""
        stmt = (
            select(Plan.id, Plan.name, func.sum(Invoice.total_amount))
            .join(Subscription, Subscription.id == Invoice.subscription_id)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(Invoice.status == InvoiceStatus.PAID)
            .group_by(Plan.id, Plan.name)
            .order_by(func.sum(Invoice.total_amount).desc())
        )
        if date_from is not None:
            stmt = stmt.where(Invoice.paid_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Invoice.paid_at <= date_to)
        return list(self.db.execute(stmt).all())

    # ------------------------------------------------------------------
    # Revenue & Invoice Analytics (Module 3, Phase 3b)
    #
    # revenue_by_day/year mirror revenue_by_month exactly, just at a
    # different date_trunc granularity. revenue_by_country/
    # payment_method mirror the exact join patterns already used by
    # Phase 2b's tax_by_country/tax_by_payment_method, summing
    # total_amount instead of tax_amount.
    # ------------------------------------------------------------------
    def revenue_by_day(self, date_from=None, date_to=None) -> List[tuple]:
        """Returns (day, revenue) rows, chronological."""
        day_expr = func.date_trunc("day", Invoice.paid_at)
        stmt = (
            select(day_expr.label("day"), func.sum(Invoice.total_amount))
            .where(Invoice.status == InvoiceStatus.PAID)
            .group_by(day_expr)
            .order_by(day_expr)
        )
        if date_from is not None:
            stmt = stmt.where(Invoice.paid_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Invoice.paid_at <= date_to)
        return list(self.db.execute(stmt).all())

    def revenue_by_year(self, date_from=None, date_to=None) -> List[tuple]:
        """Returns (year, revenue) rows, chronological."""
        year_expr = func.date_trunc("year", Invoice.paid_at)
        stmt = (
            select(year_expr.label("year"), func.sum(Invoice.total_amount))
            .where(Invoice.status == InvoiceStatus.PAID)
            .group_by(year_expr)
            .order_by(year_expr)
        )
        if date_from is not None:
            stmt = stmt.where(Invoice.paid_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Invoice.paid_at <= date_to)
        return list(self.db.execute(stmt).all())

    def revenue_by_country(self, date_from=None, date_to=None) -> List[tuple]:
        """Returns (country, revenue) rows, highest first."""
        stmt = (
            select(Customer.country, func.sum(Invoice.total_amount))
            .join(Customer, Customer.id == Invoice.customer_id)
            .where(Invoice.status == InvoiceStatus.PAID)
            .group_by(Customer.country)
            .order_by(func.sum(Invoice.total_amount).desc())
        )
        if date_from is not None:
            stmt = stmt.where(Invoice.paid_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Invoice.paid_at <= date_to)
        return list(self.db.execute(stmt).all())

    def revenue_by_payment_method(self, date_from=None, date_to=None) -> List[tuple]:
        """
        Returns (payment_method, revenue) rows, highest first. Joins
        only SUCCEEDED payments, same reasoning as
        tax_by_payment_method (Phase 2b): only a successful attempt's
        method is meaningful for "how was this revenue collected."
        """
        stmt = (
            select(Payment.payment_method, func.sum(Invoice.total_amount))
            .join(Payment, Payment.invoice_id == Invoice.id)
            .where(
                Invoice.status == InvoiceStatus.PAID,
                Payment.status == PaymentStatus.SUCCEEDED,
            )
            .group_by(Payment.payment_method)
            .order_by(func.sum(Invoice.total_amount).desc())
        )
        if date_from is not None:
            stmt = stmt.where(Invoice.paid_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Invoice.paid_at <= date_to)
        return list(self.db.execute(stmt).all())

    def count_by_status(self) -> dict:
        """Returns {InvoiceStatus: count} for every status, current totals (not date-ranged)."""
        stmt = select(Invoice.status, func.count()).group_by(Invoice.status)
        return dict(self.db.execute(stmt).all())

    def sum_outstanding_amount(self) -> Decimal:
        """
        Total amount currently owed and not yet collected: OPEN
        (awaiting payment) or FAILED (payment attempt failed, may
        still be retried) invoices. PAID/VOID/REFUNDED/DRAFT are
        correctly excluded -- nothing is "outstanding" for those.
        """
        stmt = select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(
            Invoice.status.in_([InvoiceStatus.OPEN, InvoiceStatus.FAILED])
        )
        return self.db.execute(stmt).scalar_one()

    def average_invoice_amount(self) -> Decimal:
        """Average total_amount across every invoice ever issued (any status)."""
        stmt = select(func.coalesce(func.avg(Invoice.total_amount), 0))
        return self.db.execute(stmt).scalar_one()

    def top_paying_customers(self, limit: int = 20) -> List[tuple]:
        """
        Returns (customer_id, customer_name, customer_email, total_paid)
        rows, highest first -- mirrors tax_by_customer's exact join/
        group-by shape, summing total_amount instead of tax_amount.
        """
        stmt = (
            select(Customer.id, Customer.name, Customer.email, func.sum(Invoice.total_amount))
            .join(Customer, Customer.id == Invoice.customer_id)
            .where(Invoice.status == InvoiceStatus.PAID)
            .group_by(Customer.id, Customer.name, Customer.email)
            .order_by(func.sum(Invoice.total_amount).desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).all())

    # ------------------------------------------------------------------
    # Tax Reports (Module 3, Phase 2b)
    #
    # All 6 methods below mirror revenue_by_month/revenue_by_plan
    # exactly -- same PAID-invoice scoping, same paid_at date-range
    # filtering, same join patterns -- summing Invoice.tax_amount
    # instead of total_amount. tax_amount is already the correct,
    # final tax figure computed by TaxService (Phase 2a) at invoice
    # generation time; nothing here recalculates tax, only aggregates
    # what's already stored.
    # ------------------------------------------------------------------
    def tax_collection_by_period(self, period: str, date_from=None, date_to=None) -> List[tuple]:
        """
        Returns (period_start, tax_collected) rows, chronological.
        `period` is one of "day", "week", "month", "year" (validated
        by the caller -- passed straight to Postgres's date_trunc).
        """
        period_expr = func.date_trunc(period, Invoice.paid_at)
        stmt = (
            select(period_expr.label("period"), func.sum(Invoice.tax_amount))
            .where(Invoice.status == InvoiceStatus.PAID)
            .group_by(period_expr)
            .order_by(period_expr)
        )
        if date_from is not None:
            stmt = stmt.where(Invoice.paid_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Invoice.paid_at <= date_to)
        return list(self.db.execute(stmt).all())

    def tax_by_country(self, date_from=None, date_to=None) -> List[tuple]:
        """Returns (country, tax_collected) rows, highest first."""
        stmt = (
            select(Customer.country, func.sum(Invoice.tax_amount))
            .join(Customer, Customer.id == Invoice.customer_id)
            .where(Invoice.status == InvoiceStatus.PAID)
            .group_by(Customer.country)
            .order_by(func.sum(Invoice.tax_amount).desc())
        )
        if date_from is not None:
            stmt = stmt.where(Invoice.paid_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Invoice.paid_at <= date_to)
        return list(self.db.execute(stmt).all())

    def tax_by_state(self, date_from=None, date_to=None) -> List[tuple]:
        """
        Returns (state, tax_collected) rows, highest first. Customers
        with no state set (Phase 2b's `state` column is optional) are
        excluded -- there's nothing meaningful to group them under.
        """
        stmt = (
            select(Customer.state, func.sum(Invoice.tax_amount))
            .join(Customer, Customer.id == Invoice.customer_id)
            .where(Invoice.status == InvoiceStatus.PAID, Customer.state.is_not(None))
            .group_by(Customer.state)
            .order_by(func.sum(Invoice.tax_amount).desc())
        )
        if date_from is not None:
            stmt = stmt.where(Invoice.paid_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Invoice.paid_at <= date_to)
        return list(self.db.execute(stmt).all())

    def tax_by_plan(self, date_from=None, date_to=None) -> List[tuple]:
        """Returns (plan_id, plan_name, tax_collected) rows, highest first."""
        stmt = (
            select(Plan.id, Plan.name, func.sum(Invoice.tax_amount))
            .join(Subscription, Subscription.id == Invoice.subscription_id)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(Invoice.status == InvoiceStatus.PAID)
            .group_by(Plan.id, Plan.name)
            .order_by(func.sum(Invoice.tax_amount).desc())
        )
        if date_from is not None:
            stmt = stmt.where(Invoice.paid_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Invoice.paid_at <= date_to)
        return list(self.db.execute(stmt).all())

    def tax_by_customer(self, date_from=None, date_to=None) -> List[tuple]:
        """Returns (customer_id, customer_name, tax_collected) rows, highest first."""
        stmt = (
            select(Customer.id, Customer.name, func.sum(Invoice.tax_amount))
            .join(Customer, Customer.id == Invoice.customer_id)
            .where(Invoice.status == InvoiceStatus.PAID)
            .group_by(Customer.id, Customer.name)
            .order_by(func.sum(Invoice.tax_amount).desc())
        )
        if date_from is not None:
            stmt = stmt.where(Invoice.paid_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Invoice.paid_at <= date_to)
        return list(self.db.execute(stmt).all())

    def tax_by_payment_method(self, date_from=None, date_to=None) -> List[tuple]:
        """
        Returns (payment_method, tax_collected) rows, highest first.
        Joins only SUCCEEDED payments -- an invoice can have multiple
        retry attempts (Module 3, Phase 1), and only a successful
        attempt's method is meaningful for "how was this tax actually
        collected."
        """
        stmt = (
            select(Payment.payment_method, func.sum(Invoice.tax_amount))
            .join(Payment, Payment.invoice_id == Invoice.id)
            .where(
                Invoice.status == InvoiceStatus.PAID,
                Payment.status == PaymentStatus.SUCCEEDED,
            )
            .group_by(Payment.payment_method)
            .order_by(func.sum(Invoice.tax_amount).desc())
        )
        if date_from is not None:
            stmt = stmt.where(Invoice.paid_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Invoice.paid_at <= date_to)
        return list(self.db.execute(stmt).all())
