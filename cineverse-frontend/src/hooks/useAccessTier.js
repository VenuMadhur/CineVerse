import { useEffect, useState } from 'react';
import { useCustomer } from './useCustomer';
import { subscriptionService } from '../services/subscriptionService';
import { planService } from '../services/planService';
import { TIER_RANK } from '../data/catalogData';

/**
 * Determines which demo-catalog tier (starter/professional/premium)
 * the current customer's real subscription unlocks. Reuses the exact
 * same subscriptionService/planService calls already used elsewhere
 * (e.g. DashboardPage) -- no new API calls, no duplicated backend
 * logic, no new subscription/entitlement concept on the backend.
 *
 * Tier is derived by ranking the customer's current plan by price
 * among all active plans (bottom third -> starter, middle -> premium,
 * -- more precisely: split into 3 buckets by rank) rather than
 * hardcoding an assumption that a plan is literally named "Starter" /
 * "Professional" / "Premium", since real deployments may name plans
 * differently. A higher real-money tier always unlocks everything a
 * lower tier does.
 */
export function useAccessTier() {
  const { customer } = useCustomer();
  const [tier, setTier] = useState(null); // 'starter' | 'professional' | 'premium' | null
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function resolve() {
      if (!customer) {
        setTier(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const [subsResult, plansResult] = await Promise.all([
          subscriptionService.list({ customerId: customer.id, pageSize: 5 }),
          planService.list({ status: 'active', pageSize: 100 }),
        ]);
        if (cancelled) return;

        // Only a currently-in-effect subscription grants access --
        // matches this platform's own model where trial subscribers
        // already have full, real access (see the backend's trial
        // design), but paused/past_due/cancelled do not.
        const activeSub = subsResult.items.find((s) => s.status === 'active' || s.status === 'trial');
        if (!activeSub) {
          setTier(null);
          setLoading(false);
          return;
        }

        const sortedPlans = [...plansResult.items].sort((a, b) => Number(a.price) - Number(b.price));
        const rank = sortedPlans.findIndex((p) => p.id === activeSub.plan_id);

        if (rank === -1 || sortedPlans.length === 0) {
          setTier(null);
        } else {
          const third = Math.ceil(sortedPlans.length / 3) || 1;
          if (rank < third) setTier('starter');
          else if (rank < third * 2) setTier('professional');
          else setTier('premium');
        }
      } catch {
        // Fail closed: if the customer's plan/subscription can't be
        // determined, treat as no access rather than granting it.
        if (!cancelled) setTier(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    resolve();
    return () => {
      cancelled = true;
    };
  }, [customer]);

  const hasAccess = (requiredTier) => {
    if (!tier) return false;
    return TIER_RANK[tier] >= TIER_RANK[requiredTier];
  };

  return { tier, loading, hasAccess };
}
