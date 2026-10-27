"""
RetryQueue model (Module 3, Phase 1a).

One row per scheduled retry attempt for a failed invoice payment. The
spec's "retry_id" field is this model's standard `id` primary key,
matching every other model in this codebase (Refund, Payment, etc. all
use `id`, not e.g. `refund_id`) rather than introducing a new naming
convention for just this one table.

This phase only covers the table + repository. Nothing creates rows
in this table yet, and no scheduler consumes it -- that's Phase 1b.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base
from app.models.enums import RetryStatus

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.invoice import Invoice
    from app.models.payment import Payment


class RetryQueue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "retry_queue"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The payment attempt that failed and triggered this retry entry.
    # Nullable: a retry entry conceptually belongs to an invoice that
    # needs to be paid, and while in practice it will almost always be
    # created right after a specific failed Payment, requiring it
    # would tie the retry queue's existence too tightly to a payment
    # attempt having happened at all.
    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    retry_attempt: Mapped[int] = mapped_column(nullable=False)
    scheduled_retry_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    actual_retry_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retry_status: Mapped[RetryStatus] = mapped_column(
        SAEnum(RetryStatus, name="retry_status_enum"),
        nullable=False,
        default=RetryStatus.PENDING,
        index=True,
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    next_retry_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    invoice: Mapped["Invoice"] = relationship("Invoice")
    payment: Mapped[Optional["Payment"]] = relationship("Payment")
    customer: Mapped["Customer"] = relationship("Customer")

    def __repr__(self) -> str:
        return (
            f"<RetryQueue id={self.id} invoice_id={self.invoice_id} "
            f"attempt={self.retry_attempt} status={self.retry_status}>"
        )
