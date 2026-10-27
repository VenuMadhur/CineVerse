"""
Invoice APIs (Module 2).

    GET  /api/v1/invoices                       List / filter invoices (by customer, subscription, status)
    GET  /api/v1/invoices/{invoice_id}           View invoice (with line items + Phase 6C denormalized fields)
    GET  /api/v1/invoices/{invoice_id}/payments  View payment history for an invoice
    GET  /api/v1/invoices/{invoice_id}/refunds   View refund history for an invoice
    GET  /api/v1/invoices/{invoice_id}/pdf       Download the invoice as a PDF (Phase 4)
    POST /api/v1/invoices/{invoice_id}/email     Email the invoice PDF to the customer (Phase 6C)

Phase 1D: a non-admin may only access invoices belonging to their own
linked Customer (see app/services/ownership.py). Admins retain full
access to everything.
"""
import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import PaginationParams, get_current_user
from app.core.database import get_db
from app.core.rate_limiter import get_client_ip
from app.models.enums import AuditEventType, InvoiceStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.invoice import InvoiceDetailResponse, InvoiceResponse
from app.services.audit_log_service import AuditLogService
from app.schemas.payment import PaymentRecordResponse
from app.schemas.refund import RefundResponse
from app.services.invoice_pdf_service import InvoicePdfService
from app.services.invoice_service import InvoiceService
from app.services.refund_service import RefundService
from app.repositories.payment_repository import PaymentRepository

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get(
    "",
    response_model=PaginatedResponse[InvoiceResponse],
    summary="List invoices, optionally filtered by customer, subscription, or status "
    "(non-admins are always scoped to their own customer)",
)
def list_invoices(
    customer_id: uuid.UUID | None = Query(None),
    subscription_id: uuid.UUID | None = Query(None),
    invoice_status: InvoiceStatus | None = Query(None, alias="status"),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = InvoiceService(db)
    items = service.list_invoices(
        customer_id,
        subscription_id,
        invoice_status,
        pagination.skip,
        pagination.limit,
        requesting_user=current_user,
    )
    total = service.count_invoices(
        customer_id, subscription_id, invoice_status, requesting_user=current_user
    )
    return PaginatedResponse(
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        items=items,
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceDetailResponse,
    summary="View an invoice, including its line items "
    "(your own invoice, or any if you're an admin)",
)
def get_invoice(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return InvoiceService(db).get_invoice_with_details(invoice_id, requesting_user=current_user)


@router.get(
    "/{invoice_id}/payments",
    response_model=list[PaymentRecordResponse],
    summary="View payment history for an invoice",
)
def get_invoice_payments(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Ownership check happens via get_invoice (raises 403/404 as
    # appropriate); PaymentRepository itself has no ownership context.
    InvoiceService(db).get_invoice(invoice_id, requesting_user=current_user)
    return PaymentRepository(db).list_for_invoice(invoice_id)


@router.get(
    "/{invoice_id}/refunds",
    response_model=list[RefundResponse],
    summary="View refund history for an invoice",
)
def get_invoice_refunds(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    InvoiceService(db).get_invoice(invoice_id, requesting_user=current_user)
    return RefundService(db).list_refunds(invoice_id=invoice_id)


@router.get(
    "/{invoice_id}/pdf",
    summary="Download the invoice as a PDF "
    "(your own invoice, or any if you're an admin)",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def get_invoice_pdf(
    invoice_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Same ownership check as every other invoice sub-resource above --
    # 404 if the invoice doesn't exist, 403 if it exists but isn't the
    # caller's (unless they're an admin). Generated entirely in-memory;
    # no file is written to disk and Invoice.pdf_path is untouched.
    invoice = InvoiceService(db).get_invoice(invoice_id, requesting_user=current_user)
    pdf_bytes = InvoicePdfService(db).generate(invoice)
    # Module 3, Phase 4: fires both events together -- in this
    # implementation a PDF is always regenerated fresh on every
    # download (no caching/storage), so "generated" and "downloaded"
    # are always the same moment here.
    audit_service = AuditLogService(db)
    audit_service.record(
        event_type=AuditEventType.PDF_GENERATED,
        entity_type="invoice",
        entity_id=invoice.id,
        description=f"PDF generated for invoice {invoice.invoice_number}",
        actor_id=current_user.id,
        actor_role="admin" if current_user.is_superuser else "customer",
        ip_address=get_client_ip(request),
    )
    audit_service.record(
        event_type=AuditEventType.INVOICE_DOWNLOADED,
        entity_type="invoice",
        entity_id=invoice.id,
        description=f"Invoice {invoice.invoice_number} PDF downloaded",
        actor_id=current_user.id,
        actor_role="admin" if current_user.is_superuser else "customer",
        ip_address=get_client_ip(request),
    )
    db.commit()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'
        },
    )


@router.post(
    "/{invoice_id}/email",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Email the invoice PDF to the customer "
    "(your own invoice, or any if you're an admin)",
)
def email_invoice(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dispatched asynchronously via the existing Celery + Redis
    infrastructure (same non-blocking, dispatch-failure-never-breaks-
    the-request guarantee as every other notification) -- the PDF is
    regenerated inside the task from the existing InvoicePdfService
    (Phase 4), not generated here and passed along, since Celery task
    arguments must be JSON-serializable. Returns 202 (accepted, not
    "sent") since delivery genuinely happens later, asynchronously --
    same reasoning as every other fire-and-forget notification in this
    API.
    """
    invoice = InvoiceService(db).get_invoice(invoice_id, requesting_user=current_user)
    try:
        from app.tasks.notification_tasks import send_invoice_email

        send_invoice_email.delay(str(invoice.id))
    except Exception:  # noqa: BLE001
        # Matches notification_dispatch.notify()'s guarantee: a broker
        # outage must never surface as a request failure.
        pass
    return {"detail": "Invoice email queued for delivery"}
