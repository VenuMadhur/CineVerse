"""
Unit tests for ProrationService (pure date/price math, no DB).
"""
from datetime import datetime, timezone
from decimal import Decimal

from app.services.proration_service import ProrationService


def _dt(day):
    return datetime(2026, 3, day, tzinfo=timezone.utc)


class TestProrationApplicability:
    def test_not_applicable_when_cycle_already_ended(self):
        result = ProrationService.calculate(
            old_plan_price=Decimal("10"),
            new_plan_price=Decimal("20"),
            cycle_start=_dt(1),
            cycle_end=_dt(10),
            as_of=_dt(10),  # exactly at cycle end -> ended
        )
        assert result.applicable is False
        assert "already ended" in result.reason

    def test_not_applicable_when_cycle_invalid(self):
        result = ProrationService.calculate(
            old_plan_price=Decimal("10"),
            new_plan_price=Decimal("20"),
            cycle_start=_dt(10),
            cycle_end=_dt(1),  # end before start
            as_of=_dt(5),
        )
        assert result.applicable is False

    def test_as_of_before_cycle_start_is_clamped(self):
        # as_of earlier than cycle_start should be treated as cycle_start
        # (full period remaining), not raise or misbehave.
        result = ProrationService.calculate(
            old_plan_price=Decimal("30"),
            new_plan_price=Decimal("60"),
            cycle_start=_dt(10),
            cycle_end=_dt(20),
            as_of=_dt(1),
        )
        assert result.applicable is True
        assert result.remaining_days == 10


class TestProrationUpgrade:
    def test_upgrade_mid_cycle_charges_net_positive(self):
        # 30-day cycle, 15 days remaining (halfway through)
        # old plan $30/mo, new plan $60/mo
        result = ProrationService.calculate(
            old_plan_price=Decimal("30.00"),
            new_plan_price=Decimal("60.00"),
            cycle_start=_dt(1),
            cycle_end=_dt(31),
            as_of=_dt(16),
        )
        assert result.applicable is True
        assert result.cycle_total_days == 30
        assert result.remaining_days == 15
        assert result.old_plan_unused_credit == Decimal("15.00")
        assert result.new_plan_remaining_cost == Decimal("30.00")
        assert result.net_amount == Decimal("15.00")  # customer owes $15 more


class TestProrationDowngrade:
    def test_downgrade_mid_cycle_yields_net_credit(self):
        # Same 30-day cycle, 15 days remaining. old plan $60, new plan $30.
        result = ProrationService.calculate(
            old_plan_price=Decimal("60.00"),
            new_plan_price=Decimal("30.00"),
            cycle_start=_dt(1),
            cycle_end=_dt(31),
            as_of=_dt(16),
        )
        assert result.applicable is True
        assert result.old_plan_unused_credit == Decimal("30.00")
        assert result.new_plan_remaining_cost == Decimal("15.00")
        assert result.net_amount == Decimal("-15.00")  # customer is owed a credit


class TestProrationDifferentDaysInCycle:
    def test_early_in_cycle_more_days_remaining(self):
        result = ProrationService.calculate(
            old_plan_price=Decimal("100.00"),
            new_plan_price=Decimal("200.00"),
            cycle_start=_dt(1),
            cycle_end=_dt(31),
            as_of=_dt(2),  # only 1 day used, 29 remaining
        )
        assert result.remaining_days == 29

    def test_late_in_cycle_fewer_days_remaining(self):
        result = ProrationService.calculate(
            old_plan_price=Decimal("100.00"),
            new_plan_price=Decimal("200.00"),
            cycle_start=_dt(1),
            cycle_end=_dt(31),
            as_of=_dt(30),  # 1 day remaining
        )
        assert result.remaining_days == 1
        # proportional cost should be small
        assert result.new_plan_remaining_cost < Decimal("10.00")
