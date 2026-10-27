import { useCallback, useEffect, useState } from 'react';
import PageHeader from '../components/common/PageHeader';
import { SkeletonCard } from '../components/common/Skeleton';
import Pagination from '../components/common/Pagination';
import { ErrorState } from '../components/common/EmptyState';
import RecentActivity from '../components/dashboard/RecentActivity';
import { auditLogService } from '../services/auditLogService';

const PAGE_SIZE = 20;

/**
 * Account-wide Activity Timeline: every event across the customer's
 * own account (registration, logins/logouts, subscriptions, invoices,
 * payments, refunds), chronological -- reuses the exact same
 * RecentActivity component the Dashboard's smaller preview card
 * already uses, just with the full paginated list from
 * GET /audit-logs/me instead of a single subscription's events.
 */
export default function ActivityPage() {
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await auditLogService.listForMe({ page, pageSize: PAGE_SIZE });
      setResult(data);
    } catch (err) {
      setError(err?.response?.data?.error?.message || 'Failed to load your activity.');
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <PageHeader
        title="Activity"
        subtitle="Everything that's happened on your account, in one place."
      />

      {loading && (
        <div className="glass-card space-y-4 p-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}
      {error && !loading && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && (
        <>
          <div className="glass-card p-6">
            <RecentActivity events={result.items} limit={PAGE_SIZE} />
          </div>
          {result.items.length > 0 && (
            <Pagination page={page} pageSize={PAGE_SIZE} total={result.total} onPageChange={setPage} />
          )}
        </>
      )}
    </div>
  );
}
