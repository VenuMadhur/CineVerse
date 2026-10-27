import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FiFilm,
  FiActivity,
  FiCalendar,
  FiFileText,
  FiCreditCard,
  FiRotateCcw,
  FiArrowRight,
  FiTrendingUp,
  FiCompass,
} from 'react-icons/fi';
import PageHeader from '../components/common/PageHeader';
import SectionCard from '../components/common/SectionCard';
import StatCard from '../components/dashboard/StatCard';
import RecentActivity from '../components/dashboard/RecentActivity';
import TrendChart from '../components/common/TrendChart';
import DonutChart from '../components/common/DonutChart';
import ContentCard from '../components/catalog/ContentCard';
import { SkeletonStatGrid, Skeleton } from '../components/common/Skeleton';
import { EmptyState, ErrorState } from '../components/common/EmptyState';
import StatusBadge from '../components/common/StatusBadge';
import { useCustomer } from '../hooks/useCustomer';
import { subscriptionService } from '../services/subscriptionService';
import { MOVIES, SERIES } from '../data/catalogData';
import { planService } from '../services/planService';
import { invoiceService } from '../services/invoiceService';
import { paymentService } from '../services/paymentService';
import { refundService } from '../services/refundService';
import { auditLogService } from '../services/auditLogService';
import { formatCurrency, formatDate, formatDateTime, extractErrorMessage } from '../utils/formatters';

const RECENT_LIMIT = 5;

// A small, deterministic mix for the "Continue Exploring" showcase --
// same static catalog data as /movies and /series, just a subset.
const EXPLORE_ITEMS = [...MOVIES.slice(0, 3), ...SERIES.slice(0, 2)];

