"""
Refund APIs (Module 2).

    POST /api/v1/refunds               Issue a refund (full or partial) against a paid invoice
    GET  /api/v1/refunds                List refunds, optionally filtered by customer or invoice
    GET  /api/v1/refunds/{refund_id}    Get a single refund by ID

Phase 1D: a non-admin may only access refunds belonging to their own
linked Customer (see app/services/ownership.py). Admins retain full
access to everything.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import PaginationParams, get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.refund import RefundCreateRequest, RefundResponse
from app.services.refund_service import RefundService

router = APIRouter(prefix="/refunds", tags=["Refunds"])


@router.post(
    "",
    response_model=RefundResponse,
    status_code=201,
    summary="Issue a full or partial refund against a paid invoice",
)
def create_refund(
    payload: RefundCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return RefundService(db).create_refund(
        invoice_id=payload.invoice_id,
        reason=payload.reason,
        amount=payload.amount,
        actor_id=current_user.id,
        requesting_user=current_user,
    )


@router.get(
    "",
    response_model=PaginatedResponse[RefundResponse],
    summary="List refunds, optionally filtered by customer or invoice "
    "(non-admins are always scoped to their own customer)",
)
def list_refunds(
    customer_id: uuid.UUID | None = None,
    invoice_id: uuid.UUID | None = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RefundService(db)
    items = service.list_refunds(
        customer_id, invoice_id, pagination.skip, pagination.limit, requesting_user=current_user
    )
    total = service.count_refunds(customer_id, invoice_id, requesting_user=current_user)
    return PaginatedResponse(
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        items=items,
    )


@router.get(
    "/{refund_id}",
    response_model=RefundResponse,
    summary="Get a single refund by ID (your own refund, or any if you're an admin)",
)
def get_refund(
    refund_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return RefundService(db).get_refund(refund_id, requesting_user=current_user)
