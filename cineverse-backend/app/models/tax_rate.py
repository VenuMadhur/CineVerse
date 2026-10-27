"""
TaxRate model (Module 3, Phase 2a) -- the Tax Master table.

Replaces the previous Module 2 approach of tax rates living only in
settings.TAX_RATES (a Python dict from env config) with an
admin-manageable database table supporting effective-date ranges.

`state` is included for future-readiness per the Module 3 spec's data
model, but Customer has no `state` field today -- TaxService's actual
rate lookup (Phase 2a) matches by `country` only. Nothing prevents
adding state-level precision later without a schema change here.
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class TaxRate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tax_rates"

    country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)  # ISO 3166-1 alpha-2
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tax_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "GST", "VAT", "Sales Tax"
    tax_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return (
            f"<TaxRate country={self.country} state={self.state} "
            f"percentage={self.tax_percentage} active={self.is_active}>"
        )
