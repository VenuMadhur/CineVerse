"""
Report data gathering (Phase 5).

This service answers "what goes in each report" -- and nothing else.
It contains zero aggregation logic of its own: every summary number
comes from the existing `AnalyticsService` (Phase 2), and every
row-level listing comes from the existing repository `list_all`
methods already used elsewhere in the API. `ReportExportService`
(a separate module) is responsible for turning what this service
returns into CSV/XLSX/PDF bytes.

Reports are generated synchronously within a single request -- there
is no background job queue for this (explicitly out of scope for this
phase). `_ROW_LIMIT` is a pragmatic ceiling on row-level detail data,
appropriate for this project's demo/portfolio scale; a platform with a
genuinely large dataset would want a background export job instead,
which is exactly why one wasn't built here without being asked for.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.enums import RetryStatus, SubscriptionStatus
from app.repositories.billing_cycle_repository import BillingCycleRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.refund_repository import RefundRepository
from app.repositories.retry_queue_repository import RetryQueueRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.services.analytics_service import AnalyticsService

_ROW_LIMIT = 10_000


@dataclass
class ReportData:
    """
    Generic container every report type is reshaped into before export.
    `summary` is a flat {label: value} dict (rendered as a small
    key/value block). `columns`/`rows` are the row-level detail table
    (rows are plain dicts keyed by column).
    """
    title: str
    summary: dict[str, Any] = field(default_factory=dict)
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.analytics_service = AnalyticsService(db)
        self.customer_repository = CustomerRepository(db)
        self.subscription_repository = SubscriptionRepository(db)
        self.retry_queue_repository = RetryQueueRepository(db)
        self.payment_repository = PaymentRepository(db)
        self.refund_repository = RefundRepository(db)
        self.invoice_repository = InvoiceRepository(db)
        self.billing_cycle_repository = BillingCycleRepository(db)

    def revenue_report(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> ReportData:
        analytics = self.analytics_service.get_revenue_analytics(date_from, date_to)
        summary = {
            "Total Revenue": str(analytics.total_revenue),
            "Date From": str(date_from) if date_from else "All time",
            "Date To": str(date_to) if date_to else "All time",
        }
        rows = [
            {"Month": item.month.isoformat(), "Revenue": str(item.revenue)}
            for item in analytics.revenue_by_month
        ]
        # Revenue-by-plan is genuinely useful detail too, but a single
        # flat table needs one row shape -- appended as clearly-labeled
        # extra rows rather than a second, differently-shaped table, so
        # CSV export (which can only ever be one flat table) still
        # carries this information instead of silently dropping it.
        for item in analytics.revenue_by_plan:
            rows.append({"Month": f"Plan: {item.plan_name}", "Revenue": str(item.revenue)})
        return ReportData(
            title="Revenue Report", summary=summary, columns=["Month", "Revenue"], rows=rows
        )

    def customer_report(self) -> ReportData:
        dashboard = self.analytics_service.get_dashboard_summary()
        summary = {
            "Total Customers": dashboard.total_customers,
            "Active Customers": dashboard.active_customers,
        }
        customers = self.customer_repository.list_all(skip=0, limit=_ROW_LIMIT)
        columns = ["Name", "Email", "Country", "Phone", "Created At"]
        rows = [
            {
                "Name": c.name,
                "Email": c.email,
                "Country": c.country,
                "Phone": c.phone_number or "",
                "Created At": c.created_at.strftime("%Y-%m-%d"),
            }
            for c in customers
        ]
        return ReportData(title="Customer Report", summary=summary, columns=columns, rows=rows)

    def subscription_report(self) -> ReportData:
        analytics = self.analytics_service.get_subscription_analytics()
        summary = {
            "Total Subscriptions": analytics.total_subscriptions,
            "Active": analytics.active_subscriptions,
            "Trial": analytics.trial_subscriptions,
            "Paused": analytics.paused_subscriptions,
            "Past Due": analytics.past_due_subscriptions,
            "Cancelled": analytics.cancelled_subscriptions,
        }
        subscriptions = self.subscription_repository.list_all(skip=0, limit=_ROW_LIMIT)
        columns = ["Subscription ID", "Customer ID", "Plan ID", "Status", "Trial Ends", "Activated", "Created At"]
        rows = [
            {
                "Subscription ID": str(s.id),
                "Customer ID": str(s.customer_id),
                "Plan ID": str(s.plan_id),
                "Status": s.status.value,
                "Trial Ends": s.trial_ends_at.strftime("%Y-%m-%d") if s.trial_ends_at else "",
                "Activated": s.activated_at.strftime("%Y-%m-%d") if s.activated_at else "",
                "Created At": s.created_at.strftime("%Y-%m-%d"),
            }
            for s in subscriptions
        ]
        return ReportData(title="Subscription Report", summary=summary, columns=columns, rows=rows)

    def payment_report(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> ReportData:
        analytics = self.analytics_service.get_payment_analytics(date_from, date_to)
        summary = {
            "Total Payments": analytics.total_payments,
            "Successful": analytics.successful_payments,
            "Failed": analytics.failed_payments,
            "Pending": analytics.pending_payments,
            "Date From": str(date_from) if date_from else "All time",
            "Date To": str(date_to) if date_to else "All time",
        }
        payments = self.payment_repository.list_all(
            skip=0, limit=_ROW_LIMIT, date_from=date_from, date_to=date_to
        )
        columns = ["Payment ID", "Invoice ID", "Amount", "Currency", "Status", "Method", "Processed At"]
        rows = [
            {
                "Payment ID": str(p.id),
                "Invoice ID": str(p.invoice_id),
                "Amount": str(p.amount),
                "Currency": p.currency,
                "Status": p.status.value,
                "Method": p.payment_method,
                "Processed At": p.processed_at.strftime("%Y-%m-%d %H:%M") if p.processed_at else "",
            }
            for p in payments
        ]
        return ReportData(title="Payment Report", summary=summary, columns=columns, rows=rows)

    def refund_report(self) -> ReportData:
        analytics = self.analytics_service.get_refund_analytics()
        summary = {
            "Total Refunds": analytics.total_refunds,
            "Completed": analytics.completed_refunds,
            "Pending": analytics.pending_refunds,
            "Failed": analytics.failed_refunds,
            "Total Refunded Amount": str(analytics.total_refunded_amount),
        }
        refunds = self.refund_repository.list_all(skip=0, limit=_ROW_LIMIT)
        columns = ["Refund ID", "Invoice ID", "Customer ID", "Amount", "Currency", "Status", "Reason", "Created At"]
        rows = [
            {
                "Refund ID": str(r.id),
                "Invoice ID": str(r.invoice_id),
                "Customer ID": str(r.customer_id),
                "Amount": str(r.amount),
                "Currency": r.currency,
                "Status": r.status.value,
                "Reason": r.reason,
                "Created At": r.created_at.strftime("%Y-%m-%d"),
            }
            for r in refunds
        ]
        return ReportData(title="Refund Report", summary=summary, columns=columns, rows=rows)

    # ------------------------------------------------------------------
    # Tax Reports (Module 3, Phase 2b)
    # ------------------------------------------------------------------
    _PERIOD_DIMENSIONS = {"daily": "day", "weekly": "week", "monthly": "month", "yearly": "year"}

    def tax_report(
        self,
        dimension: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> ReportData:
        """
        Covers all 9 Module 3 Tax Report views via one method, keyed
        by `dimension`: daily/weekly/monthly/yearly (tax collection
        over time), country, state, plan, customer, payment_method.
        Every dimension sums the same, already-correct
        `Invoice.tax_amount` (computed by TaxService at invoice
        generation time, Phase 2a) -- this method aggregates, it never
        recalculates tax.
        """
        summary = {
            "Dimension": dimension.replace("_", " ").title(),
            "Date From": str(date_from) if date_from else "All time",
            "Date To": str(date_to) if date_to else "All time",
        }

        if dimension in self._PERIOD_DIMENSIONS:
            period = self._PERIOD_DIMENSIONS[dimension]
            data = self.invoice_repository.tax_collection_by_period(period, date_from, date_to)
            columns = ["Period", "Tax Collected"]
            rows = [
                {"Period": period_start.strftime("%Y-%m-%d"), "Tax Collected": str(tax)}
                for period_start, tax in data
            ]
        elif dimension == "country":
            data = self.invoice_repository.tax_by_country(date_from, date_to)
            columns = ["Country", "Tax Collected"]
            rows = [{"Country": country, "Tax Collected": str(tax)} for country, tax in data]
        elif dimension == "state":
            data = self.invoice_repository.tax_by_state(date_from, date_to)
            columns = ["State", "Tax Collected"]
            rows = [{"State": state, "Tax Collected": str(tax)} for state, tax in data]
        elif dimension == "plan":
            data = self.invoice_repository.tax_by_plan(date_from, date_to)
            columns = ["Plan", "Tax Collected"]
            rows = [{"Plan": plan_name, "Tax Collected": str(tax)} for _id, plan_name, tax in data]
        elif dimension == "customer":
            data = self.invoice_repository.tax_by_customer(date_from, date_to)
            columns = ["Customer", "Tax Collected"]
            rows = [
                {"Customer": customer_name, "Tax Collected": str(tax)}
                for _id, customer_name, tax in data
            ]
        elif dimension == "payment_method":
            data = self.invoice_repository.tax_by_payment_method(date_from, date_to)
            columns = ["Payment Method", "Tax Collected"]
            rows = [
                {"Payment Method": method, "Tax Collected": str(tax)} for method, tax in data
            ]
        else:
            raise ValueError(f"Unknown tax report dimension: {dimension}")

        total_tax = sum((row_data[-1] for row_data in data), Decimal("0")) if data else Decimal("0")
        summary["Total Tax Collected"] = str(total_tax)

        return ReportData(
            title=f"Tax Report ({summary['Dimension']})", summary=summary, columns=columns, rows=rows
        )

    # ------------------------------------------------------------------
    # Customer Reports (Module 3, Phase 3c)
    # ------------------------------------------------------------------
    def customer_insights_report(
        self, dimension: str, within_days: Optional[int] = None, limit: int = 20
    ) -> ReportData:
        """
        Covers all 4 Module 3 "Customer Reports" views, keyed by
        `dimension`: top_paying, near_renewal, failed_payments,
        past_due. Each row-level listing reuses an existing repository
        method (or a small, narrowly-scoped new one added in this
        phase) -- no aggregation logic lives here, matching this
        service's existing "gathers, never computes" role.
        """
        summary = {"Dimension": dimension.replace("_", " ").title()}

        if dimension == "top_paying":
            data = self.invoice_repository.top_paying_customers(limit=limit)
            columns = ["Customer", "Email", "Total Paid"]
            rows = [
                {"Customer": name, "Email": email, "Total Paid": str(total)}
                for _id, name, email, total in data
            ]
            summary["Showing"] = f"Top {limit} customers by total paid"

        elif dimension == "near_renewal":
            window_days = within_days or settings.RENEWAL_REMINDER_DAYS
            as_of = datetime.now(timezone.utc)
            until = as_of + timedelta(days=window_days)
            data = self.billing_cycle_repository.customers_near_renewal(as_of, until)
            columns = ["Customer", "Email", "Plan", "Renewal Date"]
            rows = [
                {
                    "Customer": name,
                    "Email": email,
                    "Plan": plan_name,
                    "Renewal Date": renewal_date.strftime("%Y-%m-%d"),
                }
                for _id, name, email, plan_name, renewal_date in data
            ]
            summary["Window"] = f"Next {window_days} day(s)"

        elif dimension == "failed_payments":
            data = self.payment_repository.customers_with_failed_payments()
            columns = ["Customer", "Email", "Failed Payment Count", "Most Recent Failure"]
            rows = [
                {
                    "Customer": name,
                    "Email": email,
                    "Failed Payment Count": count,
                    "Most Recent Failure": most_recent.strftime("%Y-%m-%d") if most_recent else "",
                }
                for _id, name, email, count, most_recent in data
            ]

        elif dimension == "past_due":
            data = self.subscription_repository.customers_by_status(SubscriptionStatus.PAST_DUE)
            columns = ["Customer", "Email", "Plan"]
            rows = [
                {"Customer": name, "Email": email, "Plan": plan_name}
                for _id, name, email, plan_name, _sub_id in data
            ]

        else:
            raise ValueError(f"Unknown customer insights dimension: {dimension}")

        summary["Total Rows"] = len(rows)
        return ReportData(
            title=f"Customer Insights ({summary['Dimension']})",
            summary=summary,
            columns=columns,
            rows=rows,
        )

    # ------------------------------------------------------------------
    # Operational Reports (Module 3, Phase 3d)
    #
    # retry_queue/retry_success/retry_failure all reuse the existing
    # RetryQueueRepository.list_all() (Phase 1a) with a different
    # retry_status filter -- no new repository method needed for any
    # of the three. Only cancelled_due_to_failure needed one new,
    # narrowly-scoped query.
    # ------------------------------------------------------------------
    def operational_report(self, dimension: str) -> ReportData:
        summary = {"Dimension": dimension.replace("_", " ").title()}

        if dimension in ("retry_queue", "retry_success", "retry_failure"):
            status_filter = {
                "retry_queue": None,
                "retry_success": RetryStatus.SUCCEEDED,
                "retry_failure": RetryStatus.FAILED,
            }[dimension]
            entries = self.retry_queue_repository.list_all(
                retry_status=status_filter, limit=_ROW_LIMIT
            )
            columns = ["Customer", "Invoice", "Retry Attempt", "Status", "Scheduled Date", "Failure Reason"]
            rows = [
                {
                    "Customer": entry.customer.name if entry.customer else "",
                    "Invoice": entry.invoice.invoice_number if entry.invoice else "",
                    "Retry Attempt": entry.retry_attempt,
                    "Status": entry.retry_status.value,
                    "Scheduled Date": entry.scheduled_retry_date.strftime("%Y-%m-%d"),
                    "Failure Reason": entry.failure_reason or "",
                }
                for entry in entries
            ]

        elif dimension == "cancelled_due_to_failure":
            data = self.subscription_repository.customers_cancelled_for_payment_failure()
            columns = ["Customer", "Email", "Plan", "Cancelled Date"]
            rows = [
                {
                    "Customer": name,
                    "Email": email,
                    "Plan": plan_name,
                    "Cancelled Date": cancelled_at.strftime("%Y-%m-%d"),
                }
                for _id, name, email, plan_name, cancelled_at in data
            ]

        else:
            raise ValueError(f"Unknown operational report dimension: {dimension}")

        summary["Total Rows"] = len(rows)
        return ReportData(
            title=f"Operational Report ({summary['Dimension']})",
            summary=summary,
            columns=columns,
            rows=rows,
        )
