import { useCallback, useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { FiFilm } from 'react-icons/fi';
import PageHeader from '../components/common/PageHeader';
import PlanCard from '../components/subscription/PlanCard';
import ProrationModal from '../components/subscription/ProrationModal';
import { SkeletonPlanGrid } from '../components/common/Skeleton';
import { EmptyState, ErrorState } from '../components/common/EmptyState';
import StatusBadge from '../components/common/StatusBadge';
import { useCustomer } from '../hooks/useCustomer';
import { planService } from '../services/planService';
import { subscriptionService } from '../services/subscriptionService';
import { extractErrorMessage } from '../utils/formatters';

/**
 * Dedicated Plans module: browse all active plans and Subscribe /
 * Upgrade / Downgrade. Proration is always calculated and confirmed
 * via the backend's proration-preview + change-plan endpoints (see
 * ProrationModal) -- never computed client-side. Managing an
 * existing subscription's trial/active/paused status, or pausing/
 * resuming/cancelling it, lives on the separate Subscriptions page.
 */
export default function PlansPage() {
  const { customer } = useCustomer();
  const [plans, setPlans] = useState([]);
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [prorationTarget, setProrationTarget] = useState(null);

  const currentPlan = plans.find((p) => p.id === subscription?.plan_id) || null;
  const hasActiveSub = subscription && subscription.status !== 'cancelled';

  const loadData = useCallback(async () => {
    if (!customer) return;
    setLoading(true);
    setError(null);
    try {
      const [plansResult, subsResult] = await Promise.all([
        planService.list({ status: 'active', pageSize: 50 }),
        subscriptionService.list({ customerId: customer.id, pageSize: 5 }),
      ]);
      setPlans(plansResult.items);
      const active = subsResult.items.find((s) => s.status !== 'cancelled');
      setSubscription(active || subsResult.items[0] || null);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [customer]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSubscribe = async (plan) => {
    setActionLoading(true);
    try {
      await subscriptionService.create({ customerId: customer.id, planId: plan.id });
      toast.success(`Subscribed to ${plan.name}! Enjoy your trial.`);
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
        <PageHeader title="Plans" subtitle="Pick the plan that fits how you watch." />
        <SkeletonPlanGrid />
      </div>
    );
  }

  if (error) return <ErrorState message={error} onRetry={loadData} />;

  return (
    <div>
      <PageHeader title="Plans" subtitle="Pick the plan that fits how you watch." />

      {hasActiveSub && currentPlan && (
        <div className="glass-card mb-8 flex items-center gap-3 p-4">
          <span className="text-sm text-slate-400">You&apos;re currently on</span>
          <span className="font-bold text-white">{currentPlan.name}</span>
          <StatusBadge status={subscription.status} />
        </div>
      )}

      {plans.length === 0 ? (
        <EmptyState
          icon={FiFilm}
          title="No plans available"
          description="Check back soon — new plans are on the way."
        />
      ) : (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {plans.map((plan) => {
            const isCurrent = hasActiveSub && plan.id === subscription.plan_id;

            return (
              <PlanCard
                key={plan.id}
                plan={plan}
                highlighted={isCurrent}
                footer={
                  isCurrent ? (
                    <button disabled className="btn-secondary w-full opacity-60">
                      Current Plan
                    </button>
                  ) : hasActiveSub ? (
                    <button
                      onClick={() => setProrationTarget(plan)}
                      disabled={actionLoading}
                      className="btn-primary w-full"
                    >
                      Switch to {plan.name}
                    </button>
                  ) : (
                    <button
                      onClick={() => handleSubscribe(plan)}
                      disabled={actionLoading}
                      className="btn-primary w-full"
                    >
                      Subscribe
                    </button>
                  )
                }
              />
            );
          })}
        </div>
      )}

      <ProrationModal
        open={Boolean(prorationTarget)}
        onClose={() => setProrationTarget(null)}
        subscription={subscription}
        currentPlan={currentPlan}
        targetPlan={prorationTarget}
        onChanged={loadData}
      />
    </div>
  );
}
