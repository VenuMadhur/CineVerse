"""
RetryConfiguration model (Module 3, Phase 1a).

Defines the failed-payment retry schedule: for each retry attempt
number (1, 2, 3, ...), how many days after the payment first failed
that attempt should run. Admin-configurable so the default 1/3/7-day
schedule from the Module 3 spec can be adjusted without a code change.

This phase only covers the table + CRUD. The Celery Beat scheduler
that actually consumes this configuration to drive retries is a
later phase (1b) and does not exist yet.
"""
from sqlalchemy import Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class RetryConfiguration(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "retry_configurations"
    __table_args__ = (
        UniqueConstraint("retry_attempt", name="uq_retry_configurations_retry_attempt"),
    )

    retry_attempt: Mapped[int] = mapped_column(nullable=False, index=True)
    retry_after_days: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return (
            f"<RetryConfiguration attempt={self.retry_attempt} "
            f"after_days={self.retry_after_days} active={self.is_active}>"
        )
