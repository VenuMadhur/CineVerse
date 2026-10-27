"""
Data access layer for the RetryQueue entity.

Nothing in the application creates or consumes RetryQueue rows yet --
that's the Phase 1b scheduler. This repository exists now so Phase 1b
can be built without touching the data-access layer again, consistent
with completing the data model in one self-contained phase.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import RetryStatus
from app.models.retry_queue import RetryQueue
from app.repositories.base_repository import BaseRepository


class RetryQueueRepository(BaseRepository[RetryQueue]):
    def __init__(self, db: Session):
        super().__init__(RetryQueue, db)

    def get_by_id(self, retry_id: uuid.UUID) -> Optional[RetryQueue]:
        return super().get_by_id(retry_id)

    def list_all(
        self,
        customer_id: Optional[uuid.UUID] = None,
        invoice_id: Optional[uuid.UUID] = None,
        retry_status: Optional[RetryStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[RetryQueue]:
        stmt = select(RetryQueue).options(
            selectinload(RetryQueue.customer), selectinload(RetryQueue.invoice)
        )
        if customer_id is not None:
            stmt = stmt.where(RetryQueue.customer_id == customer_id)
        if invoice_id is not None:
            stmt = stmt.where(RetryQueue.invoice_id == invoice_id)
        if retry_status is not None:
            stmt = stmt.where(RetryQueue.retry_status == retry_status)
        stmt = stmt.order_by(RetryQueue.scheduled_retry_date.asc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count_all(
        self,
        customer_id: Optional[uuid.UUID] = None,
        invoice_id: Optional[uuid.UUID] = None,
        retry_status: Optional[RetryStatus] = None,
    ) -> int:
        stmt = select(func.count()).select_from(RetryQueue)
        if customer_id is not None:
            stmt = stmt.where(RetryQueue.customer_id == customer_id)
        if invoice_id is not None:
            stmt = stmt.where(RetryQueue.invoice_id == invoice_id)
        if retry_status is not None:
            stmt = stmt.where(RetryQueue.retry_status == retry_status)
        return self.db.execute(stmt).scalar_one()

    def list_due(self, as_of: datetime) -> List[RetryQueue]:
        """
        For the future Phase 1b scheduler: pending retries whose
        scheduled_retry_date has arrived.
        """
        stmt = select(RetryQueue).where(
            RetryQueue.retry_status == RetryStatus.PENDING,
            RetryQueue.scheduled_retry_date <= as_of,
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_pending_for_invoice(self, invoice_id: uuid.UUID) -> List[RetryQueue]:
        """
        For the future Phase 1b scheduler: used to cancel remaining
        scheduled retries once a payment succeeds.
        """
        stmt = select(RetryQueue).where(
            RetryQueue.invoice_id == invoice_id,
            RetryQueue.retry_status == RetryStatus.PENDING,
        )
        return list(self.db.execute(stmt).scalars().all())
