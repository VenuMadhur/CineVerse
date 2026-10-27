import { useCallback, useEffect, useState } from 'react';
import { FiRotateCcw } from 'react-icons/fi';
import PageHeader from '../components/common/PageHeader';
import Table, { TableRow, TableCell } from '../components/common/Table';
import { SkeletonTableRows, Skeleton } from '../components/common/Skeleton';
import Pagination from '../components/common/Pagination';
import { EmptyState, ErrorState } from '../components/common/EmptyState';
import StatusBadge from '../components/common/StatusBadge';
import RequestRefundModal from '../components/refunds/RequestRefundModal';
import { useCustomer } from '../hooks/useCustomer';
import { refundService } from '../services/refundService';
import { invoiceService } from '../services/invoiceService';
import { formatCurrency, formatDate, extractErrorMessage } from '../utils/formatters';

const PAGE_SIZE = 10;
const COLUMNS = ['Refund ID', 'Invoice', 'Amount', 'Status', 'Reason', 'Requested'];

export default function RefundsPage() {
  const { customer } = useCustomer();
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ items: [], total: 0 });
  const [refundableInvoices, setRefundableInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refundingInvoice, setRefundingInvoice] = useState(null);

  const load = useCallback(async () => {
    if (!customer) return;
    setLoading(true);
    setError(null);
    try {
      const [refundsResult, paidInvoicesResult] = await Promise.all([
        refundService.list({ customerId: customer.id, page, pageSize: PAGE_SIZE }),
        invoiceService.list({ customerId: customer.id, status: 'paid', pageSize: 50 }),
      ]);
      setResult(refundsResult);
      setRefundableInvoices(paidInvoicesResult.items);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [customer, page]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div>
        <PageHeader title="Refunds" subtitle="Refunds issued back to you, in full or in part." />
        <Skeleton className="mb-6 h-20 w-full" />
        <Table columns={COLUMNS}>
          <SkeletonTableRows rows={5} columns={COLUMNS.length} />
        </Table>
      </div>
    );
  }

  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <PageHeader title="Refunds" subtitle="Refunds issued back to you, in full or in part." />

      {refundableInvoices.length > 0 && (
        <div className="glass-card mb-8 p-5">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Request a Refund
          </h2>
          <ul className="space-y-2">
            {refundableInvoices.map((invoice) => (
              <li
                key={invoice.id}
                className="flex flex-col gap-2 rounded-lg bg-white/[0.03] px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex items-center gap-3">
                  <span className="font-medium text-white">{invoice.invoice_number}</span>
                  <span className="text-sm text-slate-400">
                    Paid {formatCurrency(invoice.total_amount, invoice.currency)}
                  </span>
                </div>
                <button
                  onClick={() => setRefundingInvoice(invoice)}
                  className="btn-secondary !py-1.5 !px-4 text-sm"
                >
                  Request Refund
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.items.length === 0 ? (
        <EmptyState
          icon={FiRotateCcw}
          title="No refunds"
          description="Refunds you receive or request will appear here. Note: downgrading to a cheaper plan applies your unused time as a credit toward today's plan change automatically — it doesn't generate a separate refund."
        />
      ) : (
        <>
          <Table columns={COLUMNS}>
            {result.items.map((refund) => (
              <TableRow key={refund.id}>
                <TableCell className="font-mono text-xs text-slate-400">
                  {refund.id.slice(0, 8)}
                </TableCell>
                <TableCell className="font-mono text-xs text-slate-400">
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
          <Pagination page={page} pageSize={PAGE_SIZE} total={result.total} onPageChange={setPage} />
        </>
      )}

      <RequestRefundModal
        open={Boolean(refundingInvoice)}
        onClose={() => setRefundingInvoice(null)}
        invoice={refundingInvoice}
        onRequested={load}
      />
    </div>
  );
}
