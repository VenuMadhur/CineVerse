import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { FiFilm, FiPause, FiPlay, FiXCircle, FiRotateCcw } from 'react-icons/fi';
import PageHeader from '../../components/common/PageHeader';
import FilterChips from '../../components/common/FilterChips';
import Table, { TableRow, TableCell } from '../../components/common/Table';
import { SkeletonTableRows } from '../../components/common/Skeleton';
import Pagination from '../../components/common/Pagination';
import { EmptyState, ErrorState } from '../../components/common/EmptyState';
import StatusBadge from '../../components/common/StatusBadge';
import ConfirmDialog from '../../components/common/ConfirmDialog';
import { subscriptionService } from '../../services/subscriptionService';
import { planService } from '../../services/planService';
import { formatDate, extractErrorMessage } from '../../utils/formatters';
import { SUBSCRIPTION_STATUS_LABELS } from '../../utils/constants';

const PAGE_SIZE = 10;
const COLUMNS = [
  'ID',
  'Customer',
  'Plan',
  'Status',
  'Trial Ends',
  'Activated',
  'Created',
  'Actions',
];
const STATUS_OPTIONS = ['', 'trial', 'active', 'paused', 'past_due', 'cancelled'];

/**
 * Admin view of every subscription on the platform with lifecycle
 * actions. Reuses subscriptionService.pause/resume/cancel/undoCancellation
 * -- the exact same POST endpoints the customer-facing SubscriptionsPage
 * already uses. No new backend endpoints were created.
 *
 * Plan names: the backend's SubscriptionResponse only includes
 * plan_id, not a name. Rather than an N+1 lookup (one request per
 * row) or truncating every plan_id to an opaque hash, this page
 * fetches the full plan list *once* per page load (plans are a small,
 * bounded set -- unlike customers/subscriptions, which can be
 * arbitrarily large) and resolves names from an in-memory map. Falls
 * back to a truncated, still-accurate ID if a plan somehow isn't in
 * that map (e.g. more than 100 plans exist).
 *
 * customer_id remains an ID, but is now a real link into the existing
 * AdminCustomerDetailPage instead of inert text -- reuses routing
 * that already exists rather than fetching customer names too (which
 * *would* risk N+1/scale issues, since the customer set is unbounded).
 */
