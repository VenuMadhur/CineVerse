"""
Data access layer for the Payment entity.
"""
import uuid
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.enums import PaymentStatus
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.repositories.base_repository import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    def __init__(self, db: Session):
        super().__init__(Payment, db)

    def get_by_gateway_reference(self, gateway_reference: str) -> Optional[Payment]:
        stmt = select(Payment).where(Payment.gateway_reference == gateway_reference)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_invoice(self, invoice_id: uuid.UUID) -> List[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.invoice_id == invoice_id)
            .order_by(Payment.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_for_invoice(self, invoice_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(Payment).where(Payment.invoice_id == invoice_id)
        return self.db.execute(stmt).scalar_one()

    def _filtered_query(
        self,
        invoice_id: Optional[uuid.UUID] = None,
        customer_id: Optional[uuid.UUID] = None,
        status: Optional[PaymentStatus] = None,
        date_from=None,
        date_to=None,
    ):
        stmt = select(Payment)
        # Payment has no customer_id column of its own -- it belongs to an
        # Invoice, which belongs to a Customer -- so filtering "my
        # payments" requires joining through Invoice. This mirrors the
        # customer_id support already on GET /invoices and GET /refunds.
        if customer_id is not None:
            stmt = stmt.join(Invoice, Invoice.id == Payment.invoice_id).where(
                Invoice.customer_id == customer_id
            )
        if invoice_id is not None:
            stmt = stmt.where(Payment.invoice_id == invoice_id)
        if status is not None:
            stmt = stmt.where(Payment.status == status)
        if date_from is not None:
            stmt = stmt.where(func.coalesce(Payment.processed_at, Payment.created_at) >= date_from)
        if date_to is not None:
            stmt = stmt.where(func.coalesce(Payment.processed_at, Payment.created_at) <= date_to)
        return stmt

    def list_all(
        self,
        invoice_id: Optional[uuid.UUID] = None,
        customer_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 100,
        status: Optional[PaymentStatus] = None,
        date_from=None,
        date_to=None,
    ) -> List[Payment]:
        stmt = (
            self._filtered_query(invoice_id, customer_id, status, date_from, date_to)
            .order_by(Payment.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_all(
        self,
        invoice_id: Optional[uuid.UUID] = None,
        customer_id: Optional[uuid.UUID] = None,
        status: Optional[PaymentStatus] = None,
        date_from=None,
        date_to=None,
    ) -> int:
        stmt = select(func.count()).select_from(
            self._filtered_query(invoice_id, customer_id, status, date_from, date_to).subquery()
        )
        return self.db.execute(stmt).scalar_one()

    # ------------------------------------------------------------------
    # Analytics (Phase 2)
    # ------------------------------------------------------------------
    def monthly_trend(
        self, date_from=None, date_to=None
    ) -> List[tuple]:
        """
        Returns (month, status, count) rows grouped by calendar month
        (based on `processed_at`, falling back to `created_at` for any
        payment somehow never marked processed) and status -- the raw
        material for "payment trends". Ordered chronologically.
        """
        month_expr = func.date_trunc(
            "month", func.coalesce(Payment.processed_at, Payment.created_at)
        )
        stmt = select(month_expr.label("month"), Payment.status, func.count()).group_by(
            month_expr, Payment.status
        ).order_by(month_expr)

        if date_from is not None:
            stmt = stmt.where(func.coalesce(Payment.processed_at, Payment.created_at) >= date_from)
        if date_to is not None:
            stmt = stmt.where(func.coalesce(Payment.processed_at, Payment.created_at) <= date_to)

        return list(self.db.execute(stmt).all())

    def customers_with_failed_payments(self) -> List[tuple]:
        """
        Returns (customer_id, customer_name, customer_email,
        failed_count, most_recent_failure) rows for Module 3, Phase
        3c's "Customers with Failed Payments" report, highest failure
        count first.
        """
        stmt = (
            select(
                Customer.id,
                Customer.name,
                Customer.email,
                func.count(),
                func.max(func.coalesce(Payment.processed_at, Payment.created_at)),
            )
            .join(Invoice, Invoice.id == Payment.invoice_id)
            .join(Customer, Customer.id == Invoice.customer_id)
            .where(Payment.status == PaymentStatus.FAILED)
            .group_by(Customer.id, Customer.name, Customer.email)
            .order_by(func.count().desc())
        )
        return list(self.db.execute(stmt).all())
