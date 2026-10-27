"""
Pydantic v2 schemas for proration calculation (Module 2).
"""
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ProrationPreviewRequest(BaseModel):
    new_plan_id: uuid.UUID = Field(..., description="Plan to preview changing to")


class ProrationResult(BaseModel):
    applicable: bool = Field(
        ..., description="Whether proration applies to this plan change"
    )
    reason: Optional[str] = Field(
        None, description="Why proration was or wasn't applied"
    )
    cycle_total_days: Optional[int] = None
    remaining_days: Optional[int] = None
    old_plan_unused_credit: Optional[Decimal] = None
    new_plan_remaining_cost: Optional[Decimal] = None
    net_amount: Decimal = Field(
        Decimal("0.00"),
        description="Positive = amount to charge the customer now; "
        "negative = credit owed to the customer",
    )