export default function AdminSubscriptionsPage() {
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ items: [], total: 0 });
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirm, setConfirm] = useState(null); // { sub, action, label, message }
  const [actionLoading, setActionLoading] = useState(false);

  const planNameById = useMemo(() => {
    const map = new Map();
    for (const plan of plans) map.set(plan.id, plan.name);
    return map;
  }, [plans]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [subsResult, plansResult] = await Promise.all([
        subscriptionService.list({
          status: status || undefined,
          page,
          pageSize: PAGE_SIZE,
        }),
        // Only fetched once per page load, not once per row -- a flat
        // list of plans is cheap and small, so this is one extra
        // request total, not N.
        planService.list({ pageSize: 100 }),
      ]);
      setResult(subsResult);
      setPlans(plansResult.items);
    } catch (err) {
      setError(err?.response?.data?.error?.message || 'Failed to load subscriptions.');
    } finally {
      setLoading(false);
    }
  }, [status, page]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAction = async () => {
    if (!confirm) return;
    const { sub, action } = confirm;
    setActionLoading(true);
    try {
      if (action === 'pause') {
        await subscriptionService.pause(sub.id);
        toast.success('Subscription paused.');
      } else if (action === 'resume') {
        await subscriptionService.resume(sub.id);
        toast.success('Subscription resumed.');
      } else if (action === 'cancel') {
        await subscriptionService.cancel(sub.id, { cancellationType: 'immediate' });
        toast.success('Subscription cancelled immediately.');
      } else if (action === 'cancel_eoc') {
        await subscriptionService.cancel(sub.id, { cancellationType: 'end_of_cycle' });
        toast.success('Subscription scheduled for cancellation at period end.');
      } else if (action === 'undo') {
        await subscriptionService.undoCancellation(sub.id);
        toast.success('Scheduled cancellation reversed.');
      }
      setConfirm(null);
      load();
    } catch (err) {
      toast.error(extractErrorMessage(err) || 'Action failed.');
    } finally {
      setActionLoading(false);
    }
  };

  const requestConfirm = (sub, action, label, message) => {
    setConfirm({ sub, action, label, message });
  };

  return (
    <div className="animate-fade-in">
      <PageHeader title="Subscriptions" subtitle="Every subscription on the platform." />

      <FilterChips
        options={STATUS_OPTIONS}
        value={status}
        onChange={(s) => {
          setStatus(s);
          setPage(1);
        }}
        formatLabel={(s) => (s ? (SUBSCRIPTION_STATUS_LABELS[s] || s) : 'All')}
      />

      {loading && (
        <Table columns={COLUMNS}>
          <SkeletonTableRows rows={PAGE_SIZE} columns={COLUMNS.length} />
        </Table>
      )}
      {error && !loading && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && result.items.length === 0 && (
        <EmptyState icon={FiFilm} title="No subscriptions found" />
      )}

      {!loading && !error && result.items.length > 0 && (
        <>
          <Table columns={COLUMNS}>
            {result.items.map((sub) => (
              <TableRow key={sub.id}>
                <TableCell
                  className="font-mono text-xs text-slate-400"
                  title={sub.id}
                >
                  {sub.id.slice(0, 8)}
                </TableCell>
                <TableCell>
                  <Link
                    to={`/admin/customers/${sub.customer_id}`}
                    className="focus-ring rounded font-mono text-xs text-slate-300 underline decoration-white/20 underline-offset-2 hover:text-white hover:decoration-white/50"
                    title={sub.customer_id}
                  >
                    {sub.customer_id.slice(0, 8)}
                  </Link>
                </TableCell>
                <TableCell className="text-slate-200" title={sub.plan_id}>
                  {planNameById.get(sub.plan_id) || sub.plan_id.slice(0, 8)}
                </TableCell>
                <TableCell>
                  <StatusBadge status={sub.status} />
                  {sub.cancel_at_period_end && (
                    <span className="ml-2 rounded-full border border-orange-500/30 bg-orange-500/10 px-2 py-0.5 text-xs text-orange-400">
                      Cancels at period end
                    </span>
                  )}
                </TableCell>
                <TableCell>{formatDate(sub.trial_ends_at)}</TableCell>
                <TableCell>{formatDate(sub.activated_at)}</TableCell>
                <TableCell>{formatDate(sub.created_at)}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    {sub.status === 'active' && (
                      <button
                        className="focus-ring btn-ghost !p-1.5 text-amber-400 hover:text-amber-300"
                        title="Pause"
                        aria-label={`Pause subscription ${sub.id.slice(0, 8)}`}
                        onClick={() =>
                          requestConfirm(
                            sub,
                            'pause',
                            'Pause Subscription',
                            'This will pause the subscription immediately. The customer will not be billed until resumed.'
                          )
                        }
                      >
                        <FiPause size={15} />
                      </button>
                    )}
                    {sub.status === 'paused' && (
                      <button
                        className="focus-ring btn-ghost !p-1.5 text-emerald-400 hover:text-emerald-300"
                        title="Resume"
                        aria-label={`Resume subscription ${sub.id.slice(0, 8)}`}
                        onClick={() =>
                          requestConfirm(
                            sub,
                            'resume',
                            'Resume Subscription',
                            'This will reactivate the subscription.'
                          )
                        }
                      >
                        <FiPlay size={15} />
                      </button>
                    )}
                    {sub.cancel_at_period_end && (
                      <button
                        className="focus-ring btn-ghost !p-1.5 text-sky-400 hover:text-sky-300"
                        title="Undo scheduled cancellation"
                        aria-label={`Undo scheduled cancellation for subscription ${sub.id.slice(0, 8)}`}
                        onClick={() =>
                          requestConfirm(
                            sub,
                            'undo',
                            'Undo Cancellation',
                            'This will cancel the scheduled end-of-cycle cancellation. The subscription will continue as normal.'
                          )
                        }
                      >
                        <FiRotateCcw size={15} />
                      </button>
                    )}
                    {sub.status !== 'cancelled' && (
                      <button
                        className="focus-ring btn-ghost !p-1.5 text-red-400 hover:text-red-300"
                        title="Cancel immediately"
                        aria-label={`Cancel subscription ${sub.id.slice(0, 8)} immediately`}
                        onClick={() =>
                          requestConfirm(
                            sub,
                            'cancel',
                            'Cancel Immediately',
                            'This will cancel the subscription right now. Any unused billing period will be refunded automatically.'
                          )
                        }
                      >
                        <FiXCircle size={15} />
                      </button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </Table>
          <Pagination page={page} pageSize={PAGE_SIZE} total={result.total} onPageChange={setPage} />
        </>
      )}

      <ConfirmDialog
        open={Boolean(confirm)}
        onClose={() => !actionLoading && setConfirm(null)}
        onConfirm={handleAction}
        title={confirm?.label || 'Confirm Action'}
        message={confirm?.message}
        confirmLabel={confirm?.label || 'Confirm'}
        loading={actionLoading}
        variant={confirm?.action === 'resume' || confirm?.action === 'undo' ? 'primary' : 'danger'}
      />
    </div>
  );
}
