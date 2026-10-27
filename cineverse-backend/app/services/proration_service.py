"""
Proration Calculation Engine (Module 2).

Computes the credit/debit owed when a subscription changes plans
mid-cycle:

    unused_credit          = old_plan.price * (remaining_days / cycle_total_days)
    new_plan_remaining_cost = new_plan.price * (remaining_days / cycle_total_days)
    net_amount              = new_plan_remaining_cost - unused_credit

`net_amount > 0` means the customer owes more (typically an upgrade);
`net_amount < 0` means the customer is owed a credit (typically a
downgrade). Kept as pure, side-effect-free logic operating on plain
values so it's fully unit-testable without a database.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional


@dataclass(frozen=True)
class ProrationCalculation:
    applicable: bool
    reason: Optional[str]
    cycle_total_days: Optional[int] = None
    remaining_days: Optional[int] = None
    old_plan_unused_credit: Optional[Decimal] = None
    new_plan_remaining_cost: Optional[Decimal] = None
    net_amount: Decimal = Decimal("0.00")


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ProrationService:
    @staticmethod
    def calculate(
        old_plan_price: Decimal,
        new_plan_price: Decimal,
        cycle_start: datetime,
        cycle_end: datetime,
        as_of: datetime,
    ) -> ProrationCalculation:
        """
        Pure calculation — does not touch the database. Validates that
        `as_of` falls strictly within [cycle_start, cycle_end); if the
        cycle has already ended (or hasn't started), proration does
        not apply and the caller should simply swap the plan without
        generating a proration invoice.
        """
        if cycle_end <= cycle_start:
            return ProrationCalculation(
                applicable=False, reason="Invalid billing cycle (end <= start)"
            )

        if as_of >= cycle_end:
            return ProrationCalculation(
                applicable=False,
                reason="Billing cycle has already ended; proration does not apply",
            )

        if as_of < cycle_start:
            as_of = cycle_start

        cycle_total_days = (cycle_end - cycle_start).days or 1
        remaining_days = max((cycle_end - as_of).days, 0)

        if remaining_days == 0:
            return ProrationCalculation(
                applicable=False,
                reason="No remaining days in the current billing cycle",
                cycle_total_days=cycle_total_days,
                remaining_days=0,
            )

        proportion = Decimal(remaining_days) / Decimal(cycle_total_days)
        old_plan_unused_credit = _round(old_plan_price * proportion)
        new_plan_remaining_cost = _round(new_plan_price * proportion)
        net_amount = _round(new_plan_remaining_cost - old_plan_unused_credit)

        return ProrationCalculation(
            applicable=True,
            reason=None,
            cycle_total_days=cycle_total_days,
            remaining_days=remaining_days,
            old_plan_unused_credit=old_plan_unused_credit,
            new_plan_remaining_cost=new_plan_remaining_cost,
            net_amount=net_amount,
        )
