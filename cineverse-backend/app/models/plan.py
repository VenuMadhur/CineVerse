"""
Plan model: subscription plan definitions (pricing, billing interval,
trial period, feature entitlements).
"""
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base
from app.models.enums import BillingInterval, PlanStatus

if TYPE_CHECKING:
    from app.models.subscription import Subscription


class Plan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    billing_interval: Mapped[BillingInterval] = mapped_column(
        SAEnum(BillingInterval, name="billing_interval_enum"),
        nullable=False,
        default=BillingInterval.MONTHLY,
    )

    trial_period_days: Mapped[int] = mapped_column(nullable=False, default=0)

    # Feature entitlements stored as flexible JSON, e.g.
    # {"api_calls": 10000, "seats": 5, "storage_gb": 50}
    feature_entitlements: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    status: Mapped[PlanStatus] = mapped_column(
        SAEnum(PlanStatus, name="plan_status_enum"),
        nullable=False,
        default=PlanStatus.ACTIVE,
        index=True,
    )

    subscriptions: Mapped[List["Subscription"]] = relationship(
        "Subscription", back_populates="plan"
    )

    def __repr__(self) -> str:
        return f"<Plan id={self.id} name={self.name!r} status={self.status}>"
