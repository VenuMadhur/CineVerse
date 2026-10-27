"""
Data access layer for the Refund entity.
"""
import uuid
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import RefundStatus
from app.models.refund import Refund
from app.repositories.base_repository import BaseRepository


class RefundRepository(BaseRepository[Refund]):
    def __init__(self, db: Session):
        super().__init__(Refund, db)

    def list_for_invoice(self, invoice_id: uuid.UUID) -> List[Refund]:
        stmt = (
            select(Refund)
            .where(Refund.invoice_id == invoice_id)
            .order_by(Refund.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def _filtered_query(
        self,
        customer_id: Optional[uuid.UUID] = None,
        invoice_id: Optional[uuid.UUID] = None,
        status: Optional[RefundStatus] = None,
    ):
        stmt = select(Refund)
        if customer_id is not None:
            stmt = stmt.where(Refund.customer_id == customer_id)
        if invoice_id is not None:
            stmt = stmt.where(Refund.invoice_id == invoice_id)
        if status is not None:
            stmt = stmt.where(Refund.status == status)
        return stmt

    def list_all(
        self,
        customer_id: Optional[uuid.UUID] = None,
        invoice_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 100,
        status: Optional[RefundStatus] = None,
    ) -> List[Refund]:
        stmt = (
            self._filtered_query(customer_id, invoice_id, status)
            .order_by(Refund.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_all(
        self,
        customer_id: Optional[uuid.UUID] = None,
        invoice_id: Optional[uuid.UUID] = None,
        status: Optional[RefundStatus] = None,
    ) -> int:
        stmt = select(func.count()).select_from(
            self._filtered_query(customer_id, invoice_id, status).subquery()
        )
        return self.db.execute(stmt).scalar_one()

    # ------------------------------------------------------------------
    # Analytics (Phase 2)
    # ------------------------------------------------------------------
    def sum_amount(self, status: Optional[RefundStatus] = None) -> Decimal:
        stmt = select(func.coalesce(func.sum(Refund.amount), 0))
        if status is not None:
            stmt = stmt.where(Refund.status == status)
        return self.db.execute(stmt).scalar_one()

    def sum_amount_by_currency(self, status: Optional[RefundStatus] = None) -> List[tuple]:
        """
        Same figure as sum_amount(), broken out by Refund.currency
        instead of blindly summed across all of them.
        """
        stmt = select(Refund.currency, func.sum(Refund.amount))
        if status is not None:
            stmt = stmt.where(Refund.status == status)
        stmt = stmt.group_by(Refund.currency).order_by(func.sum(Refund.amount).desc())
        return list(self.db.execute(stmt).all())

    def refund_trend_by_month(self, date_from=None, date_to=None) -> List[tuple]:
        """
        Returns (month, refund_count, refund_amount) rows, ordered
        chronologically. Mirrors InvoiceRepository.revenue_by_month's
        exact pattern (func.date_trunc grouping) and the same
        completed-only filter logic (revenue_by_month only counts
        PAID invoices; this only counts COMPLETED refunds). Grouped by
        Refund.processed_at -- when the refund actually completed, not
        Refund.created_at (when it was merely requested) -- a PENDING
        refund has no processed_at and is correctly excluded, since it
        hasn't actually happened yet.
        """
        month_expr = func.date_trunc("month", Refund.processed_at)
        stmt = (
            select(month_expr.label("month"), func.count(Refund.id), func.sum(Refund.amount))
            .where(Refund.status == RefundStatus.COMPLETED)
            .group_by(month_expr)
            .order_by(month_expr)
        )
        if date_from is not None:
            stmt = stmt.where(Refund.processed_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Refund.processed_at <= date_to)
        return list(self.db.execute(stmt).all())
