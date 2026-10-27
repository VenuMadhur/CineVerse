"""
Analytics Service (Phase 2).

Powers the future Admin Dashboard. Every method here is a read-only
aggregation built entirely on top of the existing repository layer --
no new tables, no duplicated business logic. New repository methods
were added only where a genuine aggregate (SUM/GROUP BY, or a status
filter) didn't already exist; everything else reuses methods that
already existed before this module (e.g. `count_all(status=...)` on
Subscription, or `BaseRepository.count()` for simple totals).
"""
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.enums import InvoiceStatus, PaymentStatus, RefundStatus, RetryStatus, SubscriptionStatus
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.refund_repository import RefundRepository
from app.repositories.retry_queue_repository import RetryQueueRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.analytics import (
    CurrencyAmountItem,
    CustomerTrendItem,
    DashboardSummaryResponse,
    InvoiceAnalyticsResponse,
    MonthlySubscriptionGrowthItem,
    MRRByPlanItem,
    PaymentAnalyticsResponse,
    PaymentTrendItem,
    RefundAnalyticsResponse,
    RefundTrendItem,
    RevenueAnalyticsResponse,
    RevenueByCountryItem,
    RevenueByDayItem,
    RevenueByMonthItem,
    RevenueByPaymentMethodItem,
    RevenueByPlanItem,
    RevenueByYearItem,
    SubscriberByPlanItem,
    SubscriptionAnalyticsResponse,
    SubscriptionKPIsResponse,
)


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db
        self.customer_repository = CustomerRepository(db)
        self.plan_repository = PlanRepository(db)
        self.subscription_repository = SubscriptionRepository(db)
        self.invoice_repository = InvoiceRepository(db)
        self.payment_repository = PaymentRepository(db)
        self.refund_repository = RefundRepository(db)
        self.retry_queue_repository = RetryQueueRepository(db)

    # ------------------------------------------------------------------
    # GET /analytics/dashboard
    # ------------------------------------------------------------------
    def get_dashboard_summary(self) -> DashboardSummaryResponse:
        mrr = self.subscription_repository.monthly_recurring_revenue()
        mrr_rows = self.subscription_repository.monthly_recurring_revenue_by_currency()
        revenue_rows = self.invoice_repository.paid_amount_by_currency()
        return DashboardSummaryResponse(
            total_customers=self.customer_repository.count(),
            active_customers=self.customer_repository.count_active(),
            trial_customers=self.customer_repository.count_by_subscription_status(
                SubscriptionStatus.TRIAL
            ),
            cancelled_customers=self.customer_repository.count_by_subscription_status(
                SubscriptionStatus.CANCELLED
            ),
            total_plans=self.plan_repository.count(),
            active_subscriptions=self.subscription_repository.count_all(
                status=SubscriptionStatus.ACTIVE
            ),
            cancelled_subscriptions=self.subscription_repository.count_all(
                status=SubscriptionStatus.CANCELLED
            ),
            total_revenue=self.invoice_repository.sum_paid_amount(),
            mrr=mrr,
            arr=mrr * 12,
            revenue_by_currency=[
                CurrencyAmountItem(currency=currency, amount=amount)
                for currency, amount in revenue_rows
            ],
            mrr_by_currency=[
                CurrencyAmountItem(currency=currency, amount=amount)
                for currency, amount in mrr_rows
            ],
            arr_by_currency=[
                CurrencyAmountItem(currency=currency, amount=amount * 12)
                for currency, amount in mrr_rows
            ],
            total_successful_payments=self.payment_repository.count_all(
                status=PaymentStatus.SUCCEEDED
            ),
            failed_payments=self.payment_repository.count_all(status=PaymentStatus.FAILED),
            total_refunds=self.refund_repository.count_all(),
        )

    # ------------------------------------------------------------------
    # GET /analytics/revenue
    # ------------------------------------------------------------------
    def get_revenue_analytics(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> RevenueAnalyticsResponse:
        total_revenue = self.invoice_repository.sum_paid_amount(date_from, date_to)

        by_day = self.invoice_repository.revenue_by_day(date_from, date_to)
        by_month = self.invoice_repository.revenue_by_month(date_from, date_to)
        by_year = self.invoice_repository.revenue_by_year(date_from, date_to)
        by_plan = self.invoice_repository.revenue_by_plan(date_from, date_to)
        by_country = self.invoice_repository.revenue_by_country(date_from, date_to)
        by_payment_method = self.invoice_repository.revenue_by_payment_method(date_from, date_to)

        return RevenueAnalyticsResponse(
            date_from=date_from,
            date_to=date_to,
            total_revenue=total_revenue,
            revenue_by_day=[
                RevenueByDayItem(day=day.date(), revenue=revenue) for day, revenue in by_day
            ],
            revenue_by_month=[
                RevenueByMonthItem(month=month.date(), revenue=revenue)
                for month, revenue in by_month
            ],
            revenue_by_year=[
                RevenueByYearItem(year=year.year, revenue=revenue) for year, revenue in by_year
            ],
            revenue_by_plan=[
                RevenueByPlanItem(plan_id=plan_id, plan_name=plan_name, revenue=revenue)
                for plan_id, plan_name, revenue in by_plan
            ],
            revenue_by_country=[
                RevenueByCountryItem(country=country, revenue=revenue)
                for country, revenue in by_country
            ],
            revenue_by_payment_method=[
                RevenueByPaymentMethodItem(payment_method=method, revenue=revenue)
                for method, revenue in by_payment_method
            ],
        )

    # ------------------------------------------------------------------
    # GET /analytics/subscriptions
    # ------------------------------------------------------------------
    def get_subscription_analytics(self) -> SubscriptionAnalyticsResponse:
        active = self.subscription_repository.count_all(status=SubscriptionStatus.ACTIVE)
        trial = self.subscription_repository.count_all(status=SubscriptionStatus.TRIAL)
        paused = self.subscription_repository.count_all(status=SubscriptionStatus.PAUSED)
        past_due = self.subscription_repository.count_all(status=SubscriptionStatus.PAST_DUE)
        cancelled = self.subscription_repository.count_all(status=SubscriptionStatus.CANCELLED)

        return SubscriptionAnalyticsResponse(
            total_subscriptions=active + trial + paused + past_due + cancelled,
            active_subscriptions=active,
            trial_subscriptions=trial,
            paused_subscriptions=paused,
            past_due_subscriptions=past_due,
            cancelled_subscriptions=cancelled,
            expired_subscriptions=0,
        )

    # ------------------------------------------------------------------
    # GET /analytics/payments
    # ------------------------------------------------------------------
    def get_payment_analytics(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> PaymentAnalyticsResponse:
        successful = self.payment_repository.count_all(status=PaymentStatus.SUCCEEDED)
        failed = self.payment_repository.count_all(status=PaymentStatus.FAILED)
        pending = self.payment_repository.count_all(status=PaymentStatus.PENDING)

        trend_rows = self.payment_repository.monthly_trend(date_from, date_to)
        trends_by_month: dict = {}
        for month, status, count in trend_rows:
            key = month.date()
            bucket = trends_by_month.setdefault(
                key, {"successful": 0, "failed": 0, "pending": 0}
            )
            if status == PaymentStatus.SUCCEEDED:
                bucket["successful"] = count
            elif status == PaymentStatus.FAILED:
                bucket["failed"] = count
            elif status == PaymentStatus.PENDING:
                bucket["pending"] = count

        payment_trends = [
            PaymentTrendItem(month=month, **counts)
            for month, counts in sorted(trends_by_month.items())
        ]

        return PaymentAnalyticsResponse(
            date_from=date_from,
            date_to=date_to,
            total_payments=successful + failed + pending,
            successful_payments=successful,
            failed_payments=failed,
            pending_payments=pending,
            payment_trends=payment_trends,
        )

    # ------------------------------------------------------------------
    # GET /analytics/refunds
    # ------------------------------------------------------------------
    def get_refund_analytics(self) -> RefundAnalyticsResponse:
        completed = self.refund_repository.count_all(status=RefundStatus.COMPLETED)
        pending = self.refund_repository.count_all(status=RefundStatus.PENDING)
        failed = self.refund_repository.count_all(status=RefundStatus.FAILED)
        refunded_rows = self.refund_repository.sum_amount_by_currency(
            status=RefundStatus.COMPLETED
        )

        return RefundAnalyticsResponse(
            total_refunds=completed + pending + failed,
            completed_refunds=completed,
            pending_refunds=pending,
            failed_refunds=failed,
            total_refunded_amount=self.refund_repository.sum_amount(status=RefundStatus.COMPLETED),
            refunded_amount_by_currency=[
                CurrencyAmountItem(currency=currency, amount=amount)
                for currency, amount in refunded_rows
            ],
        )

    def get_subscribers_by_plan(self) -> List[SubscriberByPlanItem]:
        """
        GET /analytics/subscribers-by-plan: exact database-level count
        of currently-active subscribers per plan, replacing the
        frontend's previous client-side aggregation over a capped
        sample of subscriptions.
        """
        rows = self.plan_repository.subscriber_counts_by_plan()
        return [
            SubscriberByPlanItem(plan_id=plan_id, plan_name=plan_name, subscriber_count=count)
            for plan_id, plan_name, count in rows
        ]

    def get_mrr_by_plan(self) -> List[MRRByPlanItem]:
        """
        GET /analytics/mrr-by-plan: current MRR composition by plan.
        Only plans with a nonzero contribution are included (see
        MRRByPlanItem's docstring for why this differs from
        subscribers-by-plan's zero-inclusive behavior).
        """
        rows = self.subscription_repository.monthly_recurring_revenue_by_plan()
        return [
            MRRByPlanItem(plan_id=plan_id, plan_name=plan_name, currency=currency, mrr=mrr)
            for plan_id, plan_name, currency, mrr in rows
        ]

    def get_refund_trend(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> List[RefundTrendItem]:
        """
        GET /analytics/refunds/trend: real, database-computed monthly
        refund count and amount -- only ever built from genuinely
        completed refunds (see RefundRepository.refund_trend_by_month
        for why), never fabricated.
        """
        rows = self.refund_repository.refund_trend_by_month(date_from, date_to)
        return [
            RefundTrendItem(month=month.date(), refund_count=count, refund_amount=amount)
            for month, count, amount in rows
        ]

    def get_customer_trend(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> List[CustomerTrendItem]:
        """
        GET /analytics/customers/trend: real, database-computed
        monthly new-customer count -- see
        CustomerRepository.registration_trend_by_month.
        """
        rows = self.customer_repository.registration_trend_by_month(date_from, date_to)
        return [CustomerTrendItem(month=month.date(), new_customers=count) for month, count in rows]

    # ------------------------------------------------------------------
    # GET /analytics/kpis (Module 3, Phase 3a)
    #
    # Every ratio here is computed in Decimal end-to-end -- no float
    # conversion at any point -- and rounded to 2 decimal places only
    # at the very end, when building the response. Repository methods
    # return raw counts/rows; all business/ratio math lives here.
    # ------------------------------------------------------------------
    _PERCENT_QUANT = Decimal("0.01")

    @staticmethod
    def _percentage(numerator: int, denominator: int) -> Optional[Decimal]:
        if denominator == 0:
            return None
        return (Decimal(numerator) / Decimal(denominator) * Decimal(100)).quantize(
            AnalyticsService._PERCENT_QUANT, rounding=ROUND_HALF_UP
        )

    @staticmethod
    def _default_churn_period(date_from: Optional[date], date_to: Optional[date]) -> tuple:
        """
        If no period is supplied, defaults to the last full calendar
        month (documented explicitly, per the agreed definitions --
        an all-time churn rate isn't a meaningful single number).
        """
        if date_from is not None and date_to is not None:
            return date_from, date_to
        today = datetime.now(timezone.utc).date()
        first_of_this_month = today.replace(day=1)
        last_day_of_prev_month = first_of_this_month - timedelta(days=1)
        first_of_prev_month = last_day_of_prev_month.replace(day=1)
        return first_of_prev_month, last_day_of_prev_month

    def get_subscription_kpis(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> SubscriptionKPIsResponse:
        notes: list[str] = []
        period_from, period_to = self._default_churn_period(date_from, date_to)
        if date_from is None and date_to is None:
            notes.append(
                f"No period supplied for churn rate; defaulted to the last full "
                f"calendar month ({period_from} to {period_to})."
            )
        period_from_dt = datetime(
            period_from.year, period_from.month, period_from.day, tzinfo=timezone.utc
        )
        period_to_dt = datetime(
            period_to.year, period_to.month, period_to.day, 23, 59, 59, tzinfo=timezone.utc
        )

        # ---- Trial Conversion Rate ----
        # Converted / (Converted + Cancelled-from-trial) x 100.
        # Subscriptions still in an open trial are excluded entirely --
        # their outcome isn't known yet.
        exit_counts = self.subscription_repository.trial_exit_counts()
        converted = exit_counts.get(SubscriptionStatus.ACTIVE, 0)
        cancelled_from_trial = exit_counts.get(SubscriptionStatus.CANCELLED, 0)
        completed_trials = converted + cancelled_from_trial
        trial_conversion_rate = self._percentage(converted, completed_trials)
        if completed_trials == 0:
            notes.append("Trial conversion rate is undefined: no trials have been completed yet.")

        # ---- Monthly Churn Rate ----
        # Cancelled during the period / active at the start of the period x 100.
        active_at_period_start = self.subscription_repository.count_active_as_of(period_from_dt)
        cancelled_in_period = self.subscription_repository.count_cancelled_between(
            period_from_dt, period_to_dt
        )
        monthly_churn_rate = self._percentage(cancelled_in_period, active_at_period_start)
        if active_at_period_start == 0:
            notes.append(
                "Churn rate is undefined: no subscriptions were active at the start of the period."
            )

        # ---- ARPU ----
        # MRR / Active Subscription Count (both already computed elsewhere; reused, not duplicated).
        mrr = self.subscription_repository.monthly_recurring_revenue()
        active_now = self.subscription_repository.count_all(status=SubscriptionStatus.ACTIVE)
        arpu = (mrr / Decimal(active_now)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if active_now > 0 else None
        if active_now == 0:
            notes.append("ARPU is undefined: there are no active subscriptions.")

        # ---- CLV ----
        # ARPU / Monthly Churn Rate (as a decimal fraction, not a percentage).
        clv = None
        if arpu is None:
            notes.append("CLV is undefined because ARPU is undefined (no active subscriptions).")
        elif monthly_churn_rate is None:
            notes.append(
                "CLV is undefined because the churn rate itself is undefined for this "
                "period (see the churn rate note above)."
            )
        elif monthly_churn_rate == 0:
            notes.append(
                "CLV is undefined because the churn rate is 0% for this period "
                "(division by zero -- customer lifetime would be infinite)."
            )
        else:
            churn_fraction = monthly_churn_rate / Decimal(100)
            clv = (arpu / churn_fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # ---- Payment Success / Failure Rate ----
        # SUCCEEDED / (SUCCEEDED + FAILED) x 100. PENDING excluded -- not yet concluded.
        payment_succeeded = self.payment_repository.count_all(
            status=PaymentStatus.SUCCEEDED, date_from=date_from, date_to=date_to
        )
        payment_failed = self.payment_repository.count_all(
            status=PaymentStatus.FAILED, date_from=date_from, date_to=date_to
        )
        payment_success_rate = self._percentage(payment_succeeded, payment_succeeded + payment_failed)
        payment_failure_rate = (
            (Decimal(100) - payment_success_rate) if payment_success_rate is not None else None
        )
        if payment_succeeded + payment_failed == 0:
            notes.append(
                "Payment success/failure rate is undefined: no concluded (succeeded or "
                "failed) payments exist for this period."
            )

        # ---- Retry Success / Failure Rate ----
        # RetryQueue SUCCEEDED / (SUCCEEDED + FAILED) x 100. PENDING and
        # CANCELLED excluded -- neither represents a concluded attempt.
        retry_succeeded = self.retry_queue_repository.count_all(retry_status=RetryStatus.SUCCEEDED)
        retry_failed = self.retry_queue_repository.count_all(retry_status=RetryStatus.FAILED)
        retry_success_rate = self._percentage(retry_succeeded, retry_succeeded + retry_failed)
        retry_failure_rate = (
            (Decimal(100) - retry_success_rate) if retry_success_rate is not None else None
        )
        if retry_succeeded + retry_failed == 0:
            notes.append(
                "Retry success/failure rate is undefined: no concluded (succeeded or "
                "failed) retry attempts exist."
            )

        # ---- Monthly Subscription Growth (trend, not a percentage) ----
        growth_rows = self.subscription_repository.monthly_subscription_growth(date_from, date_to)
        growth_items = [
            MonthlySubscriptionGrowthItem(
                month=month.date(),
                new_subscriptions=new_count,
                cancelled_subscriptions=cancelled_count,
                net_growth=new_count - cancelled_count,
            )
            for month, new_count, cancelled_count in growth_rows
        ]

        return SubscriptionKPIsResponse(
            date_from=date_from,
            date_to=date_to,
            trial_conversion_rate=trial_conversion_rate,
            monthly_churn_rate=monthly_churn_rate,
            arpu=arpu,
            clv=clv,
            payment_success_rate=payment_success_rate,
            payment_failure_rate=payment_failure_rate,
            retry_success_rate=retry_success_rate,
            retry_failure_rate=retry_failure_rate,
            monthly_subscription_growth=growth_items,
            notes=notes,
        )

    # ------------------------------------------------------------------
    # GET /analytics/invoices (Module 3, Phase 3b)
    # ------------------------------------------------------------------
    def get_invoice_analytics(self) -> InvoiceAnalyticsResponse:
        counts = self.invoice_repository.count_by_status()
        return InvoiceAnalyticsResponse(
            paid_invoices=counts.get(InvoiceStatus.PAID, 0),
            pending_invoices=counts.get(InvoiceStatus.OPEN, 0),
            failed_invoices=counts.get(InvoiceStatus.FAILED, 0),
            refunded_invoices=counts.get(InvoiceStatus.REFUNDED, 0),
            outstanding_invoice_amount=self.invoice_repository.sum_outstanding_amount(),
            average_invoice_amount=self.invoice_repository.average_invoice_amount().quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
        )
