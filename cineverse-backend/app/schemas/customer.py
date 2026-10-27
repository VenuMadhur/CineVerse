"""
Pydantic v2 schemas for the Customer resource.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


from app.schemas.common import ORMBaseModel


class CustomerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, examples=["Acme Corp"])
    email: EmailStr = Field(..., examples=["billing@acmecorp.com"])
    phone_number: Optional[str] = Field(None, max_length=30, examples=["+1-415-555-0100"])
    country: str = Field(..., min_length=2, max_length=2, examples=["US"])
    address: Optional[str] = Field(None, max_length=500)
    # Module 3, Phase 2b: optional, not required for existing or new
    # customers. Used for reporting (State-wise Tax) and future
    # extensibility.
    state: Optional[str] = Field(None, max_length=100, examples=["California"])

    @field_validator("country")
    @classmethod
    def country_uppercase(cls, v: str) -> str:
        return v.upper()


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    phone_number: Optional[str] = Field(None, max_length=30)
    country: Optional[str] = Field(None, min_length=2, max_length=2)
    address: Optional[str] = Field(None, max_length=500)
    state: Optional[str] = Field(None, max_length=100)


class CustomerResponse(ORMBaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    phone_number: Optional[str]
    country: str
    address: Optional[str]
    state: Optional[str]
    created_at: datetime
    updated_at: datetime
