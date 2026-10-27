"""
Pydantic v2 schemas for the Plan resource.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.enums import BillingInterval, PlanStatus
from app.schemas.common import ORMBaseModel


class PlanBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, examples=["Pro Monthly"])
    description: Optional[str] = Field(None, max_length=2000)
    price: Decimal = Field(..., ge=0, examples=[29.99])
    currency: str = Field("USD", min_length=3, max_length=3, examples=["USD"])
    billing_interval: BillingInterval = Field(
        default=BillingInterval.MONTHLY, examples=[BillingInterval.MONTHLY]
    )
    trial_period_days: int = Field(0, ge=0, le=365, examples=[14])
    feature_entitlements: Dict[str, int | str | bool] = Field(
        default_factory=dict,
        examples=[{"api_calls": 10000, "seats": 5, "storage_gb": 50}],
    )

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.upper()


class PlanCreate(PlanBase):
    pass


class PlanUpdate(BaseModel):
    """All fields optional — only supplied fields are updated."""
    description: Optional[str] = Field(None, max_length=2000)
    price: Optional[Decimal] = Field(None, ge=0)
    billing_interval: Optional[BillingInterval] = None
    trial_period_days: Optional[int] = Field(None, ge=0, le=365)
    feature_entitlements: Optional[Dict[str, int | str | bool]] = None


class PlanResponse(ORMBaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    price: Decimal
    currency: str
    billing_interval: BillingInterval
    trial_period_days: int
    feature_entitlements: Dict[str, int | str | bool]
    status: PlanStatus
    created_at: datetime
    updated_at: datetime
