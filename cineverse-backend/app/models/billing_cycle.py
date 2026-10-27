"""
BillingCycle model: tracks each billing period for a subscription.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.invoice import Invoice
    from app.models.subscription import Subscription


class BillingCycle(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "billing_cycles"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    cycle_start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    cycle_end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    renewal_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    next_billing_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    is_billed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    subscription: Mapped["Subscription"] = relationship(
        "Subscription", back_populates="billing_cycles"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="billing_cycle"
    )

    def __repr__(self) -> str:
        return (
            f"<BillingCycle id={self.id} "
            f"{self.cycle_start_date} -> {self.cycle_end_date}>"
        )
