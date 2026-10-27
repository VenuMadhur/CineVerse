"""
Pydantic v2 schemas for the Subscription resource and its lifecycle
operations (create, change plan, pause, resume, cancel).
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import CancellationType, SubscriptionStatus
from app.schemas.common import ORMBaseModel


class SubscriptionCreate(BaseModel):
    customer_id: uuid.UUID
    plan_id: uuid.UUID


class SubscriptionChangePlan(BaseModel):
    new_plan_id: uuid.UUID = Field(..., description="Plan to move the subscription to")


class SubscriptionCancel(BaseModel):
    cancellation_type: CancellationType = Field(
        default=CancellationType.END_OF_CYCLE,
        description="immediate cancels now; end_of_cycle cancels at period end",
    )
    reason: Optional[str] = Field(None, max_length=500)


class SubscriptionStatusHistoryResponse(ORMBaseModel):
    id: uuid.UUID
    from_status: Optional[SubscriptionStatus]
    to_status: SubscriptionStatus
    reason: Optional[str]
    created_at: datetime


class SubscriptionResponse(ORMBaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    plan_id: uuid.UUID
    status: SubscriptionStatus
    trial_started_at: Optional[datetime]
    trial_ends_at: Optional[datetime]
    activated_at: Optional[datetime]
    past_due_at: Optional[datetime]
    paused_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancel_at_period_end: bool
    cancellation_type: Optional[CancellationType]
    created_at: datetime
    updated_at: datetime


class SubscriptionDetailResponse(SubscriptionResponse):
    status_history: list[SubscriptionStatusHistoryResponse] = []


class SubscriptionChangePlanResponse(SubscriptionResponse):
    """
    Returned by POST /subscriptions/{id}/change-plan. Extends the base
    subscription response (non-breaking for existing consumers) with
    the proration outcome, if proration was applicable (Module 2).
    """
    proration: Optional["ProrationResult"] = None


# Imported at the bottom to avoid a circular import at module load time
# (proration.py has no dependency back on subscription.py).
from app.schemas.proration import ProrationResult  # noqa: E402

SubscriptionChangePlanResponse.model_rebuild()
