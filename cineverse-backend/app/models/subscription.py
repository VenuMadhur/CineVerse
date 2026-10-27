"""
Subscription model and its status-history audit table.

The Subscription table stores current state plus denormalized
timestamp columns (trial_started_at, activated_at, etc.) for fast
access, while SubscriptionStatusHistory keeps a full append-only
log of every transition for compliance / debugging.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from app.core.database import Base
from app.models.enums import CancellationType, SubscriptionStatus

if TYPE_CHECKING:
    from app.models.billing_cycle import BillingCycle
    from app.models.customer import Customer
    from app.models.plan import Plan


class Subscription(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, name="subscription_status_enum"),
        nullable=False,
        default=SubscriptionStatus.TRIAL,
        index=True,
    )

    # ---- Lifecycle timestamps ----
    trial_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    past_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paused_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # If the customer has requested end-of-cycle cancellation, this flag
    # marks the subscription for cancellation once the current cycle ends.
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False, nullable=False)
    cancellation_type: Mapped[Optional[CancellationType]] = mapped_column(
        SAEnum(CancellationType, name="cancellation_type_enum"), nullable=True
    )

    customer: Mapped["Customer"] = relationship(
        "Customer", back_populates="subscriptions"
    )
    plan: Mapped["Plan"] = relationship("Plan", back_populates="subscriptions")

    billing_cycles: Mapped[List["BillingCycle"]] = relationship(
        "BillingCycle",
        back_populates="subscription",
        order_by="BillingCycle.cycle_start_date",
    )

    status_history: Mapped[List["SubscriptionStatusHistory"]] = relationship(
        "SubscriptionStatusHistory",
        back_populates="subscription",
        order_by="SubscriptionStatusHistory.created_at",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Subscription id={self.id} status={self.status}>"


class SubscriptionStatusHistory(Base, UUIDPrimaryKeyMixin):
    """Append-only log of every subscription status transition."""

    __tablename__ = "subscription_status_history"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[Optional[SubscriptionStatus]] = mapped_column(
        SAEnum(SubscriptionStatus, name="subscription_status_enum"), nullable=True
    )
    to_status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, name="subscription_status_enum"), nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    subscription: Mapped["Subscription"] = relationship(
        "Subscription", back_populates="status_history"
    )

    def __repr__(self) -> str:
        return (
            f"<SubscriptionStatusHistory {self.from_status} -> "
            f"{self.to_status} at {self.created_at}>"
        )
