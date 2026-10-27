"""
Analytics APIs (Phase 2, extended in Module 3 Phase 3a) -- powers the Admin Dashboard.

    GET /api/v1/analytics/dashboard      Summary counters across the whole platform
    GET /api/v1/analytics/revenue        Revenue by month, by plan, optional date range
    GET /api/v1/analytics/subscriptions  Subscription status breakdown
    GET /api/v1/analytics/payments       Payment status breakdown + monthly trend
    GET /api/v1/analytics/refunds        Refund status breakdown + total refunded amount
    GET /api/v1/analytics/subscribers-by-plan  Exact active-subscriber count per plan
    GET /api/v1/analytics/mrr-by-plan    Current MRR composition by plan (not historical)
    GET /api/v1/analytics/refunds/trend  Monthly refund count and amount (completed refunds only)
    GET /api/v1/analytics/customers/trend  Monthly new-customer registration count
    GET /api/v1/analytics/kpis           Trial conversion, churn, ARPU, CLV, payment/retry rates, growth
    GET /api/v1/analytics/invoices       Invoice status counts, outstanding & average amount

Every endpoint requires get_current_superuser (admin only) -- a
regular, non-admin user gets 403, exactly like the Plan-mutation and
customer-list endpoints from Phase 1C. This module is read-only: it
never enforces or bypasses Customer ownership (see
app/services/ownership.py) because admins already have unrestricted
access by design -- these endpoints intentionally aggregate across
every customer, which is the entire point of a platform-wide
dashboard.
"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_superuser
from app.core.database import get_db
from app.models.user import User
from app.schemas.analytics import (
    DashboardSummaryResponse,
    InvoiceAnalyticsResponse,
    PaymentAnalyticsResponse,
    RefundAnalyticsResponse,
    RefundTrendItem,
    RevenueAnalyticsResponse,
    SubscriberByPlanItem,
    MRRByPlanItem,
    SubscriptionAnalyticsResponse,
    SubscriptionKPIsResponse,
    CustomerTrendItem,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/dashboard",
    response_model=DashboardSummaryResponse,
    summary="Platform-wide summary counters (admin only)",
    description="`total_revenue`/`mrr`/`arr` are kept for backward compatibility only and blend "
    "all currencies into one number. Use `revenue_by_currency`/`mrr_by_currency`/"
    "`arr_by_currency` for any new UI.",
)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return AnalyticsService(db).get_dashboard_summary()


@router.get(
    "/revenue",
    response_model=RevenueAnalyticsResponse,
    summary="Revenue by month and by plan, with optional date-range filtering (admin only)",
)
def get_revenue_analytics(
    date_from: date | None = Query(None, description="Inclusive start date (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="Inclusive end date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return AnalyticsService(db).get_revenue_analytics(date_from, date_to)


@router.get(
    "/subscriptions",
    response_model=SubscriptionAnalyticsResponse,
    summary="Subscription status breakdown (admin only)",
)
def get_subscription_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return AnalyticsService(db).get_subscription_analytics()


@router.get(
    "/payments",
    response_model=PaymentAnalyticsResponse,
    summary="Payment status breakdown and monthly trend, with optional date-range filtering (admin only)",
)
def get_payment_analytics(
    date_from: date | None = Query(None, description="Inclusive start date (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="Inclusive end date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return AnalyticsService(db).get_payment_analytics(date_from, date_to)


@router.get(
    "/refunds",
    response_model=RefundAnalyticsResponse,
    summary="Refund status breakdown and total refunded amount (admin only)",
    description="`total_refunded_amount` is kept for backward compatibility only and blends "
    "all currencies into one number. Use `refunded_amount_by_currency` for any new UI.",
)
def get_refund_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return AnalyticsService(db).get_refund_analytics()


@router.get(
    "/subscribers-by-plan",
    response_model=list[SubscriberByPlanItem],
    summary="Exact active-subscriber count per plan, including plans with zero subscribers (admin only)",
)
def get_subscribers_by_plan(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return AnalyticsService(db).get_subscribers_by_plan()


@router.get(
    "/mrr-by-plan",
    response_model=list[MRRByPlanItem],
    summary="Current MRR composition by plan -- today's active subscriptions at today's prices (admin only)",
    description="A current-state snapshot, not a historical trend -- there is no plan-price history "
    "table in this schema, so no past-month MRR figure can be honestly reconstructed.",
)
def get_mrr_by_plan(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return AnalyticsService(db).get_mrr_by_plan()


@router.get(
    "/refunds/trend",
    response_model=list[RefundTrendItem],
    summary="Monthly refund count and amount, completed refunds only (admin only)",
    description="Grouped by the month each refund actually completed. A refund still pending has "
    "no completion date yet and is correctly excluded, not counted as zero.",
)
def get_refund_trend(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return AnalyticsService(db).get_refund_trend(date_from, date_to)


@router.get(
    "/customers/trend",
    response_model=list[CustomerTrendItem],
    summary="Monthly new-customer registration count (admin only)",
    description="Grouped by Customer.created_at -- an exact, always-populated registration "
    "timestamp that never changes retroactively, so every month this covers is exact, not approximated.",
)
def get_customer_trend(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return AnalyticsService(db).get_customer_trend(date_from, date_to)


@router.get(
    "/kpis",
    response_model=SubscriptionKPIsResponse,
    summary="Subscription & payment KPIs: trial conversion rate, churn rate, ARPU, CLV, "
    "payment/retry success & failure rates, monthly subscription growth (admin only)",
)
def get_subscription_kpis(
    date_from: date | None = Query(
        None, description="Inclusive start date (YYYY-MM-DD). Also used as the churn period."
    ),
    date_to: date | None = Query(
        None, description="Inclusive end date (YYYY-MM-DD). Also used as the churn period."
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return AnalyticsService(db).get_subscription_kpis(date_from, date_to)


@router.get(
    "/invoices",
    response_model=InvoiceAnalyticsResponse,
    summary="Invoice status counts (paid/pending/failed/refunded), outstanding amount, "
    "and average invoice amount (admin only)",
)
def get_invoice_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    return AnalyticsService(db).get_invoice_analytics()
