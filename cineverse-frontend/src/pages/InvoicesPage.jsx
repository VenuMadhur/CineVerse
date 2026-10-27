import { useCallback, useEffect, useState } from 'react';
import { FiFileText } from 'react-icons/fi';
import PageHeader from '../components/common/PageHeader';
import Table, { TableRow, TableCell } from '../components/common/Table';
import { SkeletonTableRows } from '../components/common/Skeleton';
import Pagination from '../components/common/Pagination';
import { EmptyState, ErrorState } from '../components/common/EmptyState';
import StatusBadge from '../components/common/StatusBadge';
import InvoiceDetailModal from '../components/invoices/InvoiceDetailModal';
import { useCustomer } from '../hooks/useCustomer';
import { invoiceService } from '../services/invoiceService';
import { formatCurrency, formatDate, extractErrorMessage } from '../utils/formatters';

const PAGE_SIZE = 10;
const COLUMNS = ['Invoice #', 'Amount', 'Tax', 'Status', 'Issue Date', 'Due Date'];

export default function InvoicesPage() {
  const { customer } = useCustomer();
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState(null);

  const load = useCallback(async () => {
    if (!customer) return;
    setLoading(true);
    setError(null);
    try {
      const data = await invoiceService.list({ customerId: customer.id, page, pageSize: PAGE_SIZE });
      setResult(data);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [customer, page]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <PageHeader title="Invoices" subtitle="Every invoice generated for your subscription, including tax." />

      {loading && (
        <Table columns={COLUMNS}>
          <SkeletonTableRows rows={PAGE_SIZE} columns={COLUMNS.length} />
        </Table>
      )}
      {error && !loading && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && result.items.length === 0 && (
        <EmptyState
          icon={FiFileText}
          title="No invoices yet"
          description="Invoices appear here once your subscription starts billing."
        />
      )}

      {!loading && !error && result.items.length > 0 && (
        <>
          <Table columns={COLUMNS}>
            {result.items.map((invoice) => (
              <TableRow key={invoice.id} onClick={() => setSelectedInvoiceId(invoice.id)}>
                <TableCell className="font-medium text-white">{invoice.invoice_number}</TableCell>
                <TableCell>{formatCurrency(invoice.total_amount, invoice.currency)}</TableCell>
                <TableCell>{formatCurrency(invoice.tax_amount, invoice.currency)}</TableCell>
                <TableCell>
                  <StatusBadge status={invoice.status} />
                </TableCell>
                <TableCell>{formatDate(invoice.created_at)}</TableCell>
                <TableCell>{formatDate(invoice.due_date)}</TableCell>
              </TableRow>
            ))}
          </Table>
          <Pagination page={page} pageSize={PAGE_SIZE} total={result.total} onPageChange={setPage} />
        </>
      )}

      <InvoiceDetailModal
        open={Boolean(selectedInvoiceId)}
        onClose={() => setSelectedInvoiceId(null)}
        invoiceId={selectedInvoiceId}
        onChanged={load}
      />
    </div>
  );
}
