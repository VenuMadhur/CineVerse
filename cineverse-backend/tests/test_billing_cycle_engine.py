"""
Unit tests for the billing cycle engine's renewal date math.
"""
from datetime import datetime, timezone

from app.models.enums import BillingInterval
from app.services.billing_cycle_service import add_interval


def test_monthly_interval_regular_day():
    start = datetime(2026, 1, 15, tzinfo=timezone.utc)
    result = add_interval(start, BillingInterval.MONTHLY)
    assert result == datetime(2026, 2, 15, tzinfo=timezone.utc)


def test_monthly_interval_month_end_clamping():
    # Jan 31 + 1 month -> Feb 28 (2026 is not a leap year)
    start = datetime(2026, 1, 31, tzinfo=timezone.utc)
    result = add_interval(start, BillingInterval.MONTHLY)
    assert result == datetime(2026, 2, 28, tzinfo=timezone.utc)


def test_monthly_interval_leap_year():
    start = datetime(2028, 1, 31, tzinfo=timezone.utc)  # 2028 is a leap year
    result = add_interval(start, BillingInterval.MONTHLY)
    assert result == datetime(2028, 2, 29, tzinfo=timezone.utc)


def test_monthly_interval_crosses_year_boundary():
    start = datetime(2026, 12, 15, tzinfo=timezone.utc)
    result = add_interval(start, BillingInterval.MONTHLY)
    assert result == datetime(2027, 1, 15, tzinfo=timezone.utc)


def test_annual_interval_regular_day():
    start = datetime(2026, 3, 10, tzinfo=timezone.utc)
    result = add_interval(start, BillingInterval.ANNUAL)
    assert result == datetime(2027, 3, 10, tzinfo=timezone.utc)


def test_annual_interval_leap_day_clamping():
    # Feb 29 2028 + 1 year -> Feb 28 2029 (2029 is not a leap year)
    start = datetime(2028, 2, 29, tzinfo=timezone.utc)
    result = add_interval(start, BillingInterval.ANNUAL)
    assert result == datetime(2029, 2, 28, tzinfo=timezone.utc)
