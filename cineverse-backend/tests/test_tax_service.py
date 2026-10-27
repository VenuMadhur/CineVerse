"""
Unit tests for TaxService (Module 3, Phase 2a): Tax Master table
lookup first, falling back to settings.TAX_RATES/DEFAULT_TAX_RATE for
any country with no configured, currently-effective row -- confirming
identical behavior to the pre-Phase-2a config-only implementation for
anything not yet migrated into the table.
"""
from datetime import date, timedelta
from decimal import Decimal

from app.models.tax_rate import TaxRate
from app.services.tax_service import TaxService


def test_known_country_rate_falls_back_to_settings_when_no_table_row(db_session):
    """No TaxRate rows exist yet -- exercises the fallback path,
    confirming identical behavior to the pre-Phase-2a implementation."""
    service = TaxService(db_session)
    assert service.get_tax_rate("US") == Decimal("0.08")
    assert service.get_tax_rate("IN") == Decimal("0.18")


def test_country_code_case_insensitive(db_session):
    service = TaxService(db_session)
    assert service.get_tax_rate("us") == service.get_tax_rate("US")


def test_unknown_country_falls_back_to_default(db_session):
    service = TaxService(db_session)
    assert service.get_tax_rate("ZZ") == Decimal("0.00")


def test_calculate_tax_rounds_half_up(db_session):
    service = TaxService(db_session)
    tax = service.calculate_tax(Decimal("100.00"), "US")
    assert tax == Decimal("8.00")


def test_calculate_tax_zero_for_negative_or_zero_amount(db_session):
    service = TaxService(db_session)
    assert service.calculate_tax(Decimal("0"), "US") == Decimal("0.00")
    assert service.calculate_tax(Decimal("-5"), "US") == Decimal("0.00")


def test_calculate_tax_for_country_with_no_configured_rate(db_session):
    service = TaxService(db_session)
    tax = service.calculate_tax(Decimal("100.00"), "ZZ")
    assert tax == Decimal("0.00")


# ---------------------------------------------------------------------
# Tax Master table lookup (new in Phase 2a)
# ---------------------------------------------------------------------


def _add_tax_rate(db_session, **overrides):
    defaults = dict(
        country="US",
        state=None,
        tax_name="Sales Tax",
        tax_percentage=Decimal("9.50"),
        effective_from=date.today() - timedelta(days=30),
        effective_to=None,
        is_active=True,
    )
    defaults.update(overrides)
    rate = TaxRate(**defaults)
    db_session.add(rate)
    db_session.commit()
    return rate


def test_table_row_takes_priority_over_settings_fallback(db_session):
    _add_tax_rate(db_session, country="US", tax_percentage=Decimal("9.50"))
    service = TaxService(db_session)
    # settings.TAX_RATES["US"] is 0.08 -- the table row must win.
    assert service.get_tax_rate("US") == Decimal("0.0950")
    assert service.calculate_tax(Decimal("100.00"), "US") == Decimal("9.50")


def test_inactive_table_row_is_ignored(db_session):
    _add_tax_rate(db_session, country="US", tax_percentage=Decimal("9.50"), is_active=False)
    service = TaxService(db_session)
    # Falls back to settings since the only row is inactive.
    assert service.get_tax_rate("US") == Decimal("0.08")


def test_future_effective_row_is_not_yet_applied(db_session):
    _add_tax_rate(
        db_session,
        country="US",
        tax_percentage=Decimal("12.00"),
        effective_from=date.today() + timedelta(days=30),
    )
    service = TaxService(db_session)
    assert service.get_tax_rate("US") == Decimal("0.08")  # falls back; new rate isn't effective yet


def test_expired_row_is_not_applied(db_session):
    _add_tax_rate(
        db_session,
        country="US",
        tax_percentage=Decimal("5.00"),
        effective_from=date.today() - timedelta(days=60),
        effective_to=date.today() - timedelta(days=10),
    )
    service = TaxService(db_session)
    assert service.get_tax_rate("US") == Decimal("0.08")  # falls back; old rate has expired


def test_most_recently_effective_row_wins_when_multiple_match(db_session):
    _add_tax_rate(
        db_session,
        country="US",
        tax_percentage=Decimal("7.00"),
        effective_from=date.today() - timedelta(days=100),
    )
    _add_tax_rate(
        db_session,
        country="US",
        tax_percentage=Decimal("9.50"),
        effective_from=date.today() - timedelta(days=10),
    )
    service = TaxService(db_session)
    assert service.get_tax_rate("US") == Decimal("0.0950")


def test_rate_is_country_scoped(db_session):
    _add_tax_rate(db_session, country="US", tax_percentage=Decimal("9.50"))
    service = TaxService(db_session)
    # A different country with no table row still falls back correctly.
    assert service.get_tax_rate("IN") == Decimal("0.18")
