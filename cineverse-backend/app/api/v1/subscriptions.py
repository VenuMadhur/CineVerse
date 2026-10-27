"""
Subscription Management APIs.

    POST /api/v1/subscriptions                          Create subscription
    GET  /api/v1/subscriptions                           List / filter subscriptions
    GET  /api/v1/subscriptions/{subscription_id}         Get subscription details
    POST /api/v1/subscriptions/{subscription_id}/activate    Activate (trial -> active)
    POST /api/v1/subscriptions/{subscription_id}/proration-preview  Calculate proration (Module 2)
    POST /api/v1/subscriptions/{subscription_id}/change-plan Upgrade/downgrade (applies proration)
    POST /api/v1/subscriptions/{subscription_id}/pause    Pause
    POST /api/v1/subscriptions/{subscription_id}/resume   Resume
    POST /api/v1/subscriptions/{subscription_id}/cancel   Cancel (immediate or end-of-cycle)
    POST /api/v1/subscriptions/{subscription_id}/undo-cancellation  Undo a scheduled end-of-cycle cancellation
    GET  /api/v1/subscriptions/{subscription_id}/billing-cycles

Phase 1D: every endpoint now requires authentication (GET routes were
previously public) and enforces that a non-admin may only access
subscriptions belonging to their own linked Customer -- see
app/services/ownership.py. Admins retain full access to everything.
"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PaginationParams, get_current_user
from app.core.database import get_db
from app.models.enums import SubscriptionStatus
from app.models.user import User
from app.schemas.billing_cycle import BillingCycleResponse
from app.schemas.common import PaginatedResponse
from app.schemas.proration import ProrationPreviewRequest, ProrationResult
from app.schemas.subscription import (
    SubscriptionCancel,
    SubscriptionChangePlan,
    SubscriptionChangePlanResponse,
    SubscriptionCreate,
    SubscriptionDetailResponse,
    SubscriptionResponse,
)
from app.services.billing_cycle_service import BillingCycleService
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=201,
    summary="Create a subscription (starts in trial status)",
)
def create_subscription(
    payload: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return SubscriptionService(db).create_subscription(
        payload, actor_id=current_user.id, requesting_user=current_user
    )


@router.get(
    "",
    response_model=PaginatedResponse[SubscriptionResponse],
    summary="List subscriptions, optionally filtered by status or customer "
    "(non-admins are always scoped to their own customer)",
)
def list_subscriptions(
    sub_status: SubscriptionStatus | None = Query(None, alias="status"),
    customer_id: uuid.UUID | None = Query(None),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SubscriptionService(db)
    items = service.list_subscriptions(
        sub_status, customer_id, pagination.skip, pagination.limit, requesting_user=current_user
    )
    total = service.count_subscriptions(sub_status, customer_id, requesting_user=current_user)
    return PaginatedResponse(
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        items=items,
    )


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionDetailResponse,
    summary="Get subscription details including status history "
    "(your own subscription, or any if you're an admin)",
)
def get_subscription(
    subscription_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return SubscriptionService(db).get_subscription(subscription_id, requesting_user=current_user)


@router.post(
    "/{subscription_id}/activate",
    response_model=SubscriptionResponse,
    summary="Manually activate a trial subscription",
)
def activate_subscription(
    subscription_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return SubscriptionService(db).activate_subscription(
        subscription_id, actor_id=current_user.id, requesting_user=current_user
    )


@router.post(
    "/{subscription_id}/proration-preview",
    response_model=ProrationResult,
    summary="Calculate the proration effect of a plan change without applying it",
)
def preview_proration(
    subscription_id: uuid.UUID,
    payload: ProrationPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    calc = SubscriptionService(db).preview_proration(
        subscription_id, payload.new_plan_id, requesting_user=current_user
    )
    return ProrationResult(**calc.__dict__)


@router.post(
    "/{subscription_id}/change-plan",
    response_model=SubscriptionChangePlanResponse,
    summary="Upgrade or downgrade a subscription's plan (auto-applies proration if mid-cycle)",
)
def change_plan(
    subscription_id: uuid.UUID,
    payload: SubscriptionChangePlan,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription, proration_calc = SubscriptionService(db).change_plan(
        subscription_id, payload.new_plan_id, actor_id=current_user.id, requesting_user=current_user
    )
    response = SubscriptionChangePlanResponse.model_validate(subscription)
    if proration_calc is not None:
        response.proration = ProrationResult(**proration_calc.__dict__)
    return response


@router.post(
    "/{subscription_id}/pause",
    response_model=SubscriptionResponse,
    summary="Pause an active subscription",
)
def pause_subscription(
    subscription_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return SubscriptionService(db).pause_subscription(
        subscription_id, actor_id=current_user.id, requesting_user=current_user
    )


@router.post(
    "/{subscription_id}/resume",
    response_model=SubscriptionResponse,
    summary="Resume a paused subscription",
)
def resume_subscription(
    subscription_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return SubscriptionService(db).resume_subscription(
        subscription_id, actor_id=current_user.id, requesting_user=current_user
    )


@router.post(
    "/{subscription_id}/undo-cancellation",
    response_model=SubscriptionResponse,
    summary="Undo a not-yet-executed 'cancel at end of billing cycle' request",
)
def undo_scheduled_cancellation(
    subscription_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return SubscriptionService(db).undo_scheduled_cancellation(
        subscription_id, actor_id=current_user.id, requesting_user=current_user
    )


@router.post(
    "/{subscription_id}/cancel",
    response_model=SubscriptionResponse,
    summary="Cancel a subscription, immediately or at end of billing cycle "
    "(immediate cancellation of an active subscription auto-refunds unused time)",
)
def cancel_subscription(
    subscription_id: uuid.UUID,
    payload: SubscriptionCancel,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return SubscriptionService(db).cancel_subscription(
        subscription_id, payload, actor_id=current_user.id, requesting_user=current_user
    )


@router.get(
    "/{subscription_id}/billing-cycles",
    response_model=list[BillingCycleResponse],
    summary="List billing cycles for a subscription",
)
def list_billing_cycles(
    subscription_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Ownership check happens via get_subscription (raises 403/404 as
    # appropriate); BillingCycleService itself has no ownership context.
    SubscriptionService(db).get_subscription(subscription_id, requesting_user=current_user)
    return BillingCycleService(db).list_for_subscription(subscription_id)
