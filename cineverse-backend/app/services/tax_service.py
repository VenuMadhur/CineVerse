"""
Tax Calculation module (Module 2, updated in Module 3 Phase 2a).

Originally a stateless, config-only lookup (settings.TAX_RATES).
Phase 2a replaces the rate *source* with the Tax Master table
(TaxRate/tax_rates), admin-manageable with effective-date ranges,
while keeping the exact same calculation math and rounding behavior
InvoiceService already relies on. settings.TAX_RATES/DEFAULT_TAX_RATE
remain as the final fallback for any country with no configured row
in the table, preserving identical behavior for anything not yet
migrated into the Tax Master table.
"""
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.repositories.tax_rate_repository import TaxRateRepository


class TaxService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = TaxRateRepository(db)

    def get_tax_rate(self, country_code: str, as_of: Optional[date] = None) -> Decimal:
        """
        Returns the applicable tax rate (as a decimal fraction, e.g.
        Decimal('0.08') for 8%) for the given ISO 3166-1 alpha-2
        country code. Looks up the Tax Master table first; falls back
        to settings.TAX_RATES / DEFAULT_TAX_RATE if no active,
        currently-effective row exists for that country.
        """
        as_of = as_of or datetime.now(timezone.utc).date()
        tax_rate_row = self.repository.get_effective_rate(country_code, as_of)
        if tax_rate_row is not None:
            return (tax_rate_row.tax_percentage / Decimal("100")).quantize(Decimal("0.0001"))

        fallback_rate = settings.TAX_RATES.get(country_code.upper(), settings.DEFAULT_TAX_RATE)
        return Decimal(str(fallback_rate))

    def calculate_tax(self, amount: Decimal, country_code: str) -> Decimal:
        """
        Calculates the tax amount for `amount`, rounded to 2 decimal
        places using standard half-up rounding (never negative).
        """
        if amount <= 0:
            return Decimal("0.00")
        rate = self.get_tax_rate(country_code)
        tax = (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return tax
