import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FiUsers,
  FiDollarSign,
  FiTrendingUp,
  FiFilm,
  FiCreditCard,
  FiPieChart,
  FiActivity,
  FiBarChart2,
  FiRepeat,
  FiTag,
  FiRotateCcw,
} from 'react-icons/fi';
import PageHeader from '../../components/common/PageHeader';
import SectionCard from '../../components/common/SectionCard';
import StatCard from '../../components/dashboard/StatCard';
import TrendChart from '../../components/common/TrendChart';
import DonutChart from '../../components/common/DonutChart';
import BarChart from '../../components/common/BarChart';
import RecentActivity from '../../components/dashboard/RecentActivity';
import MiniSparkline from '../../components/common/MiniSparkline';
import MiniRing from '../../components/common/MiniRing';
import { SkeletonStatGrid, Skeleton } from '../../components/common/Skeleton';
import { ErrorState, EmptyState } from '../../components/common/EmptyState';
import { analyticsService } from '../../services/analyticsService';
import { customerService } from '../../services/customerService';
import { auditLogService } from '../../services/auditLogService';
import { formatCurrency, formatCurrencyBreakdown, formatDate } from '../../utils/formatters';

/**
 * Admin Dashboard -- visual-first: a compact 4-metric KPI strip (each
 * a real, meaningfully-sized visualization, not a flat number or a
 * barely-visible dot), the Revenue Trend as the single large hero
 * chart, then five rows of paired secondary/business/recent
 * analytics. All data comes from analytics/customer/audit-log
 * endpoints -- no fabricated figures.
 *
 * KPI strip, each backed by genuinely real data, no duplicate fetches:
 *   - Customers: area sparkline of GET /analytics/customers/trend
 *     (real, since Customer.created_at is set exactly once at
 *     registration and never changes retroactively). Renders exactly
 *     as many points as genuinely exist -- no padded/fabricated
 *     months, and a single real month renders as a single honest dot
 *     rather than being hidden.
 *   - Revenue: area sparkline reusing the SAME revenue_by_month data
 *     already fetched for the big Revenue Trend chart below -- no
 *     second API call. Currency is derived from the real
 *     revenue_by_currency breakdown, never hardcoded.
 *   - Active Subscriptions: a larger, more balanced ring (56px, up
 *     from 36px) reusing the SAME subscription counts already
 *     fetched for the Subscription Distribution donut below -- no
 *     second API call. The percentage is computed from those same
 *     real active/total figures, never hardcoded.
 *   - MRR: GET /analytics/mrr-by-plan -- a real, CURRENT-STATE MRR
 *     composition (today's active subscriptions x today's plan
 *     prices, the exact same normalization as
 *     DashboardSummaryResponse.mrr_by_currency), shown as a compact
 *     per-plan bar breakdown. Deliberately NOT a historical trend:
 *     Plan.price has no history table anywhere in this schema
 *     (confirmed by inspection), so reconstructing past MRR would
 *     require assuming today's prices applied historically -- wrong
 *     for any plan whose price was ever changed. ARR (=MRR x 12,
 *     exact, not derived from history) remains shown as context.
 *
 * Plan Distribution and Refund Trend are real, exact database-level
 * aggregates (GET /analytics/subscribers-by-plan, GET
 * /analytics/refunds/trend). Subscription Growth
 * (kpis.monthly_subscription_growth) remains the honest substitute
 * for a literal "customer growth" chart in that slot, now that the
 * Customers KPI card covers true customer growth instead.
 */
