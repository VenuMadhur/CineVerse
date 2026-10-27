"""
Customer model.

Phase 1A: `user_id` links a Customer to the User account that owns it
(nullable -- not every Customer necessarily has a self-service login;
managed/admin-created accounts may have none). This is the ownership
foundation only -- no authorization logic reads this column yet.
"""
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.subscription import Subscription
    from app.models.user import User


class Customer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)  # ISO 3166-1 alpha-2
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Module 3, Phase 2b: nullable, optional -- no existing customer is
    # required to have one. Used for reporting (State-wise Tax) and
    # future extensibility; not used anywhere in tax rate *lookup*
    # today (TaxService still matches by country only).
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )

    subscriptions: Mapped[List["Subscription"]] = relationship(
        "Subscription", back_populates="customer"
    )
    # Lazy ("select") loading only -- deliberately not eager (no
    # "joined"/"selectin"/"subquery") so existing queries that load a
    # Customer are not affected by an extra implicit join/query.
    user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="customer", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Customer id={self.id} email={self.email!r}>"