export default function DashboardPage() {
  const { customer } = useCustomer();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [subscription, setSubscription] = useState(null);
  const [plan, setPlan] = useState(null);
  const [renewalDate, setRenewalDate] = useState(null);
  const [invoiceCount, setInvoiceCount] = useState(0);
  const [paidInvoiceCount, setPaidInvoiceCount] = useState(0);
  const [refundCount, setRefundCount] = useState(0);
  const [activity, setActivity] = useState([]);
  const [recentInvoices, setRecentInvoices] = useState([]);
  const [invoiceHistory, setInvoiceHistory] = useState([]);
  const [recentPayments, setRecentPayments] = useState([]);
  const [paymentBreakdown, setPaymentBreakdown] = useState(null);
  const [recentRefunds, setRecentRefunds] = useState([]);

  const load = useCallback(async () => {
    if (!customer) return;
    setLoading(true);
    setError(null);
    try {
      const subsResult = await subscriptionService.list({ customerId: customer.id, pageSize: 5 });
      const latestSub = subsResult.items.find((s) => s.status !== 'cancelled') || null;

      const [invoicesResult, paidInvoicesResult, refundsResult, invoiceHistoryResult, paymentsForBreakdown] =
        await Promise.all([
          invoiceService.list({ customerId: customer.id, pageSize: 1 }),
          invoiceService.list({ customerId: customer.id, status: 'paid', pageSize: 1 }),
          refundService.list({ customerId: customer.id, pageSize: RECENT_LIMIT }),
          // Fetched once at a larger page size: the same real invoices
          // power both the "Recent Invoices" list (sliced to 5 below)
          // and the monthly chart (aggregated from the full set) --
          // one API call, not two.
          invoiceService.list({ customerId: customer.id, pageSize: 24 }),
          // For the "My Payment History" donut -- a broader sample of
          // this customer's own payment attempts (succeeded/failed/
          // pending), reusing the exact same paymentService.list call
          // already used on PaymentsPage, just scoped and paged
          // differently for an aggregate view instead of a list.
          paymentService.list({ customerId: customer.id, pageSize: 100 }),
        ]);

      setInvoiceCount(invoicesResult.total);
      setPaidInvoiceCount(paidInvoicesResult.total);
      setRefundCount(refundsResult.total);
      setRecentInvoices(invoiceHistoryResult.items.slice(0, RECENT_LIMIT));
      setPaymentBreakdown({
        succeeded: paymentsForBreakdown.items.filter((p) => p.status === 'succeeded').length,
        failed: paymentsForBreakdown.items.filter((p) => p.status === 'failed').length,
        pending: paymentsForBreakdown.items.filter((p) => p.status === 'pending').length,
      });
      setInvoiceHistory(invoiceHistoryResult.items);
      setRecentRefunds(refundsResult.items);

      // "Recent Payments" isn't a standalone backend endpoint (payments
      // only exist attached to an invoice), so we pull payment history
      // for the same recent invoices and merge -- same approach as the
      // dedicated Payments page.
      const paymentsPerInvoice = await Promise.all(
        invoiceHistoryResult.items.slice(0, RECENT_LIMIT).map((inv) =>
          invoiceService.listPayments(inv.id).then((payments) =>
            payments.map((p) => ({ ...p, invoiceNumber: inv.invoice_number }))
          )
        )
      );
      setRecentPayments(
        paymentsPerInvoice
          .flat()
          .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
          .slice(0, RECENT_LIMIT)
      );

      if (latestSub) {
        setSubscription(latestSub);
        const [planData, cycles, events] = await Promise.all([
          planService.get(latestSub.plan_id),
          subscriptionService.listBillingCycles(latestSub.id),
          auditLogService.listForEntity('subscription', latestSub.id),
        ]);
        setPlan(planData);
        const unbilled = cycles.find((c) => !c.is_billed);
        setRenewalDate(unbilled?.next_billing_date || cycles[0]?.next_billing_date || null);
        setActivity(events);
      } else {
        setSubscription(null);
        setPlan(null);
        setRenewalDate(null);
        setActivity([]);
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [customer]);

  useEffect(() => {
    load();
  }, [load]);

  // Real invoice history aggregated into a monthly chart -- built from
  // the exact same invoices already fetched for the "Recent Invoices"
  // list above, not a separate/fabricated source. Currency-aware: a
  // customer's invoices are very likely all one currency, but plan
  // currency is unconstrained (see the backend's multi-currency work),
  // so if genuinely mixed currencies exist in the history, each gets
  // its own series rather than being blended into one misleading sum.
  const invoiceChartData = useMemo(() => {
    if (invoiceHistory.length === 0) return null;

    const byCurrency = new Map(); // currency -> Map(monthKey -> total)
    const monthKeys = [];
    for (const inv of invoiceHistory) {
      const d = new Date(inv.created_at);
      const monthKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      if (!monthKeys.includes(monthKey)) monthKeys.push(monthKey);
      const currency = inv.currency || 'USD';
      if (!byCurrency.has(currency)) byCurrency.set(currency, new Map());
      const monthTotals = byCurrency.get(currency);
      monthTotals.set(monthKey, (monthTotals.get(monthKey) || 0) + Number(inv.total_amount));
    }
    monthKeys.sort();
    const xLabels = monthKeys.map((k) => {
      const [y, m] = k.split('-');
      return new Date(Number(y), Number(m) - 1, 1).toLocaleDateString(undefined, { month: 'short' });
    });
    const palette = [
      { colorClass: 'stroke-[#E50914] text-[#E50914]', dotClass: 'bg-[#E50914]' },
      { colorClass: 'stroke-sky-400 text-sky-400', dotClass: 'bg-sky-400' },
      { colorClass: 'stroke-amber-400 text-amber-400', dotClass: 'bg-amber-400' },
    ];
    const series = Array.from(byCurrency.entries()).map(([currency, monthTotals], i) => ({
      label: currency,
      ...palette[i % palette.length],
      values: monthKeys.map((k) => monthTotals.get(k) || 0),
    }));
    return { series, xLabels };
  }, [invoiceHistory]);

  if (loading) {
    return (
      <div>
        <PageHeader title="Welcome back" subtitle="Here's what's happening with your CineVerse account." />
        <div className="mb-8">
          <SkeletonStatGrid count={6} />
        </div>
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (error) {
    return <ErrorState message={error} onRetry={load} />;
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title={`Welcome back${customer?.name ? `, ${customer.name.split(' ')[0]}` : ''}`}
        subtitle="Here's what's happening with your CineVerse account."
      />

      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          icon={FiFilm}
          label="Current Plan"
          value={plan?.name || 'No active plan'}
          sublabel={plan ? `${plan.billing_interval} billing` : 'Subscribe to get started'}
          tone="brand"
        />
        <StatCard
          icon={FiActivity}
          label="Subscription Status"
          value={subscription ? <StatusBadge status={subscription.status} /> : '—'}
          tone="success"
        />
        <StatCard
          icon={FiCalendar}
          label="Renewal Date"
          value={renewalDate ? formatDate(renewalDate) : '—'}
          tone="info"
        />
        <StatCard icon={FiFileText} label="Invoices" value={invoiceCount} sublabel="Total issued" />
        <StatCard
          icon={FiCreditCard}
          label="Payments"
          value={paidInvoiceCount}
          sublabel="Invoices paid"
          tone="success"
        />
        <StatCard icon={FiRotateCcw} label="Refunds" value={refundCount} sublabel="Total issued" tone="warning" />
      </div>

      {!subscription && (
        <div className="metric-card glass-card relative mb-8 overflow-hidden border-[#E50914]/25 bg-gradient-to-br from-[#E50914]/10 via-transparent to-transparent">
          <div className="relative flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div>
              <p className="text-lg font-bold text-white">You don&apos;t have an active subscription yet.</p>
              <p className="mt-1 text-sm text-slate-400">Browse plans and start streaming today.</p>
            </div>
            <Link to="/plans" className="btn-primary whitespace-nowrap">
              View Plans <FiArrowRight />
            </Link>
          </div>
        </div>
      )}

      <SectionCard
        icon={FiCompass}
        label="Continue Exploring"
        accent="info"
        className="mb-6"
        action={
          <Link to="/movies" className="focus-ring rounded text-sm text-slate-400 hover:text-white">
            Browse all
          </Link>
        }
      >
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {EXPLORE_ITEMS.map((item, i) => (
            <ContentCard key={item.id} item={item} index={i} />
          ))}
        </div>
      </SectionCard>

      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard icon={FiTrendingUp} label="My Spending Trend" accent="brand">
          {invoiceChartData ? (
            <TrendChart
              series={invoiceChartData.series}
              xLabels={invoiceChartData.xLabels}
              ariaLabel="Monthly invoice amount history"
            />
          ) : (
            <EmptyState icon={FiFileText} title="No invoice history yet" />
          )}
        </SectionCard>

        <SectionCard icon={FiCreditCard} label="My Payment History" accent="success">
          {paymentBreakdown &&
          paymentBreakdown.succeeded + paymentBreakdown.failed + paymentBreakdown.pending > 0 ? (
            <DonutChart
              centerValue={paymentBreakdown.succeeded + paymentBreakdown.failed + paymentBreakdown.pending}
              centerLabel="Attempts"
              segments={[
                { label: 'Succeeded', value: paymentBreakdown.succeeded, colorClass: 'stroke-emerald-400', dotClass: 'bg-emerald-400' },
                { label: 'Failed', value: paymentBreakdown.failed, colorClass: 'stroke-red-400', dotClass: 'bg-red-400' },
                { label: 'Pending', value: paymentBreakdown.pending, colorClass: 'stroke-amber-400', dotClass: 'bg-amber-400' },
              ]}
            />
          ) : (
            <EmptyState icon={FiCreditCard} title="No payments yet" />
          )}
        </SectionCard>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard
          icon={FiFileText}
          label="Recent Invoices"
          accent="brand"
          action={
            <Link to="/invoices" className="focus-ring rounded text-sm text-slate-400 hover:text-white">
              View all
            </Link>
          }
        >
          {recentInvoices.length === 0 ? (
            <EmptyState icon={FiFileText} title="No invoices yet" />
          ) : (
            <ul className="-mx-2 divide-y divide-white/5">
              {recentInvoices.map((invoice) => (
                <li
                  key={invoice.id}
                  className="flex items-center justify-between gap-3 rounded-lg px-2 py-3 text-sm transition-colors hover:bg-white/[0.03]"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium text-slate-200">{invoice.invoice_number}</p>
                    <p className="text-xs text-slate-500">{formatDate(invoice.created_at)}</p>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-2">
                    <span className="text-slate-300">
                      {formatCurrency(invoice.total_amount, invoice.currency)}
                    </span>
                    <StatusBadge status={invoice.status} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard
          icon={FiCreditCard}
          label="Recent Payments"
          accent="success"
          action={
            <Link to="/payments" className="focus-ring rounded text-sm text-slate-400 hover:text-white">
              View all
            </Link>
          }
        >
          {recentPayments.length === 0 ? (
            <EmptyState icon={FiCreditCard} title="No payments yet" />
          ) : (
            <ul className="-mx-2 divide-y divide-white/5">
              {recentPayments.map((payment) => (
                <li
                  key={payment.id}
                  className="flex items-center justify-between gap-3 rounded-lg px-2 py-3 text-sm transition-colors hover:bg-white/[0.03]"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium text-slate-200">{payment.invoiceNumber}</p>
                    <p className="text-xs text-slate-500">
                      {formatDateTime(payment.processed_at || payment.created_at)}
                    </p>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-2">
                    <span className="text-slate-300">
                      {formatCurrency(payment.amount, payment.currency)}
                    </span>
                    <StatusBadge status={payment.status} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard
          icon={FiRotateCcw}
          label="Recent Refunds"
          accent="amber"
          action={
            <Link to="/refunds" className="focus-ring rounded text-sm text-slate-400 hover:text-white">
              View all
            </Link>
          }
        >
          {recentRefunds.length === 0 ? (
            <EmptyState icon={FiRotateCcw} title="No refunds yet" />
          ) : (
            <ul className="-mx-2 divide-y divide-white/5">
              {recentRefunds.map((refund) => (
                <li
                  key={refund.id}
                  className="flex items-center justify-between gap-3 rounded-lg px-2 py-3 text-sm transition-colors hover:bg-white/[0.03]"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium text-slate-200">{refund.reason}</p>
                    <p className="text-xs text-slate-500">{formatDate(refund.created_at)}</p>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-2">
                    <span className="text-slate-300">
                      {formatCurrency(refund.amount, refund.currency)}
                    </span>
                    <StatusBadge status={refund.status} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard
          icon={FiActivity}
          label="Recent Activity"
          accent="info"
          action={
            <Link to="/activity" className="focus-ring rounded text-sm font-medium text-[#E50914] hover:underline">
              View All
            </Link>
          }
        >
          <RecentActivity events={activity} />
        </SectionCard>
      </div>
    </div>
  );
}
