"""
Customer Management APIs.

    POST  /api/v1/customers               Create customer
    GET   /api/v1/customers               List customers (admin-only, Phase 1C)
    GET   /api/v1/customers/me            Get the authenticated user's linked customer
    GET   /api/v1/customers/{customer_id} Get customer by ID (own customer only, unless admin)
    PATCH /api/v1/customers/{customer_id} Update customer (own customer only, unless admin)
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import PaginationParams, get_current_superuser, get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer",
)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return CustomerService(db).create_customer(payload, actor_id=current_user.id)


@router.get(
    "",
    response_model=PaginatedResponse[CustomerResponse],
    summary="List all customers (admin only)",
    description="Optional `search` matches against name or email (case-insensitive, partial match). "
    "Omit it for the existing unfiltered, paginated list.",
)
def list_customers(
    pagination: PaginationParams = Depends(),
    search: Optional[str] = Query(None, min_length=1, max_length=200, description="Filter by name or email"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    service = CustomerService(db)
    items = service.list_customers(pagination.skip, pagination.limit, search=search)
    total = service.count_customers(search=search)
    return PaginatedResponse(
        total=total, page=pagination.page, page_size=pagination.page_size, items=items
    )


@router.get(
    "/me",
    response_model=CustomerResponse,
    summary="Get the customer record linked to the authenticated user",
)
def get_my_customer(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns 404 if this User account has no linked Customer yet (e.g.
    a brand-new registration where customer provisioning hasn't
    happened, or an account created before Phase 1A's backfill with
    no matching email). This route must be declared before
    `/{customer_id}` -- otherwise FastAPI would try to parse "me" as a
    UUID path parameter and fail with a 422 instead.
    """
    return CustomerService(db).get_my_customer(current_user.id)


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer details by ID (your own customer, or any if you're an admin)",
)
def get_customer(
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return CustomerService(db).get_customer(customer_id, requesting_user=current_user)


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update a customer's details (your own customer, or any if you're an admin)",
)
def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return CustomerService(db).update_customer(
        customer_id, payload, actor_id=current_user.id, requesting_user=current_user
    )
