import { useCallback, useEffect, useState } from 'react';
import { FiCreditCard } from 'react-icons/fi';
import PageHeader from '../../components/common/PageHeader';
import FilterChips from '../../components/common/FilterChips';
import Table, { TableRow, TableCell } from '../../components/common/Table';
import { SkeletonTableRows } from '../../components/common/Skeleton';
import Pagination from '../../components/common/Pagination';
import { EmptyState, ErrorState } from '../../components/common/EmptyState';
import StatusBadge from '../../components/common/StatusBadge';
import { paymentService } from '../../services/paymentService';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { PAYMENT_STATUS_LABELS } from '../../utils/constants';

const PAGE_SIZE = 10;
const COLUMNS = ['Transaction', 'Invoice ID', 'Amount', 'Method', 'Attempt', 'Status', 'Date'];
// paymentService.list() accepts a status param -- the backend
// PaymentRepository.list_all already supports filtering by status.
const STATUS_OPTIONS = ['', 'succeeded', 'failed', 'pending', 'refunded'];

/**
 * Admin view of every payment attempt on the platform. Enhanced with
 * a status filter and the invoice_id column (for tracing a payment
 * back to its invoice). Reuses paymentService.list() -- no new API.
 *
 * The backend PaymentRecordResponse does not include customer_id
 * directly -- it's only accessible via the linked invoice. Showing
 * customer context would require either an extra lookup per row or a
 * new endpoint, both out of scope for this targeted fix. The invoice_id
 * column provides a clear paper trail.
 */
export default function AdminPaymentsPage() {
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await paymentService.list({
        status: status || undefined,
        page,
        pageSize: PAGE_SIZE,
      });
      setResult(data);
    } catch (err) {
      setError(err?.response?.data?.error?.message || 'Failed to load payments.');
    } finally {
      setLoading(false);
    }
  }, [status, page]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="animate-fade-in">
      <PageHeader title="Payments" subtitle="Every payment attempt on the platform." />

      <FilterChips
        options={STATUS_OPTIONS}
        value={status}
        onChange={(s) => {
          setStatus(s);
          setPage(1);
        }}
        formatLabel={(s) => (s ? (PAYMENT_STATUS_LABELS[s] || s) : 'All')}
      />

      {loading && (
        <Table columns={COLUMNS}>
          <SkeletonTableRows rows={PAGE_SIZE} columns={COLUMNS.length} />
        </Table>
      )}
      {error && !loading && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && result.items.length === 0 && (
        <EmptyState icon={FiCreditCard} title="No payments found" />
      )}

      {!loading && !error && result.items.length > 0 && (
        <>
          <Table columns={COLUMNS}>
            {result.items.map((payment) => (
              <TableRow key={payment.id}>
                <TableCell className="font-mono text-xs text-slate-400" title={payment.gateway_reference}>
                  {payment.gateway_reference?.slice(0, 16) || payment.id.slice(0, 8)}
                </TableCell>
                <TableCell className="font-mono text-xs text-slate-400" title={payment.invoice_id}>
                  {payment.invoice_id.slice(0, 8)}
                </TableCell>
                <TableCell>{formatCurrency(payment.amount, payment.currency)}</TableCell>
                <TableCell className="capitalize">
                  {payment.payment_method?.replace(/_/g, ' ')}
                </TableCell>
                <TableCell className="text-slate-400">#{payment.attempt_number}</TableCell>
                <TableCell>
                  <StatusBadge status={payment.status} />
                </TableCell>
                <TableCell>{formatDateTime(payment.processed_at || payment.created_at)}</TableCell>
              </TableRow>
            ))}
          </Table>
          <Pagination page={page} pageSize={PAGE_SIZE} total={result.total} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
