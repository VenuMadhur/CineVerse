"""
Failed Payment Retry APIs (Module 3, Phase 1a).

    POST   /api/v1/retry/configuration              Create a retry configuration (admin only)
    GET    /api/v1/retry/configuration               List retry configurations
    GET    /api/v1/retry/configuration/{config_id}   Get a retry configuration by ID
    PATCH  /api/v1/retry/configuration/{config_id}   Update a retry configuration (admin only)

This phase covers Retry Configuration management only -- defining the
retry schedule (attempt number -> days after the payment first
failed). No retry execution, no Celery scheduler, and no Retry Queue
endpoint exist yet; those are later phases.

Admin-gating: every endpoint here requires get_current_superuser,
including reads. This differs from the Plans module (where GET is
public, since plans are customer-facing) -- retry configuration is
purely internal operational data with no customer-facing use case, so
there's no reason to expose it to non-admins at all.
"""
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import PaginationParams, get_current_superuser
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.retry import (
    RetryConfigurationCreate,
    RetryConfigurationResponse,
    RetryConfigurationUpdate,
)
from app.services.retry_service import RetryService

router = APIRouter(prefix="/retry", tags=["Retry"])


@router.post(
    "/configuration",
    response_model=RetryConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a retry configuration for a given attempt number (admin only)",
)
def create_retry_configuration(
    payload: RetryConfigurationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return RetryService(db).create_configuration(payload, actor_id=current_user.id)


@router.get(
    "/configuration",
    response_model=PaginatedResponse[RetryConfigurationResponse],
    summary="List retry configurations, ordered by attempt number (admin only)",
)
def list_retry_configurations(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    service = RetryService(db)
    items = service.list_configurations(pagination.skip, pagination.limit)
    total = service.count_configurations()
    return PaginatedResponse(
        total=total, page=pagination.page, page_size=pagination.page_size, items=items
    )


@router.get(
    "/configuration/{config_id}",
    response_model=RetryConfigurationResponse,
    summary="Get a retry configuration by ID (admin only)",
)
def get_retry_configuration(
    config_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return RetryService(db).get_configuration(config_id)


@router.patch(
    "/configuration/{config_id}",
    response_model=RetryConfigurationResponse,
    summary="Update a retry configuration's retry_after_days or is_active (admin only)",
)
def update_retry_configuration(
    config_id: uuid.UUID,
    payload: RetryConfigurationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return RetryService(db).update_configuration(config_id, payload, actor_id=current_user.id)
