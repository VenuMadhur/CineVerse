"""
Reports & Export APIs (Phase 5, extended in Module 3 Phase 2b) -- admin-only.

    GET /api/v1/reports/revenue?format=&date_from=&date_to=
    GET /api/v1/reports/customers?format=
    GET /api/v1/reports/subscriptions?format=
    GET /api/v1/reports/payments?format=&date_from=&date_to=
    GET /api/v1/reports/refunds?format=
    GET /api/v1/reports/tax?dimension=&format=&date_from=&date_to=

`format` is one of csv|xlsx|pdf (default csv). Date-range filtering is
only offered where the underlying analytics already support it
(revenue, payments) -- matching Phase 2 exactly rather than inventing
new filtering the analytics layer doesn't have.

Every endpoint requires get_current_superuser, same as every other
admin-only route in this API (Plans mutation, customer list,
analytics). Report generation is synchronous, within a single request
-- there is no background job queue for this (out of scope for this
phase).
"""
from datetime import date

from fastapi import APIRouter, Depends, Query, Response

from sqlalchemy.orm import Session

from app.api.deps import get_current_superuser
from app.core.database import get_db
from app.models.user import User
from app.services.report_export_service import ReportExportService
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports"])

_FORMAT_QUERY = Query("csv", pattern="^(csv|xlsx|pdf)$", description="Export format: csv, xlsx, or pdf")
_TAX_DIMENSIONS = "^(daily|weekly|monthly|yearly|country|state|plan|customer|payment_method)$"
_CUSTOMER_INSIGHTS_DIMENSIONS = "^(top_paying|near_renewal|failed_payments|past_due)$"
_OPERATIONAL_DIMENSIONS = "^(retry_queue|retry_success|retry_failure|cancelled_due_to_failure)$"


def _respond(content: bytes, media_type: str, extension: str, report_name: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{report_name}.{extension}"'},
    )


@router.get("/revenue", summary="Revenue report: export as CSV, Excel, or PDF (admin only)")
def get_revenue_report(
    format: str = _FORMAT_QUERY,
    date_from: date | None = Query(None, description="Inclusive start date (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="Inclusive end date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    report = ReportService(db).revenue_report(date_from, date_to)
    content, media_type, extension = ReportExportService().export(report, format)
    return _respond(content, media_type, extension, "revenue-report")


@router.get("/customers", summary="Customer report: export as CSV, Excel, or PDF (admin only)")
def get_customer_report(
    format: str = _FORMAT_QUERY,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    report = ReportService(db).customer_report()
    content, media_type, extension = ReportExportService().export(report, format)
    return _respond(content, media_type, extension, "customer-report")


@router.get("/subscriptions", summary="Subscription report: export as CSV, Excel, or PDF (admin only)")
def get_subscription_report(
    format: str = _FORMAT_QUERY,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    report = ReportService(db).subscription_report()
    content, media_type, extension = ReportExportService().export(report, format)
    return _respond(content, media_type, extension, "subscription-report")


@router.get("/payments", summary="Payment report: export as CSV, Excel, or PDF (admin only)")
def get_payment_report(
    format: str = _FORMAT_QUERY,
    date_from: date | None = Query(None, description="Inclusive start date (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="Inclusive end date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    report = ReportService(db).payment_report(date_from, date_to)
    content, media_type, extension = ReportExportService().export(report, format)
    return _respond(content, media_type, extension, "payment-report")


@router.get("/refunds", summary="Refund report: export as CSV, Excel, or PDF (admin only)")
def get_refund_report(
    format: str = _FORMAT_QUERY,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    report = ReportService(db).refund_report()
    content, media_type, extension = ReportExportService().export(report, format)
    return _respond(content, media_type, extension, "refund-report")


@router.get(
    "/tax",
    summary="Tax report: daily/weekly/monthly/yearly collection, or by country/state/plan/"
    "customer/payment method -- export as CSV, Excel, or PDF (admin only)",
)
def get_tax_report(
    dimension: str = Query(
        ..., pattern=_TAX_DIMENSIONS, description="One of the 9 Module 3 tax report views"
    ),
    format: str = _FORMAT_QUERY,
    date_from: date | None = Query(None, description="Inclusive start date (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="Inclusive end date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    report = ReportService(db).tax_report(dimension, date_from, date_to)
    content, media_type, extension = ReportExportService().export(report, format)
    return _respond(content, media_type, extension, f"tax-report-{dimension}")


@router.get(
    "/customer-insights",
    summary="Customer report: top paying customers, near renewal, with failed payments, "
    "or in past_due -- export as CSV, Excel, or PDF (admin only)",
)
def get_customer_insights_report(
    dimension: str = Query(
        ..., pattern=_CUSTOMER_INSIGHTS_DIMENSIONS, description="One of the 4 Module 3 customer report views"
    ),
    format: str = _FORMAT_QUERY,
    within_days: int | None = Query(
        None, ge=1, description="Only for dimension=near_renewal; defaults to RENEWAL_REMINDER_DAYS"
    ),
    limit: int = Query(20, ge=1, le=200, description="Only for dimension=top_paying"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    report = ReportService(db).customer_insights_report(dimension, within_days, limit)
    content, media_type, extension = ReportExportService().export(report, format)
    return _respond(content, media_type, extension, f"customer-insights-{dimension}")


@router.get(
    "/operational",
    summary="Operational report: retry queue, retry success, retry failure, or subscriptions "
    "cancelled due to payment failure -- export as CSV, Excel, or PDF (admin only)",
)
def get_operational_report(
    dimension: str = Query(
        ..., pattern=_OPERATIONAL_DIMENSIONS, description="One of the 4 Module 3 operational report views"
    ),
    format: str = _FORMAT_QUERY,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    report = ReportService(db).operational_report(dimension)
    content, media_type, extension = ReportExportService().export(report, format)
    return _respond(content, media_type, extension, f"operational-report-{dimension}")
