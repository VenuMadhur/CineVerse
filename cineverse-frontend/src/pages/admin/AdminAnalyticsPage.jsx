import { useEffect, useState } from 'react';
import {
  FiTrendingUp,
  FiUsers,
  FiCreditCard,
  FiRotateCcw,
  FiFileText,
  FiActivity,
} from 'react-icons/fi';
import PageHeader from '../../components/common/PageHeader';
import { Skeleton } from '../../components/common/Skeleton';
import { ErrorState } from '../../components/common/EmptyState';
import TrendChart from '../../components/common/TrendChart';
import BarChart from '../../components/common/BarChart';
import { analyticsService } from '../../services/analyticsService';
import { formatCurrencyBreakdown, formatCurrency } from '../../utils/formatters';

// ------------------------------------------------------------------
// Minimal CSS-only bar chart -- no external charting dependency.
// Uses percentage-width colored bars, appropriate for this admin
// overview page that needs orientation, not pixel-perfect data viz.
// ------------------------------------------------------------------
/**
 * Horizontal bar chart -- now a shared component, see
 * src/components/common/BarChart.jsx (imported below).
 */

/**
 * Lightweight multi-series SVG line chart. No charting library added --
 * follows the same "hand-rolled, CSS-var-themed" approach already
 * established by BarChart above, just for time series instead of
 * categorical data.
 *
 * series: [{ label, colorClass (a Tailwind stroke-* class), values: number[] }]
 * xLabels: string[] (same length as each series' values)
 */
/**
 * Multi-series time-series line chart -- now a shared component,
 * see src/components/common/TrendChart.jsx (imported below). Used
 * here for Subscription Growth, and reused as-is on the customer
 * DashboardPage for the invoice history chart.
 */

