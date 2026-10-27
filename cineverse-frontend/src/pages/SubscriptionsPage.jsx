import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { FiArrowRight, FiFilm, FiPause, FiPlay, FiPower, FiRepeat, FiRotateCcw, FiXCircle } from 'react-icons/fi';
import PageHeader from '../components/common/PageHeader';
import CancelSubscriptionModal from '../components/subscription/CancelSubscriptionModal';
import { SkeletonCard } from '../components/common/Skeleton';
import { EmptyState, ErrorState } from '../components/common/EmptyState';
import StatusBadge from '../components/common/StatusBadge';
import { useCustomer } from '../hooks/useCustomer';
import { planService } from '../services/planService';
import { subscriptionService } from '../services/subscriptionService';
import { extractErrorMessage, formatDate } from '../utils/formatters';

/**
 * Manages the customer's existing subscription: trial/active/paused/
 * past_due status, activation, pause/resume, and cancellation.
 * Browsing plans and upgrading/downgrading lives on the separate
 * Plans page (see src/pages/PlansPage.jsx).
 */
export default function SubscriptionsPage() {
  const { customer } = useCustomer();
  const [subscription, setSubscription] = useState(null);
  const [plan, setPlan] = useState(null);
  const [billingCycle, setBillingCycle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [cancelModalOpen, setCancelModalOpen] = useState(false);

  const loadData = useCallback(async () => {
    if (!customer) return;
    setLoading(true);
    setError(null);
    try {
      const subsResult = await subscriptionService.list({ customerId: customer.id, pageSize: 5 });
      const active = subsResult.items.find((s) => s.status !== 'cancelled');
      const current = active || subsResult.items[0] || null;
      setSubscription(current);

      if (current) {
        const [planData, cycles] = await Promise.all([
          planService.get(current.plan_id),
          subscriptionService.listBillingCycles(current.id),
        ]);
        setPlan(planData);
        const unbilled = cycles.find((c) => !c.is_billed);
        setBillingCycle(unbilled || cycles[0] || null);
      } else {
        setPlan(null);
        setBillingCycle(null);
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [customer]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const runAction = async (action, successMessage) => {
    setActionLoading(true);
    try {
      await action();
      toast.success(successMessage);
      await loadData();
    } catch (err) {
      toast.error(extractErrorMessage(err));
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div>
        <PageHeader title="Your Subscription" subtitle="Manage your CineVerse subscription." />
        <SkeletonCard />
      </div>
    );
  }

  if (error) return <ErrorState message={error} onRetry={loadData} />;

  if (!subscription) {
    return (
      <div>
        <PageHeader title="Your Subscription" subtitle="Manage your CineVerse subscription." />
        <EmptyState
          icon={FiFilm}
          title="No subscription yet"
          description="Browse our plans and start streaming today."
        />
        <div className="mt-6 flex justify-center">
          <Link to="/plans" className="btn-primary">
            View Plans <FiArrowRight />
          </Link>
        </div>
      </div>
    );
  }

  const statusMessage = {
    trial: `Your free trial ends ${formatDate(subscription.trial_ends_at)}.`,
    active: 'Your subscription is active and will renew automatically.',
    paused: 'Your subscription is currently paused. Resume anytime to keep watching.',
    past_due: 'Your last payment failed. Please check your Invoices to resolve this.',
  }[subscription.status];

  return (
    <div>
      <PageHeader
        title="Your Subscription"
        subtitle="Manage your CineVerse subscription."
        actions={
          <Link to="/plans" className="btn-secondary">
            <FiRepeat /> Change Plan
          </Link>
        }
      />

      <div className="glass-card p-6">
        <div className="mb-2 flex flex-wrap items-center gap-3">
          <h2 className="text-xl font-bold text-white">{plan?.name || 'Subscription'}</h2>
          <StatusBadge status={subscription.status} />
          {subscription.cancel_at_period_end && (
            <span className="inline-flex items-center rounded-full border border-amber-500/30 bg-amber-500/15 px-2.5 py-1 text-xs font-semibold text-amber-400">
              Cancels at period end
            </span>
          )}
        </div>
        <p className="mb-6 text-sm text-slate-400">{statusMessage}</p>

        <div className="mb-6 grid grid-cols-2 gap-4 rounded-lg border border-white/10 bg-white/[0.03] p-4 text-sm sm:grid-cols-4">
          <div>
            <p className="text-xs text-slate-500">Status</p>
            <p className="font-medium text-white capitalize">{subscription.status.replace('_', ' ')}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Trial Ends</p>
            <p className="font-medium text-white">{formatDate(subscription.trial_ends_at)}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Renewal Date</p>
            <p className="font-medium text-white">
              {billingCycle ? formatDate(billingCycle.next_billing_date) : '—'}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Plan Price</p>
            <p className="font-medium text-white">
              {plan ? `${plan.currency} ${plan.price}/${plan.billing_interval === 'monthly' ? 'mo' : 'yr'}` : '—'}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          {subscription.status === 'trial' && (
            <button
              onClick={() => runAction(() => subscriptionService.activate(subscription.id), 'Subscription activated!')}
              disabled={actionLoading}
              className="btn-primary"
            >
              <FiPower /> Activate Now
            </button>
          )}
          {subscription.status === 'active' && (
            <button
              onClick={() => runAction(() => subscriptionService.pause(subscription.id), 'Subscription paused.')}
              disabled={actionLoading}
              className="btn-secondary"
            >
              <FiPause /> Pause
            </button>
          )}
          {subscription.status === 'paused' && (
            <button
              onClick={() => runAction(() => subscriptionService.resume(subscription.id), 'Subscription resumed!')}
              disabled={actionLoading}
              className="btn-secondary"
            >
              <FiPlay /> Resume
            </button>
          )}
          {subscription.cancel_at_period_end && (
            <button
              onClick={() =>
                runAction(
                  () => subscriptionService.undoCancellation(subscription.id),
                  'Cancellation undone — your subscription will continue renewing.'
                )
              }
              disabled={actionLoading}
              className="btn-secondary"
            >
              <FiRotateCcw /> Undo Cancellation
            </button>
          )}
          {!subscription.cancel_at_period_end && subscription.status !== 'cancelled' && (
            <button
              onClick={() => setCancelModalOpen(true)}
              disabled={actionLoading}
              className="btn-ghost text-red-400 hover:bg-red-500/10 hover:text-red-300"
            >
              <FiXCircle /> Cancel Subscription
            </button>
          )}
        </div>
      </div>

      <CancelSubscriptionModal
        open={cancelModalOpen}
        onClose={() => setCancelModalOpen(false)}
        subscription={subscription}
        onCancelled={loadData}
      />
    </div>
  );
}
