"""
Pydantic v2 schema for the payment webhook payload (Module 2).

This is the shape POSTed to /api/v1/webhooks/payment — both by the
in-process WebhookSenderService (when PAYMENT_WEBHOOK_URL is unset)
and by any external system replaying/forwarding a gateway event.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class PaymentWebhookPayload(BaseModel):
    invoice_id: uuid.UUID
    customer_id: uuid.UUID
    transaction_id: str = Field(..., description="Gateway transaction reference")
    status: Literal["paid", "failed", "refunded"]
    amount: Decimal
    event_time: datetime
    message: Optional[str] = Field(
        None, description="Optional human-readable gateway message"
    )


class WebhookAcknowledgement(BaseModel):
    received: bool = True
    event_processed: bool
    detail: str
