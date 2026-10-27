import { useCallback, useEffect, useMemo, useState } from 'react';
import { customerService } from '../services/customerService';
import { useAuth } from '../hooks/useAuth';

import { CustomerContext } from './CustomerContextStore';

/**
 * Bridges the JWT `User` account to its `Customer` billing record via
 * the backend's GET /customers/me (Phase 1B), which is backed by the
 * Customer.user_id ownership link added in Phase 1A.
 *
 * This replaces an earlier client-side bridge (a localStorage
 * customerId cache + a paginated email search across all customers)
 * that existed only because the backend had no such link at the
 * time. The backend is now the single source of truth: a 404 from
 * GET /customers/me means "no customer yet," full stop -- no more
 * multi-strategy fallback resolution or race-guarding needed.
 */
export function CustomerProvider({ children }) {
  const { isAuthenticated, userId, isSuperuser, roleLoading } = useAuth();
  const [customer, setCustomer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [needsSetup, setNeedsSetup] = useState(false);

  useEffect(() => {
    // QA fix (confirmed race condition): if a customer logs out and a
    // different customer logs back in quickly, the *previous*
    // customer's still-in-flight GET /customers/me request could
    // resolve *after* the new one (e.g. on a slower network), and
    // without this guard its stale response would silently overwrite
    // the correct, freshly-loaded data with no way to self-correct
    // short of a hard refresh. Mirrors the same cancelled-flag
    // pattern DashboardPage's own load effect already uses correctly.
    let cancelled = false;

    const run = async () => {
      if (roleLoading) {
        return;
      }

      if (!isAuthenticated) {
        if (!cancelled) {
          setCustomer(null);
          setNeedsSetup(false);
        }
        return;
      }

      if (isSuperuser) {
        if (!cancelled) {
          setCustomer(null);
          setNeedsSetup(false);
        }
        return;
      }

      setLoading(true);
      try {
        const record = await customerService.getMe();
        if (cancelled) return;
        setCustomer(record);
        setNeedsSetup(false);
      } catch (err) {
        if (cancelled) return;
        if (err?.response?.status === 404) {
          // No customer linked to this account yet -- expected for a
          // brand-new registration mid-flow, or a pre-Phase-1A account
          // that the one-time backfill couldn't match.
          setCustomer(null);
          setNeedsSetup(true);
        } else {
          // Unexpected error (network, 5xx, etc.) -- don't misreport
          // this as "needs setup"; just leave customer unresolved so a
          // retry (refreshCustomer) can be attempted.
          setCustomer(null);
          setNeedsSetup(false);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    run();

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, userId, isSuperuser, roleLoading]);
  const resolveCustomer = useCallback(async () => {
    if (roleLoading) return;
    
    if (!isAuthenticated) {
      setCustomer(null);
      setNeedsSetup(false);
      return;
    }

    if (isSuperuser) {
      setCustomer(null);
      setNeedsSetup(false);
      return;
    }
    setLoading(true);
    try {
      const record = await customerService.getMe();
      setCustomer(record);
      setNeedsSetup(false);
    } catch (err) {
      if (err?.response?.status === 404) {
        setCustomer(null);
        setNeedsSetup(true);
      } else {
        setCustomer(null);
        setNeedsSetup(false);
      }
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, isSuperuser, roleLoading]);

  const provisionCustomer = useCallback(
    async ({ name, email, country, phoneNumber, address }) => {
      const record = await customerService.create({ name, email, country, phoneNumber, address });
      setCustomer(record);
      setNeedsSetup(false);
      return record;
    },
    []
  );

  const updateCustomer = useCallback(
    async (fields) => {
      if (!customer) return null;
      const updated = await customerService.update(customer.id, fields);
      setCustomer(updated);
      return updated;
    },
    [customer]
  );

  const value = useMemo(
    () => ({
      customer,
      loadingCustomer: loading,
      needsSetup,
      refreshCustomer: resolveCustomer,
      provisionCustomer,
      updateCustomer,
    }),
    [customer, loading, needsSetup, resolveCustomer, provisionCustomer, updateCustomer]
  );

  return <CustomerContext.Provider value={value}>{children}</CustomerContext.Provider>;
}
