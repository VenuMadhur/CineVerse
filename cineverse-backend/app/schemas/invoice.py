"""
Pydantic v2 schemas for the Invoice resource (Module 2).
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import InvoiceLineItemType, InvoiceStatus
from app.schemas.common import ORMBaseModel


class InvoiceLineItemResponse(ORMBaseModel):
    id: uuid.UUID
    item_type: InvoiceLineItemType
    description: str
    quantity: int
    unit_price: Decimal
    amount: Decimal


class InvoiceResponse(ORMBaseModel):
    id: uuid.UUID
    invoice_number: str
    subscription_id: uuid.UUID
    billing_cycle_id: Optional[uuid.UUID]
    customer_id: uuid.UUID
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    currency: str
    status: InvoiceStatus
    due_date: Optional[datetime]
    paid_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class InvoiceDetailResponse(InvoiceResponse):
    line_items: List[InvoiceLineItemResponse] = []
    # Phase 6C: denormalized fields for a self-contained invoice view
    # (no extra round trips to /customers/{id} or /invoices/{id}/payments
    # needed just to show these). All optional/defaulted so this stays
    # backward compatible with anything constructing an InvoiceDetailResponse
    # without them.
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_country: Optional[str] = None
    billing_address: Optional[str] = None
    payment_method: Optional[str] = None
    discount_amount: Decimal = Decimal("0")
    refund_status: str = "none"  # "none" | "partial" | "full"


class InvoiceGenerateRequest(BaseModel):
    subscription_id: uuid.UUID = Field(
        ..., description="Subscription to generate the current cycle's invoice for"
    )
