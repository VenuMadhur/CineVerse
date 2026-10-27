"""
Pydantic v2 schemas for the Analytics module (Phase 2).

All analytics endpoints are admin-only (see app/api/v1/analytics.py)
and are read-only aggregations over existing tables -- no new
database tables were introduced for this module.
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class CurrencyAmountItem(BaseModel):
    """
    A single currency's amount within a breakdown. Used wherever a
    platform-wide total (revenue, MRR, ARR, refunds) needs to be shown
    without blending potentially different currencies into one
    meaningless number -- Plan.currency/Invoice.currency/
    Refund.currency are all genuinely unconstrained per-record, so an
    admin can create a plan in any currency at any time.
    """
    currency: str = Field(..., description="ISO 4217 currency code, e.g. 'USD', 'INR'.")
    amount: Decimal = Field(..., description="The total for this currency only.")


class DashboardSummaryResponse(BaseModel):
    total_customers: int
    active_customers: int
    trial_customers: int
    cancelled_customers: int
    total_plans: int
    active_subscriptions: int
    cancelled_subscriptions: int
    total_revenue: Decimal = Field(
        ...,
        description="DEPRECATED for display purposes -- kept only for backward compatibility "
        "with existing consumers. This is a single number obtained by summing amounts across "
        "*all* currencies as if they were equivalent, which is financially meaningless the "
        "moment more than one currency is genuinely in use (Plan.currency is unconstrained "
        "per-plan). New UI development should use `revenue_by_currency` instead.",
    )
    mrr: Decimal = Field(
        ...,
        description="DEPRECATED for display purposes -- kept only for backward compatibility. "
        "Same currency-blending caveat as `total_revenue`. New UI development should use "
        "`mrr_by_currency` instead.",
    )
    arr: Decimal = Field(
        ...,
        description="DEPRECATED for display purposes -- kept only for backward compatibility. "
        "Same currency-blending caveat as `total_revenue`. New UI development should use "
        "`arr_by_currency` instead.",
    )
    total_successful_payments: int
    failed_payments: int
    total_refunds: int
    revenue_by_currency: List[CurrencyAmountItem] = Field(
        default=[],
        description="Recognized revenue (paid invoices), broken out by currency. "
        "**Use this field for display** -- never `total_revenue` -- whenever more than one "
        "currency may be in use.",
    )
    mrr_by_currency: List[CurrencyAmountItem] = Field(
        default=[],
        description="Monthly recurring revenue, broken out by currency. "
        "**Use this field for display** -- never `mrr` -- whenever more than one currency may "
        "be in use.",
    )
    arr_by_currency: List[CurrencyAmountItem] = Field(
        default=[],
        description="Annualized run rate (mrr_by_currency x 12 per currency), broken out by "
        "currency. **Use this field for display** -- never `arr`.",
    )


class RevenueByDayItem(BaseModel):
    day: date
    revenue: Decimal


class RevenueByMonthItem(BaseModel):
    month: date  # first day of the month, e.g. 2026-07-01
    revenue: Decimal


class RevenueByYearItem(BaseModel):
    year: int
    revenue: Decimal


class RevenueByPlanItem(BaseModel):
    plan_id: uuid.UUID
    plan_name: str
    revenue: Decimal


class SubscriberByPlanItem(BaseModel):
    """
    Exact database-level count of currently-ACTIVE subscriptions per
    plan -- the same "active" definition already used everywhere else
    on this platform (DashboardSummaryResponse.active_subscriptions,
    SubscriptionAnalyticsResponse.active_subscriptions): status ==
    SubscriptionStatus.ACTIVE specifically, not trial/paused/past_due/
    cancelled. Includes plans with zero active subscribers (a plan
    nobody has subscribed to is still meaningful information for a
    distribution view), which is why this is a LEFT JOIN from Plan
    rather than an inner join from Subscription.
    """
    plan_id: uuid.UUID
    plan_name: str
    subscriber_count: int


class MRRByPlanItem(BaseModel):
    """
    Current-state MRR composition by plan -- today's active
    subscriptions x today's plan prices, normalized to a monthly
    figure (annual plans divided by 12), the exact same math as
    DashboardSummaryResponse.mrr_by_currency. NOT a historical trend:
    there is no plan-price history table in this schema, so this only
    ever represents right now, never a past month. Only includes plans
    with at least one active subscriber (a plan contributing zero MRR
    isn't meaningful in a composition breakdown, unlike
    SubscriberByPlanItem's distribution view where zero is itself
    informative).
    """
    plan_id: uuid.UUID
    plan_name: str
    currency: str
    mrr: Decimal


class RefundTrendItem(BaseModel):
    """
    Real, database-computed monthly refund trend -- only COMPLETED
    refunds (mirrors revenue_by_month only counting PAID invoices),
    grouped by Refund.processed_at (when the refund actually
    completed, not when it was merely requested -- a PENDING refund
    has no processed_at yet and is correctly excluded here, exactly
    parallel to how revenue_by_month excludes unpaid invoices).
    """
    month: date
    refund_count: int
    refund_amount: Decimal


class CustomerTrendItem(BaseModel):
    """
    Real, database-computed count of customers registered per month,
    grouped by Customer.created_at (a genuine, always-populated
    timestamp -- TimestampMixin, same as every other model in this
    project). Unlike MRR, a customer's registration date never
    changes retroactively, so this trend is exact for every month it
    covers, not an approximation.
    """
    month: date
    new_customers: int



class RevenueByCountryItem(BaseModel):
    country: str
    revenue: Decimal


class RevenueByPaymentMethodItem(BaseModel):
    payment_method: str
    revenue: Decimal


class RevenueAnalyticsResponse(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    total_revenue: Decimal
    revenue_by_day: List[RevenueByDayItem] = []
    revenue_by_month: List[RevenueByMonthItem]
    revenue_by_year: List[RevenueByYearItem] = []
    revenue_by_plan: List[RevenueByPlanItem]
    revenue_by_country: List[RevenueByCountryItem] = []
    revenue_by_payment_method: List[RevenueByPaymentMethodItem] = []


class InvoiceAnalyticsResponse(BaseModel):
    """Module 3, Phase 3b. "Pending" maps to this codebase's actual
    InvoiceStatus.OPEN -- the spec's term for an unpaid, not-yet-due-
    or-failed invoice."""
    paid_invoices: int
    pending_invoices: int
    failed_invoices: int
    refunded_invoices: int
    outstanding_invoice_amount: Decimal  # sum of OPEN + FAILED invoices
    average_invoice_amount: Decimal  # across every invoice ever issued, any status


class SubscriptionAnalyticsResponse(BaseModel):
    total_subscriptions: int
    active_subscriptions: int
    trial_subscriptions: int
    paused_subscriptions: int
    past_due_subscriptions: int
    cancelled_subscriptions: int
    # This schema has no "expired" concept -- SubscriptionStatus has no
    # such state (a subscription only ever becomes cancelled, never
    # "expires" on its own). Always 0; kept as an explicit field since
    # the requirement says "if applicable" and callers may reasonably
    # expect the key to exist. See README for the full explanation.
    expired_subscriptions: int = 0


class PaymentTrendItem(BaseModel):
    month: date
    successful: int
    failed: int
    pending: int


class PaymentAnalyticsResponse(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    total_payments: int
    successful_payments: int
    failed_payments: int
    pending_payments: int
    payment_trends: List[PaymentTrendItem]


class RefundAnalyticsResponse(BaseModel):
    total_refunds: int
    # RefundStatus has no "approved"/"rejected" states -- only
    # pending/completed/failed. `completed_refunds` is the closest
    # equivalent to "approved" (money was actually returned);
    # `failed_refunds` is the closest equivalent to "rejected" (the
    # refund did not go through). See README for the full mapping.
    completed_refunds: int
    pending_refunds: int
    failed_refunds: int
    total_refunded_amount: Decimal = Field(
        ...,
        description="DEPRECATED for display purposes -- kept only for backward compatibility "
        "with existing consumers. Blends amounts across all currencies as if they were "
        "equivalent, which is financially meaningless the moment more than one currency is "
        "genuinely in use. New UI development should use `refunded_amount_by_currency` instead.",
    )
    refunded_amount_by_currency: List[CurrencyAmountItem] = Field(
        default=[],
        description="Total refunded amount, broken out by currency. **Use this field for "
        "display** -- never `total_refunded_amount` -- whenever more than one currency may be "
        "in use.",
    )


class MonthlySubscriptionGrowthItem(BaseModel):
    month: date  # first day of the month
    new_subscriptions: int
    cancelled_subscriptions: int
    net_growth: int  # new - cancelled; can be negative


class SubscriptionKPIsResponse(BaseModel):
    """
    Module 3, Phase 3a. Every rate below is `None` (not 0, not a
    fabricated number) when its denominator is zero -- see `notes` for
    a plain-language explanation of any such case. Percentages are
    already rounded to 2 decimal places server-side.
    """
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    trial_conversion_rate: Optional[Decimal] = None
    monthly_churn_rate: Optional[Decimal] = None
    arpu: Optional[Decimal] = None
    clv: Optional[Decimal] = None
    payment_success_rate: Optional[Decimal] = None
    payment_failure_rate: Optional[Decimal] = None
    retry_success_rate: Optional[Decimal] = None
    retry_failure_rate: Optional[Decimal] = None
    monthly_subscription_growth: List[MonthlySubscriptionGrowthItem]
    notes: List[str] = []