function KPICard({ label, value, sub, colorClass = 'text-white' }) {
  return (
    <div className="glass-card p-5">
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`text-2xl font-bold ${colorClass}`}>{value ?? '—'}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

function Section({ icon: Icon, title, children, loading, error }) {
  return (
    <div className="glass-card p-6">
      <div className="mb-5 flex items-center gap-2 text-amber-400">
        <Icon size={18} />
        <span className="text-sm font-semibold uppercase tracking-wide">{title}</span>
      </div>
      {loading && <Skeleton className="h-40 rounded-lg" />}
      {error && !loading && <p className="text-sm text-red-400">{error}</p>}
      {!loading && !error && children}
    </div>
  );
}

function pct(v) {
  if (v == null) return '—';
  return `${Number(v).toFixed(2)}%`;
}

/**
 * Admin Analytics page — surfaces all seven backend analytics endpoints
 * (/analytics/dashboard, /revenue, /subscriptions, /payments, /refunds,
 * /kpis, /invoices) in a single overview. Uses CSS-only bar charts to
 * avoid adding a charting dependency (recharts is not installed).
 * All data is real: no mocks, no hardcoded values.
 */
export default function AdminAnalyticsPage() {
  const [dashboard, setDashboard] = useState(null);
  const [revenue, setRevenue] = useState(null);
  const [subs, setSubs] = useState(null);
  const [payments, setPayments] = useState(null);
  const [refunds, setRefunds] = useState(null);
  const [kpis, setKpis] = useState(null);
  const [invoices, setInvoices] = useState(null);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState({
    dashboard: true,
    revenue: true,
    subs: true,
    payments: true,
    refunds: true,
    kpis: true,
    invoices: true,
  });

  const setLoad = (key, val) => setLoading((p) => ({ ...p, [key]: val }));
  const setErr = (key, msg) => setErrors((p) => ({ ...p, [key]: msg }));

  useEffect(() => {
    analyticsService
      .getDashboard()
      .then(setDashboard)
      .catch(() => setErr('dashboard', 'Failed to load dashboard data.'))
      .finally(() => setLoad('dashboard', false));

    analyticsService
      .getRevenue()
      .then(setRevenue)
      .catch(() => setErr('revenue', 'Failed to load revenue data.'))
      .finally(() => setLoad('revenue', false));

    analyticsService
      .getSubscriptions()
      .then(setSubs)
      .catch(() => setErr('subs', 'Failed to load subscription data.'))
      .finally(() => setLoad('subs', false));

    analyticsService
      .getPayments()
      .then(setPayments)
      .catch(() => setErr('payments', 'Failed to load payment data.'))
      .finally(() => setLoad('payments', false));

    analyticsService
      .getRefunds()
      .then(setRefunds)
      .catch(() => setErr('refunds', 'Failed to load refund data.'))
      .finally(() => setLoad('refunds', false));

    analyticsService
      .getKpis()
      .then(setKpis)
      .catch(() => setErr('kpis', 'Failed to load KPI data.'))
      .finally(() => setLoad('kpis', false));

    analyticsService
      .getInvoiceAnalytics()
      .then(setInvoices)
      .catch(() => setErr('invoices', 'Failed to load invoice analytics.'))
      .finally(() => setLoad('invoices', false));
  }, []);

  // ---- derived display values ----
  const mrrDisplay = dashboard
    ? formatCurrencyBreakdown(dashboard.mrr_by_currency)
    : '—';
  const arrDisplay = dashboard
    ? formatCurrencyBreakdown(dashboard.arr_by_currency)
    : '—';
  const revenueDisplay = dashboard
    ? formatCurrencyBreakdown(dashboard.revenue_by_currency)
    : '—';

  const revenueByMonthItems = (revenue?.revenue_by_month ?? []).slice(-12).map((r) => ({
    label: new Date(r.month).toLocaleDateString('en-US', { month: 'short', year: '2-digit' }),
    value: Number(r.revenue),
    formatted: formatCurrency(r.revenue, 'USD'),
  }));

  const revenueByPlanItems = (revenue?.revenue_by_plan ?? []).slice(0, 8).map((r) => ({
    label: r.plan_name,
    value: Number(r.revenue),
    formatted: formatCurrency(r.revenue, 'USD'),
  }));

  const subsItems = subs
    ? [
        { label: 'Active', value: subs.active_subscriptions, formatted: String(subs.active_subscriptions) },
        { label: 'Trial', value: subs.trial_subscriptions, formatted: String(subs.trial_subscriptions) },
        { label: 'Paused', value: subs.paused_subscriptions, formatted: String(subs.paused_subscriptions) },
        { label: 'Past Due', value: subs.past_due_subscriptions, formatted: String(subs.past_due_subscriptions) },
        { label: 'Cancelled', value: subs.cancelled_subscriptions, formatted: String(subs.cancelled_subscriptions) },
      ]
    : [];

  const paymentItems = payments
    ? [
        { label: 'Succeeded', value: payments.successful_payments, formatted: String(payments.successful_payments) },
        { label: 'Failed', value: payments.failed_payments, formatted: String(payments.failed_payments) },
        { label: 'Pending', value: payments.pending_payments, formatted: String(payments.pending_payments) },
      ]
    : [];

  const invoiceItems = invoices
    ? [
        { label: 'Paid', value: invoices.paid_invoices, formatted: String(invoices.paid_invoices) },
        { label: 'Open', value: invoices.pending_invoices, formatted: String(invoices.pending_invoices) },
        { label: 'Failed', value: invoices.failed_invoices, formatted: String(invoices.failed_invoices) },
        { label: 'Refunded', value: invoices.refunded_invoices, formatted: String(invoices.refunded_invoices) },
      ]
    : [];

  return (
    <div className="animate-fade-in space-y-8">
      <PageHeader
        title="Analytics"
        subtitle="Platform-wide metrics from real data. All figures are live."
      />

      {/* Top KPI cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {loading.dashboard ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="glass-card p-5">
              <Skeleton className="h-4 w-24 rounded mb-2" />
              <Skeleton className="h-8 w-32 rounded" />
            </div>
          ))
        ) : errors.dashboard ? (
          <div className="col-span-full">
            <ErrorState message={errors.dashboard} />
          </div>
        ) : (
          <>
            <KPICard
              label="MRR"
              value={mrrDisplay}
              sub="Monthly Recurring Revenue"
              colorClass="text-emerald-400"
            />
            <KPICard
              label="ARR"
              value={arrDisplay}
              sub="Annualized Run Rate"
              colorClass="text-emerald-400"
            />
            <KPICard
              label="Total Revenue"
              value={revenueDisplay}
              sub="From paid invoices"
              colorClass="text-white"
            />
            <KPICard
              label="Active Subscribers"
              value={dashboard?.active_subscriptions}
              sub={`of ${dashboard?.total_customers} customers`}
            />
          </>
        )}
      </div>

      {/* KPI Rates */}
      <Section icon={FiActivity} title="Subscription & Payment KPIs" loading={loading.kpis} error={errors.kpis}>
        {kpis && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <KPICard
              label="Trial Conversion"
              value={pct(kpis.trial_conversion_rate)}
              sub="Trials → Active"
              colorClass="text-amber-400"
            />
            <KPICard
              label="Monthly Churn"
              value={pct(kpis.monthly_churn_rate)}
              sub="Cancellations / Active"
              colorClass={Number(kpis.monthly_churn_rate) > 5 ? 'text-red-400' : 'text-white'}
            />
            <KPICard
              label="Payment Success"
              value={pct(kpis.payment_success_rate)}
              colorClass="text-emerald-400"
            />
            <KPICard
              label="ARPU"
              value={kpis.arpu != null ? formatCurrency(kpis.arpu, 'USD') : '—'}
              sub="Avg Revenue Per User"
            />
          </div>
        )}
        {kpis?.notes?.length > 0 && (
          <div className="mt-4 space-y-1">
            {kpis.notes.map((note, i) => (
              <p key={i} className="text-xs text-slate-500">
                ℹ️ {note}
              </p>
            ))}
          </div>
        )}
      </Section>

      {/* Subscription growth trend -- real data (kpis.monthly_subscription_growth),
          fetched by the existing getKpis() call but never rendered before now. */}
      <Section
        icon={FiTrendingUp}
        title="Subscription Growth (last 12 months)"
        loading={loading.kpis}
        error={errors.kpis}
      >
        {kpis?.monthly_subscription_growth?.length > 0 ? (
          <TrendChart
            xLabels={kpis.monthly_subscription_growth.map((m) =>
              new Date(m.month).toLocaleDateString(undefined, { month: 'short' })
            )}
            series={[
              {
                label: 'New',
                colorClass: 'stroke-emerald-400 text-emerald-400',
                dotClass: 'bg-emerald-400',
                values: kpis.monthly_subscription_growth.map((m) => m.new_subscriptions),
              },
              {
                label: 'Cancelled',
                colorClass: 'stroke-red-400 text-red-400',
                dotClass: 'bg-red-400',
                values: kpis.monthly_subscription_growth.map((m) => m.cancelled_subscriptions),
              },
            ]}
          />
        ) : (
          <p className="text-sm text-slate-500">No subscription growth data yet.</p>
        )}
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Revenue by month */}
        <Section icon={FiTrendingUp} title="Revenue by Month (last 12)" loading={loading.revenue} error={errors.revenue}>
          {revenueByMonthItems.length > 0 ? (
            <BarChart items={revenueByMonthItems} colorClass="bg-[#E50914]" />
          ) : (
            <p className="text-sm text-slate-500">No revenue data yet.</p>
          )}
        </Section>

        {/* Revenue by plan */}
        <Section icon={FiTrendingUp} title="Revenue by Plan" loading={loading.revenue} error={errors.revenue}>
          {revenueByPlanItems.length > 0 ? (
            <BarChart items={revenueByPlanItems} colorClass="bg-amber-500" />
          ) : (
            <p className="text-sm text-slate-500">No plan revenue data yet.</p>
          )}
        </Section>

        {/* Subscription breakdown */}
        <Section icon={FiUsers} title="Subscription Status" loading={loading.subs} error={errors.subs}>
          {subsItems.length > 0 ? (
            <BarChart items={subsItems} colorClass="bg-sky-500" />
          ) : (
            <p className="text-sm text-slate-500">No subscription data yet.</p>
          )}
          {subs && (
            <p className="mt-3 text-xs text-slate-500">
              Total: {subs.total_subscriptions} subscriptions
            </p>
          )}
        </Section>

        {/* Payments breakdown */}
        <Section icon={FiCreditCard} title="Payment Attempts" loading={loading.payments} error={errors.payments}>
          {paymentItems.length > 0 ? (
            <BarChart items={paymentItems} colorClass="bg-emerald-500" />
          ) : (
            <p className="text-sm text-slate-500">No payment data yet.</p>
          )}
          {payments && (
            <p className="mt-3 text-xs text-slate-500">
              Total: {payments.total_payments} attempts
            </p>
          )}
        </Section>

        {/* Invoice breakdown */}
        <Section icon={FiFileText} title="Invoice Status" loading={loading.invoices} error={errors.invoices}>
          {invoiceItems.length > 0 ? (
            <BarChart items={invoiceItems} colorClass="bg-violet-500" />
          ) : (
            <p className="text-sm text-slate-500">No invoice data yet.</p>
          )}
          {invoices && (
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-slate-500">Outstanding: </span>
                <span className="font-medium text-orange-400">
                  {formatCurrency(invoices.outstanding_invoice_amount, 'USD')}
                </span>
              </div>
              <div>
                <span className="text-slate-500">Avg invoice: </span>
                <span className="font-medium text-white">
                  {formatCurrency(invoices.average_invoice_amount, 'USD')}
                </span>
              </div>
            </div>
          )}
        </Section>

        {/* Refunds */}
        <Section icon={FiRotateCcw} title="Refunds" loading={loading.refunds} error={errors.refunds}>
          {refunds && (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <KPICard
                  label="Completed"
                  value={refunds.completed_refunds}
                  colorClass="text-sky-400"
                />
                <KPICard
                  label="Pending"
                  value={refunds.pending_refunds}
                  colorClass="text-amber-400"
                />
                <KPICard
                  label="Failed"
                  value={refunds.failed_refunds}
                  colorClass="text-red-400"
                />
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] px-4 py-3 text-sm">
                <span className="text-slate-400">Total refunded: </span>
                <span className="font-bold text-sky-400">
                  {formatCurrencyBreakdown(refunds.refunded_amount_by_currency)}
                </span>
              </div>
            </div>
          )}
        </Section>
      </div>
    </div>
  );
}
