"""
Audit Log viewer APIs.

    GET /api/v1/audit-logs                    List all audit events (admin only)
    GET /api/v1/audit-logs/me                 Account-wide Activity Timeline (your own account)
    GET /api/v1/audit-logs/{entity_type}/{entity_id}  Audit trail for one entity

Final production review: this router predates Phase 1D and was never
covered by its ownership-enforcement pass. Confirmed live that any
authenticated non-admin could see the entire platform's audit log, or
any other customer's private entity trail, just by knowing/guessing an
ID. Both endpoints now enforce ownership via app/services/ownership.py,
exactly like every other resource in this API.
"""
import uuid

from fastapi import APIRouter, Depends, Query

from sqlalchemy.orm import Session

from app.api.deps import PaginationParams, get_current_user
from app.core.database import get_db
from app.exceptions.custom_exceptions import ForbiddenException
from app.models.user import User
from app.schemas.audit_log import AuditLogResponse
from app.schemas.common import PaginatedResponse
from app.services.audit_log_service import AuditLogService
from app.services.ownership import assert_owns_audit_entity

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get(
    "",
    response_model=PaginatedResponse[AuditLogResponse],
    summary="List audit log entries, optionally filtered by entity type "
    "(admin only, except entity_type=plan which is public data)",
)
def list_audit_logs(
    entity_type: str | None = Query(None, description="e.g. plan, customer, subscription"),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # This endpoint has no per-row customer scoping (unlike every other
    # list endpoint in this API) -- filtering by entity_type alone
    # would still mix every customer's subscriptions/invoices/etc
    # together. Only "plan" is safe for a non-admin: plans are public
    # data (GET /plans needs no auth at all), so their audit trail
    # isn't customer-sensitive either. Everything else requires admin.
    if entity_type != "plan" and not current_user.is_superuser:
        raise ForbiddenException("This action requires administrator privileges")

    service = AuditLogService(db)
    items = service.list_all(entity_type, pagination.skip, pagination.limit)
    total = service.count_all(entity_type)
    return PaginatedResponse(
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        items=items,
    )


@router.get(
    "/me",
    response_model=PaginatedResponse[AuditLogResponse],
    summary="Account-wide Activity Timeline: every event across your own "
    "account (registration, logins/logouts, subscriptions, invoices, "
    "payments, refunds), chronological",
)
def get_my_activity_timeline(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Always scoped to the caller's own account -- there is no
    customer_id parameter to pass, unlike every list endpoint
    elsewhere in this API, since this endpoint has no admin/"see
    everyone" mode at all. Reuses AuditLogService.list_for_account,
    which itself reuses the existing Subscription/Invoice/Payment/
    Refund repositories to resolve which entities belong to this
    account -- no new queries beyond what those resources' own list
    endpoints already run.
    """
    service = AuditLogService(db)
    items = service.list_for_account(current_user, pagination.skip, pagination.limit)
    total = service.count_for_account(current_user)
    return PaginatedResponse(
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        items=items,
    )


@router.get(
    "/{entity_type}/{entity_id}",
    response_model=list[AuditLogResponse],
    summary="Get the complete audit trail for a single entity "
    "(only if you own it, or you're an admin)",
)
def get_entity_audit_trail(
    entity_type: str,
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_owns_audit_entity(entity_type, entity_id, current_user, db)
    return AuditLogService(db).list_for_entity(entity_type, entity_id)
