"""
Pydantic v2 schemas for Payment processing (Module 2 mock gateway).
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import PaymentStatus
from app.schemas.common import ORMBaseModel


class PaymentProcessRequest(BaseModel):
    invoice_id: uuid.UUID
    amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Amount to charge; defaults to the invoice's total_amount",
    )


class PaymentResponse(BaseModel):
    """Immediate response from the mock payment gateway call."""
    transaction_id: str
    invoice_id: uuid.UUID
    amount: Decimal
    status: PaymentStatus
    processed_at: Optional[datetime]
    message: str


class PaymentRecordResponse(ORMBaseModel):
    """Full persisted Payment record, used for payment history endpoints."""
    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    currency: str
    status: PaymentStatus
    payment_method: str
    gateway_reference: Optional[str]
    attempt_number: int
    processed_at: Optional[datetime]
    failure_reason: Optional[str]
    created_at: datetime
