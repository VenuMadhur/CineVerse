"""
Payment APIs (Module 2).

    POST /api/v1/payments/process   Process a payment via the mock gateway
    GET  /api/v1/payments           View payment history (optionally filtered by invoice or customer)
    GET  /api/v1/payments/{id}      View a single payment record

Phase 1D: a non-admin may only access payments belonging to their own
linked Customer (see app/services/ownership.py). Admins retain full
access to everything.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import PaginationParams, get_current_user
from app.core.database import get_db
from app.exceptions.custom_exceptions import NotFoundException
from app.models.enums import PaymentStatus
from app.models.user import User
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.common import PaginatedResponse
from app.schemas.payment import PaymentProcessRequest, PaymentRecordResponse, PaymentResponse
from app.services.ownership import assert_owns_customer, effective_customer_filter
from app.services.payment_gateway_service import PaymentGatewayService

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "/process",
    response_model=PaymentResponse,
    status_code=201,
    summary="Process a payment against an invoice via the mock payment gateway",
)
def process_payment(
    payload: PaymentProcessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return PaymentGatewayService(db).process_payment(
        invoice_id=payload.invoice_id,
        amount=payload.amount,
        actor_id=current_user.id,
        requesting_user=current_user,
    )


@router.get(
    "",
    response_model=PaginatedResponse[PaymentRecordResponse],
    summary="List payments, optionally filtered by invoice or customer "
    "(non-admins are always scoped to their own customer)",
)
def list_payments(
    invoice_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    status: PaymentStatus | None = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    effective_customer_id = effective_customer_filter(customer_id, current_user, db)
    repository = PaymentRepository(db)
    items = repository.list_all(invoice_id, effective_customer_id, pagination.skip, pagination.limit, status=status)
    total = repository.count_all(invoice_id, effective_customer_id, status=status)
    return PaginatedResponse(
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        items=items,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentRecordResponse,
    summary="Get a single payment record by ID (your own payment, or any if you're an admin)",
)
def get_payment(
    payment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = PaymentRepository(db).get_by_id(payment_id)
    if payment is None:
        raise NotFoundException(f"Payment {payment_id} not found")

    invoice = InvoiceRepository(db).get_by_id(payment.invoice_id)
    if invoice is not None:
        assert_owns_customer(invoice.customer_id, current_user, db)
    return payment
