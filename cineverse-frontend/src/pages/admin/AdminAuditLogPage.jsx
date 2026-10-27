import { useCallback, useEffect, useState } from 'react';
import { FiActivity } from 'react-icons/fi';
import PageHeader from '../../components/common/PageHeader';
import FilterChips from '../../components/common/FilterChips';
import Table, { TableRow, TableCell } from '../../components/common/Table';
import { SkeletonTableRows } from '../../components/common/Skeleton';
import Pagination from '../../components/common/Pagination';
import { EmptyState, ErrorState } from '../../components/common/EmptyState';
import { auditLogService } from '../../services/auditLogService';
import { formatDateTime, titleCase } from '../../utils/formatters';

const PAGE_SIZE = 20;
const COLUMNS = ['Event', 'Entity Type', 'Entity ID', 'Description', 'IP Address', 'Role', 'When'];
const ENTITY_TYPES = ['', 'customer', 'subscription', 'invoice', 'payment', 'refund', 'plan'];

/**
 * Admin view of the platform-wide audit trail. Reuses the existing
 * GET /audit-logs (admin-only as of the final production review --
 * previously ungated, a real gap fixed alongside this page) and
 * auditLogService.list(), which already existed but had no page
 * calling it before now.
 */
export default function AdminAuditLogPage() {
  const [entityType, setEntityType] = useState('');
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await auditLogService.list({
        entityType: entityType || undefined,
        page,
        pageSize: PAGE_SIZE,
      });
      setResult(data);
    } catch (err) {
      setError(err?.response?.data?.error?.message || 'Failed to load the audit log.');
    } finally {
      setLoading(false);
    }
  }, [entityType, page]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="animate-fade-in">
      <PageHeader title="Audit Log" subtitle="Every recorded event across the platform." />

      <FilterChips
        options={ENTITY_TYPES}
        value={entityType}
        onChange={(type) => {
          setEntityType(type);
          setPage(1);
        }}
      />

      {loading && (
        <Table columns={COLUMNS}>
          <SkeletonTableRows rows={PAGE_SIZE} columns={COLUMNS.length} />
        </Table>
      )}
      {error && !loading && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && result.items.length === 0 && (
        <EmptyState icon={FiActivity} title="No audit events found" />
      )}

      {!loading && !error && result.items.length > 0 && (
        <>
          <Table columns={COLUMNS}>
            {result.items.map((event) => (
              <TableRow key={event.id}>
                <TableCell className="font-medium text-white">{titleCase(event.event_type)}</TableCell>
                <TableCell className="capitalize">{event.entity_type}</TableCell>
                <TableCell className="font-mono text-xs text-slate-400">
                  {event.entity_id ? event.entity_id.slice(0, 8) : '—'}
                </TableCell>
                <TableCell className="max-w-md">
                  <p className="truncate">{event.description}</p>
                  {(event.old_value || event.new_value) && (
                    <p className="mt-0.5 truncate text-xs text-slate-500">
                      {event.old_value && <span>was: {event.old_value}</span>}
                      {event.old_value && event.new_value && ' → '}
                      {event.new_value && <span>now: {event.new_value}</span>}
                    </p>
                  )}
                  {event.remarks && (
                    <p className="mt-0.5 truncate text-xs italic text-slate-500">{event.remarks}</p>
                  )}
                </TableCell>
                <TableCell className="font-mono text-xs text-slate-400">
                  {event.ip_address || '—'}
                </TableCell>
                <TableCell className="capitalize text-slate-400">{event.actor_role || '—'}</TableCell>
                <TableCell>{formatDateTime(event.created_at)}</TableCell>
              </TableRow>
            ))}
          </Table>
          <Pagination page={page} pageSize={PAGE_SIZE} total={result.total} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
