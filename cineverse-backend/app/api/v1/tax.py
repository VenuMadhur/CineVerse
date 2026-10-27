"""
Tax Master APIs (Module 3, Phase 2a).

    POST   /api/v1/tax/rates              Create a tax rate (admin only)
    GET    /api/v1/tax/rates              List tax rates, optionally filtered by country
    GET    /api/v1/tax/rates/{rate_id}    Get a tax rate by ID
    PATCH  /api/v1/tax/rates/{rate_id}    Update a tax rate (admin only)

Admin-gating: every endpoint here requires get_current_superuser,
including reads -- tax rate configuration is purely internal
operational/financial data with no customer-facing use case, same
reasoning as the Retry Configuration module (Phase 1a).
"""
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import PaginationParams, get_current_superuser
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.tax import TaxRateCreate, TaxRateResponse, TaxRateUpdate
from app.services.tax_rate_service import TaxRateService

router = APIRouter(prefix="/tax", tags=["Tax"])


@router.post(
    "/rates",
    response_model=TaxRateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tax rate (admin only)",
)
def create_tax_rate(
    payload: TaxRateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return TaxRateService(db).create_tax_rate(payload, actor_id=current_user.id)


@router.get(
    "/rates",
    response_model=PaginatedResponse[TaxRateResponse],
    summary="List tax rates, optionally filtered by country (admin only)",
)
def list_tax_rates(
    country: str | None = Query(None, min_length=2, max_length=2),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    service = TaxRateService(db)
    items = service.list_tax_rates(country, pagination.skip, pagination.limit)
    total = service.count_tax_rates(country)
    return PaginatedResponse(
        total=total, page=pagination.page, page_size=pagination.page_size, items=items
    )


@router.get(
    "/rates/{rate_id}",
    response_model=TaxRateResponse,
    summary="Get a tax rate by ID (admin only)",
)
def get_tax_rate(
    rate_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return TaxRateService(db).get_tax_rate(rate_id)


@router.patch(
    "/rates/{rate_id}",
    response_model=TaxRateResponse,
    summary="Update a tax rate's percentage, name, effective dates, or active status (admin only)",
)
def update_tax_rate(
    rate_id: uuid.UUID,
    payload: TaxRateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return TaxRateService(db).update_tax_rate(rate_id, payload, actor_id=current_user.id)