export default function AdminDashboardPage() {
  const [summary, setSummary] = useState(null);
  const [refunds, setRefunds] = useState(null);
  const [refundTrend, setRefundTrend] = useState([]);
  const [revenue, setRevenue] = useState(null);
  const [subscriptions, setSubscriptions] = useState(null);
  const [payments, setPayments] = useState(null);
  const [kpis, setKpis] = useState(null);
  const [subscribersByPlan, setSubscribersByPlan] = useState([]);
  const [mrrByPlan, setMrrByPlan] = useState([]);
  const [customerTrend, setCustomerTrend] = useState([]);
  const [recentCustomers, setRecentCustomers] = useState([]);
  const [recentAudit, setRecentAudit] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        dashboard,
        refundStats,
        refundTrendData,
        revenueStats,
        subStats,
        paymentStats,
        kpiStats,
        customers,
        audit,
        planDist,
        customerTrendData,
        mrrByPlanData,
      ] = await Promise.all([
        analyticsService.getDashboard(),
        analyticsService.getRefunds(),
        analyticsService.getRefundTrend(),
        analyticsService.getRevenue(),
        analyticsService.getSubscriptions(),
        analyticsService.getPayments(),
        analyticsService.getKpis(),
        customerService.list({ page: 1, pageSize: 5 }),
        auditLogService.list({ page: 1, pageSize: 6 }),
        analyticsService.getSubscribersByPlan(),
        analyticsService.getCustomerTrend(),
        analyticsService.getMrrByPlan(),
      ]);
      setSummary(dashboard);
      setRefunds(refundStats);
      setRefundTrend(refundTrendData);
      setRevenue(revenueStats);
      setSubscriptions(subStats);
      setPayments(paymentStats);
      setKpis(kpiStats);
      setRecentCustomers(customers.items);
      setRecentAudit(audit.items);
      setSubscribersByPlan(planDist);
      setCustomerTrend(customerTrendData);
      setMrrByPlan(mrrByPlanData);
    } catch (err) {
      setError(err?.response?.data?.error?.message || 'Failed to load dashboard analytics.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="animate-fade-in">
        <PageHeader title="Admin Dashboard" subtitle="Platform-wide overview across every customer." />
        <SkeletonStatGrid count={4} />
        <div className="mt-6">
          <Skeleton className="h-80 w-full" />
        </div>
      </div>
    );
  }

  if (error) return <ErrorState message={error} onRetry={load} />;

  const revenueCurrency = summary.revenue_by_currency[0]?.currency || 'USD';
  const refundCurrency = refunds?.refunded_amount_by_currency[0]?.currency || 'USD';
  const activePlanDistribution = subscribersByPlan.filter((p) => p.subscriber_count > 0);

  return (
    <div className="animate-fade-in">
      <PageHeader title="Admin Dashboard" subtitle="Platform-wide overview across every customer." />

      {/* Compact KPI summary -- 4 metrics only. Every other figure
          previously shown here (trial/cancelled customers, ARR, total
          plans, cancelled subscriptions, payment/refund counts) is
          still fully available elsewhere (AdminAnalyticsPage,
          AdminCustomersPage, AdminPlansPage, AdminSubscriptionsPage,
          AdminRefundsPage) -- nothing was removed from the platform,
          only decluttered from this specific page. */}
      <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          icon={FiUsers}
          label="Customers"
          value={summary.total_customers}
          tone="brand"
          visual={
            customerTrend.length > 0 ? (
              <div>
                <MiniSparkline
                  values={customerTrend.map((m) => m.new_customers)}
                  colorClass="stroke-[#E50914] text-[#E50914]"
                />
                {customerTrend.length === 1 && (
                  <p className="mt-0.5 text-[10px] text-slate-600">Only 1 month of data so far</p>
                )}
              </div>
            ) : null
          }
        />
        <StatCard
          icon={FiDollarSign}
          label="Revenue"
          value={formatCurrencyBreakdown(summary.revenue_by_currency)}
          tone="success"
          visual={
            revenue?.revenue_by_month?.length > 0 ? (
              <div>
                <MiniSparkline
                  values={revenue.revenue_by_month.map((m) => Number(m.revenue))}
                  colorClass="stroke-emerald-400 text-emerald-400"
                />
                {revenue.revenue_by_month.length === 1 && (
                  <p className="mt-0.5 text-[10px] text-slate-600">Only 1 month of data so far</p>
                )}
              </div>
            ) : null
          }
        />
        <StatCard
          icon={FiFilm}
          label="Active Subscriptions"
          value={summary.active_subscriptions}
          tone="info"
          visual={
            subscriptions && subscriptions.total_subscriptions > 0 ? (
              <div className="flex items-center gap-3">
                <MiniRing
                  value={subscriptions.active_subscriptions}
                  total={subscriptions.total_subscriptions}
                  colorClass="stroke-sky-400"
                  size={56}
                  thickness={6}
                />
                <div className="text-xs text-slate-500">
                  <p className="font-semibold text-white">
                    {Math.round((subscriptions.active_subscriptions / subscriptions.total_subscriptions) * 100)}%
                  </p>
                  <p>of {subscriptions.total_subscriptions} total</p>
                </div>
              </div>
            ) : null
          }
        />
        <StatCard
          icon={FiTrendingUp}
          label="MRR"
          value={formatCurrencyBreakdown(summary.mrr_by_currency)}
          sublabel={`ARR: ${formatCurrencyBreakdown(summary.arr_by_currency)}`}
          tone="violet"
          visual={
            mrrByPlan.length > 0 ? (
              <div className="space-y-1">
                {mrrByPlan.slice(0, 3).map((p) => {
                  const maxMrr = Math.max(...mrrByPlan.map((x) => Number(x.mrr)), 1);
                  return (
                    <div key={p.plan_id} className="flex items-center gap-2">
                      <span className="w-16 shrink-0 truncate text-[10px] text-slate-500">{p.plan_name}</span>
                      <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                        <div
                          className="h-full rounded-full bg-violet-400"
                          style={{ width: `${Math.max((Number(p.mrr) / maxMrr) * 100, 4).toFixed(0)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : null
          }
        />
      </div>
      {/* MRR's visual is a current-state composition by plan (GET
          /analytics/mrr-by-plan), not a historical trend -- see the
          module docstring above for why a historical MRR chart would
          require fabricating precision this schema doesn't support. */}

      {/* Main visual analytics -- the single large hero chart. */}
      <SectionCard icon={FiTrendingUp} label="Revenue Trend — Last 12 Months" accent="brand" className="mb-6">
        {revenue?.revenue_by_month?.length > 0 ? (
          <TrendChart
            height={280}
            ariaLabel="Monthly platform revenue trend, last 12 months"
            formatValue={(v) => formatCurrency(v, revenueCurrency)}
            xLabels={revenue.revenue_by_month.map((m) =>
              new Date(m.month).toLocaleDateString(undefined, { month: 'short' })
            )}
            series={[
              {
                label: 'Revenue',
                colorClass: 'stroke-[#E50914] text-[#E50914]',
                dotClass: 'bg-[#E50914]',
                values: revenue.revenue_by_month.map((m) => Number(m.revenue)),
              },
            ]}
          />
        ) : (
          <EmptyState icon={FiTrendingUp} title="No revenue recorded yet" />
        )}
      </SectionCard>

      {/* Row: Subscription Distribution | Payment Success vs Failed */}
      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard icon={FiPieChart} label="Subscription Distribution" accent="violet">
          {subscriptions && subscriptions.total_subscriptions > 0 ? (
            <DonutChart
              centerValue={subscriptions.total_subscriptions}
              centerLabel="Total"
              segments={[
                { label: 'Active', value: subscriptions.active_subscriptions, colorClass: 'stroke-emerald-400', dotClass: 'bg-emerald-400' },
                { label: 'Trial', value: subscriptions.trial_subscriptions, colorClass: 'stroke-amber-400', dotClass: 'bg-amber-400' },
                { label: 'Paused', value: subscriptions.paused_subscriptions, colorClass: 'stroke-sky-400', dotClass: 'bg-sky-400' },
                { label: 'Past Due', value: subscriptions.past_due_subscriptions, colorClass: 'stroke-orange-400', dotClass: 'bg-orange-400' },
                { label: 'Cancelled', value: subscriptions.cancelled_subscriptions, colorClass: 'stroke-red-400', dotClass: 'bg-red-400' },
              ]}
            />
          ) : (
            <EmptyState icon={FiPieChart} title="No subscriptions yet" />
          )}
        </SectionCard>

        <SectionCard icon={FiCreditCard} label="Payment Success vs Failed" accent="success">
          {payments && payments.total_payments > 0 ? (
            <DonutChart
              centerValue={payments.total_payments}
              centerLabel="Attempts"
              segments={[
                { label: 'Succeeded', value: payments.successful_payments, colorClass: 'stroke-emerald-400', dotClass: 'bg-emerald-400' },
                { label: 'Failed', value: payments.failed_payments, colorClass: 'stroke-red-400', dotClass: 'bg-red-400' },
                { label: 'Pending', value: payments.pending_payments, colorClass: 'stroke-amber-400', dotClass: 'bg-amber-400' },
              ]}
            />
          ) : (
            <EmptyState icon={FiCreditCard} title="No payment attempts yet" />
          )}
        </SectionCard>
      </div>

      {/* Row: Revenue by Month | Plan Distribution */}
      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard icon={FiBarChart2} label="Revenue by Month" accent="brand">
          {revenue?.revenue_by_month?.length > 0 ? (
            <BarChart
              colorClass="bg-[#E50914]"
              items={revenue.revenue_by_month.slice(-6).map((m) => ({
                label: new Date(m.month).toLocaleDateString(undefined, { month: 'short' }),
                value: Number(m.revenue),
                formatted: formatCurrency(m.revenue, revenueCurrency),
              }))}
            />
          ) : (
            <EmptyState icon={FiBarChart2} title="No revenue recorded yet" />
          )}
        </SectionCard>

        <SectionCard
          icon={FiTag}
          label="Plan Distribution"
          accent="info"
          action={
            <Link to="/admin/plans" className="focus-ring rounded text-sm text-slate-400 hover:text-white">
              View plans
            </Link>
          }
        >
          {/* Real, exact database count -- GET /analytics/subscribers-by-plan.
              No sampling, no cap: every active subscription on the
              platform is counted by the database itself. */}
          {activePlanDistribution.length > 0 ? (
            <BarChart
              colorClass="bg-sky-400"
              items={activePlanDistribution
                .sort((a, b) => b.subscriber_count - a.subscriber_count)
                .map((p) => ({
                  label: p.plan_name,
                  value: p.subscriber_count,
                  formatted: String(p.subscriber_count),
                }))}
            />
          ) : (
            <EmptyState icon={FiTag} title="No active subscriptions yet" />
          )}
        </SectionCard>
      </div>

      {/* Row: Refund Trend | Subscription Growth (the honest
          "customer analytics" substitute -- see module docstring). */}
      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard
          icon={FiRotateCcw}
          label="Refund Trend — Amount by Month"
          accent="amber"
          action={
            <Link to="/admin/refunds" className="focus-ring rounded text-sm text-slate-400 hover:text-white">
              View all
            </Link>
          }
        >
          {/* Real, database-computed trend -- GET /analytics/refunds/trend.
              Only completed refunds; a month with no completed refunds
              simply doesn't appear (never interpolated as zero). Status
              breakdown (completed/pending/failed) is still available in
              full on the Refunds page -- shown here only as a one-line
              summary rather than a second, redundant chart. */}
          {refundTrend.length > 0 ? (
            <>
              <TrendChart
                ariaLabel="Monthly refunded amount trend"
                formatValue={(v) => formatCurrency(v, refundCurrency)}
                xLabels={refundTrend.map((m) =>
                  new Date(m.month).toLocaleDateString(undefined, { month: 'short' })
                )}
                series={[
                  {
                    label: 'Refunded',
                    colorClass: 'stroke-amber-400 text-amber-400',
                    dotClass: 'bg-amber-400',
                    values: refundTrend.map((m) => Number(m.refund_amount)),
                  },
                ]}
              />
              {refunds && (
                <p className="mt-3 text-xs text-slate-500">
                  {refunds.completed_refunds} completed, {refunds.pending_refunds} pending,{' '}
                  {refunds.failed_refunds} failed overall.
                </p>
              )}
            </>
          ) : (
            <EmptyState icon={FiRotateCcw} title="No completed refunds yet" />
          )}
        </SectionCard>

        <SectionCard icon={FiRepeat} label="Subscription Growth (last 12 months)" accent="violet">
          {kpis?.monthly_subscription_growth?.length > 0 ? (
            <TrendChart
              ariaLabel="Monthly subscription growth trend"
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
            <EmptyState icon={FiRepeat} title="No subscription growth data yet" />
          )}
        </SectionCard>
      </div>

      {/* Row: Recent Customers | Recent Activity */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard
          icon={FiUsers}
          label="Recent Customers"
          accent="slate"
          action={
            <Link to="/admin/customers" className="focus-ring rounded text-sm text-slate-400 hover:text-white">
              View all
            </Link>
          }
        >
          {recentCustomers.length === 0 ? (
            <EmptyState icon={FiUsers} title="No customers yet" />
          ) : (
            <ul className="divide-y divide-white/5">
              {recentCustomers.map((c) => (
                <li key={c.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                  <div className="min-w-0">
                    <Link
                      to={`/admin/customers/${c.id}`}
                      className="focus-ring truncate font-medium text-slate-200 hover:text-white"
                    >
                      {c.name}
                    </Link>
                    <p className="truncate text-xs text-slate-500">{c.email}</p>
                  </div>
                  <span className="flex-shrink-0 text-xs text-slate-500">{formatDate(c.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard
          icon={FiActivity}
          label="Recent Activity"
          accent="slate"
          action={
            <Link to="/admin/audit-log" className="focus-ring rounded text-sm text-slate-400 hover:text-white">
              View all
            </Link>
          }
        >
          <RecentActivity events={recentAudit} limit={6} />
        </SectionCard>
      </div>
    </div>
  );
}
