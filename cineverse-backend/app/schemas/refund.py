"""
Pydantic v2 schemas for Refund processing (Module 2).
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import RefundStatus
from app.schemas.common import ORMBaseModel


class RefundCreateRequest(BaseModel):
    invoice_id: uuid.UUID
    amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Amount to refund; defaults to a full refund of the invoice total",
    )
    reason: str = Field(..., min_length=1, max_length=500)


class RefundResponse(ORMBaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    customer_id: uuid.UUID
    amount: Decimal
    currency: str
    reason: str
    status: RefundStatus
    processed_at: Optional[datetime]
    created_at: datetime
