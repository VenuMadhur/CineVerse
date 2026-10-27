"""
Plan Management APIs.

    POST   /api/v1/plans              Create plan (admin only, Phase 1C)
    GET    /api/v1/plans              List / filter plans (public)
    GET    /api/v1/plans/{plan_id}    Get plan by ID (public)
    PATCH  /api/v1/plans/{plan_id}    Update plan (admin only, Phase 1C)
    POST   /api/v1/plans/{plan_id}/archive   Archive plan (admin only, Phase 1C)
    POST   /api/v1/plans/{plan_id}/unarchive Restore an archived plan (admin only)
    DELETE /api/v1/plans/{plan_id}           Delete a plan (admin only) -- blocked if ever used
"""
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import PaginationParams, get_current_superuser
from app.core.database import get_db
from app.models.enums import PlanStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.plan import PlanCreate, PlanResponse, PlanUpdate
from app.services.plan_service import PlanService

router = APIRouter(prefix="/plans", tags=["Plans"])


@router.post(
    "",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new subscription plan (admin only)",
)
def create_plan(
    payload: PlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return PlanService(db).create_plan(payload, actor_id=current_user.id)


@router.get(
    "",
    response_model=PaginatedResponse[PlanResponse],
    summary="List plans, optionally filtered by status",
)
def list_plans(
    plan_status: PlanStatus | None = Query(None, alias="status"),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    service = PlanService(db)
    items = service.list_plans(plan_status, pagination.skip, pagination.limit)
    total = service.count_plans(plan_status)
    return PaginatedResponse(
        total=total, page=pagination.page, page_size=pagination.page_size, items=items
    )


@router.get(
    "/{plan_id}",
    response_model=PlanResponse,
    summary="Get a plan by ID",
)
def get_plan(plan_id: uuid.UUID, db: Session = Depends(get_db)):
    return PlanService(db).get_plan(plan_id)


@router.patch(
    "/{plan_id}",
    response_model=PlanResponse,
    summary="Update a plan's price, features, trial days, interval, or description (admin only)",
)
def update_plan(
    plan_id: uuid.UUID,
    payload: PlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return PlanService(db).update_plan(plan_id, payload, actor_id=current_user.id)


@router.post(
    "/{plan_id}/archive",
    response_model=PlanResponse,
    summary="Archive a plan (existing subscribers keep using it) (admin only)",
)
def archive_plan(
    plan_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return PlanService(db).archive_plan(plan_id, actor_id=current_user.id)


@router.post(
    "/{plan_id}/unarchive",
    response_model=PlanResponse,
    summary="Restore an archived plan so it's offered to new customers again (admin only)",
)
def unarchive_plan(
    plan_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return PlanService(db).unarchive_plan(plan_id, actor_id=current_user.id)


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a plan (admin only) -- blocked if any subscription has ever used it",
)
def delete_plan(
    plan_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    PlanService(db).delete_plan(plan_id, actor_id=current_user.id)
    return None
