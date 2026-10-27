"""
Pydantic v2 schemas for the BillingCycle resource.
"""
import uuid
from datetime import datetime

from app.schemas.common import ORMBaseModel


class BillingCycleResponse(ORMBaseModel):
    id: uuid.UUID
    subscription_id: uuid.UUID
    cycle_start_date: datetime
    cycle_end_date: datetime
    renewal_date: datetime
    next_billing_date: datetime
    is_billed: bool
    created_at: datetime
