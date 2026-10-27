"""
Pydantic v2 schemas for the Tax Rate resource (Module 3, Phase 2a).
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMBaseModel


class TaxRateBase(BaseModel):
    country: str = Field(..., min_length=2, max_length=2, examples=["US"])
    state: Optional[str] = Field(None, max_length=100)
    tax_name: str = Field(..., min_length=1, max_length=100, examples=["Sales Tax"])
    tax_percentage: Decimal = Field(..., ge=0, le=100, examples=[8.00])
    effective_from: date
    effective_to: Optional[date] = None
    is_active: bool = Field(True)

    @field_validator("country")
    @classmethod
    def country_uppercase(cls, v: str) -> str:
        return v.upper()


class TaxRateCreate(TaxRateBase):
    pass


class TaxRateUpdate(BaseModel):
    """All fields optional -- only supplied fields are updated."""
    tax_name: Optional[str] = Field(None, max_length=100)
    tax_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    is_active: Optional[bool] = None


class TaxRateResponse(ORMBaseModel):
    id: uuid.UUID
    country: str
    state: Optional[str]
    tax_name: str
    tax_percentage: Decimal
    effective_from: date
    effective_to: Optional[date]
    is_active: bool
    created_at: datetime
    updated_at: datetime
