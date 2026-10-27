import { useCallback, useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import toast from 'react-hot-toast';
import { FiRotateCcw, FiPlusCircle } from 'react-icons/fi';
import PageHeader from '../../components/common/PageHeader';
import FilterChips from '../../components/common/FilterChips';
import Table, { TableRow, TableCell } from '../../components/common/Table';
import { SkeletonTableRows } from '../../components/common/Skeleton';
import Pagination from '../../components/common/Pagination';
import { EmptyState, ErrorState } from '../../components/common/EmptyState';
import StatusBadge from '../../components/common/StatusBadge';
import Modal from '../../components/common/Modal';
import Spinner from '../../components/common/Spinner';
import { refundService } from '../../services/refundService';
import { formatCurrency, formatDate, extractErrorMessage } from '../../utils/formatters';
import { REFUND_STATUS_LABELS } from '../../utils/constants';

const PAGE_SIZE = 10;
const COLUMNS = ['Refund ID', 'Invoice ID', 'Amount', 'Status', 'Reason', 'Requested'];
const STATUS_OPTIONS = ['', 'pending', 'completed', 'failed'];

/**
 * Admin view of every refund on the platform. Enhanced with a status
 * filter and an "Issue Refund" action. Reuses refundService.create()
 * -- the same POST /refunds the customer-facing RefundsPage uses;
 * admins bypass ownership checks server-side via get_current_superuser
 * dependency on the backend, so no new endpoint is needed.
 */
export default function AdminRefundsPage() {
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [issueOpen, setIssueOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await refundService.list({ page, pageSize: PAGE_SIZE });
      setResult(data);
    } catch (err) {
      setError(err?.response?.data?.error?.message || 'Failed to load refunds.');
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  // Client-side status filter — the backend GET /refunds has no status
  // query param, so we filter after fetching. The status filter resets
  // pagination to page 1 to avoid empty views.
  const displayed =
    status
      ? result.items.filter((r) => r.status === status)
      : result.items;

  const onIssueSubmit = async (values) => {
    setSubmitting(true);
    try {
      await refundService.create({
        invoiceId: values.invoiceId.trim(),
        amount: values.amount ? parseFloat(values.amount) : undefined,
        reason: values.reason,
      });
      toast.success('Refund issued successfully.');
      setIssueOpen(false);
      reset();
      load();
    } catch (err) {
      toast.error(extractErrorMessage(err) || 'Failed to issue refund.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Refunds"
        subtitle="Every refund issued on the platform."
        actions={
          <button
            onClick={() => {
              reset();
              setIssueOpen(true);
            }}
            className="btn-primary"
          >
            <FiPlusCircle size={16} /> Issue Refund
          </button>
        }
      />

      <FilterChips
        options={STATUS_OPTIONS}
        value={status}
        onChange={(s) => {
          setStatus(s);
          setPage(1);
        }}
        formatLabel={(s) => (s ? (REFUND_STATUS_LABELS[s] || s) : 'All')}
      />

      {loading && (
        <Table columns={COLUMNS}>
          <SkeletonTableRows rows={PAGE_SIZE} columns={COLUMNS.length} />
        </Table>
      )}
      {error && !loading && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && displayed.length === 0 && (
        <EmptyState icon={FiRotateCcw} title="No refunds found" />
      )}

      {!loading && !error && displayed.length > 0 && (
        <>
          <Table columns={COLUMNS}>
            {displayed.map((refund) => (
              <TableRow key={refund.id}>
                <TableCell className="font-mono text-xs text-slate-400" title={refund.id}>
                  {refund.id.slice(0, 8)}
                </TableCell>
                <TableCell className="font-mono text-xs text-slate-400" title={refund.invoice_id}>
                  {refund.invoice_id.slice(0, 8)}
                </TableCell>
                <TableCell>{formatCurrency(refund.amount, refund.currency)}</TableCell>
                <TableCell>
                  <StatusBadge status={refund.status} />
                </TableCell>
                <TableCell className="max-w-xs truncate">{refund.reason}</TableCell>
                <TableCell>{formatDate(refund.created_at)}</TableCell>
              </TableRow>
            ))}
          </Table>
          {!status && (
            <Pagination page={page} pageSize={PAGE_SIZE} total={result.total} onPageChange={setPage} />
          )}
        </>
      )}

      {/* Issue Refund Modal */}
      <Modal open={issueOpen} onClose={() => !submitting && setIssueOpen(false)} title="Issue Refund">
        <form onSubmit={handleSubmit(onIssueSubmit)} className="space-y-4">
          <div>
            <label className="label-text">Invoice ID</label>
            <input
              className="input-field font-mono text-sm"
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              {...register('invoiceId', {
                required: 'Invoice ID is required',
                pattern: {
                  value: /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
                  message: 'Must be a valid UUID',
                },
              })}
            />
            {errors.invoiceId && (
              <p className="mt-1 text-xs text-red-400">{errors.invoiceId.message}</p>
            )}
          </div>

          <div>
            <label className="label-text">Amount (leave blank for full refund)</label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              className="input-field"
              placeholder="e.g. 9.99"
              {...register('amount', {
                min: { value: 0.01, message: 'Amount must be greater than 0' },
              })}
            />
            {errors.amount && (
              <p className="mt-1 text-xs text-red-400">{errors.amount.message}</p>
            )}
          </div>

          <div>
            <label className="label-text">Reason</label>
            <textarea
              className="input-field resize-none"
              rows={3}
              placeholder="Provide a clear reason for the refund…"
              {...register('reason', { required: 'Reason is required' })}
            />
            {errors.reason && (
              <p className="mt-1 text-xs text-red-400">{errors.reason.message}</p>
            )}
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={() => setIssueOpen(false)}
              disabled={submitting}
              className="btn-secondary flex-1"
            >
              Cancel
            </button>
            <button type="submit" disabled={submitting} className="btn-primary flex-1">
              {submitting ? <Spinner size="sm" /> : 'Issue Refund'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
