import { useCallback, useEffect, useState } from 'react';
import { FiCreditCard } from 'react-icons/fi';
import PageHeader from '../components/common/PageHeader';
import Table, { TableRow, TableCell } from '../components/common/Table';
import { SkeletonTableRows, Skeleton } from '../components/common/Skeleton';
import { EmptyState, ErrorState } from '../components/common/EmptyState';
import StatusBadge from '../components/common/StatusBadge';
import ProcessPaymentModal from '../components/payments/ProcessPaymentModal';
import { useCustomer } from '../hooks/useCustomer';
import { invoiceService } from '../services/invoiceService';
import { formatCurrency, formatDateTime, extractErrorMessage } from '../utils/formatters';

const COLUMNS = ['Payment ID', 'Invoice', 'Amount', 'Method', 'Status', 'Date'];

/**
 * The backend's GET /payments only filters by invoice_id, not
 * customer_id -- there is no "list my payments" endpoint. So this
 * page fetches the customer's invoices (existing GET /invoices?
 * customer_id=) and, for each, its payment history (existing
 * GET /invoices/{id}/payments), then merges the results client-side.
 * No new backend functionality is invented.
 */
export default function PaymentsPage() {
  const { customer } = useCustomer();
  const [rows, setRows] = useState([]);
  const [outstandingInvoices, setOutstandingInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [payingInvoice, setPayingInvoice] = useState(null);

  const load = useCallback(async () => {
    if (!customer) return;
    setLoading(true);
    setError(null);
    try {
      const invoicesResult = await invoiceService.list({ customerId: customer.id, pageSize: 50 });

      setOutstandingInvoices(
        invoicesResult.items.filter((inv) => inv.status === 'open' || inv.status === 'failed')
      );

      const perInvoicePayments = await Promise.all(
        invoicesResult.items.map(async (invoice) => {
          const payments = await invoiceService.listPayments(invoice.id);
          return payments.map((payment) => ({ ...payment, invoiceNumber: invoice.invoice_number }));
        })
      );
      const merged = perInvoicePayments
        .flat()
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      setRows(merged);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [customer]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div>
        <PageHeader title="Payments" subtitle="Pay outstanding invoices and review your payment history." />
        <Skeleton className="mb-6 h-24 w-full" />
        <Table columns={COLUMNS}>
          <SkeletonTableRows rows={5} columns={COLUMNS.length} />
        </Table>
      </div>
    );
  }

  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <PageHeader title="Payments" subtitle="Pay outstanding invoices and review your payment history." />

      {outstandingInvoices.length > 0 && (
        <div className="glass-card mb-8 p-5">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Outstanding Invoices
          </h2>
          <ul className="space-y-2">
            {outstandingInvoices.map((invoice) => (
              <li
                key={invoice.id}
                className="flex flex-col gap-2 rounded-lg bg-white/[0.03] px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex items-center gap-3">
                  <span className="font-medium text-white">{invoice.invoice_number}</span>
                  <StatusBadge status={invoice.status} />
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-semibold text-white">
                    {formatCurrency(invoice.total_amount, invoice.currency)}
                  </span>
                  <button onClick={() => setPayingInvoice(invoice)} className="btn-primary !py-1.5 !px-4 text-sm">
                    Pay Now
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {rows.length === 0 ? (
        <EmptyState
          icon={FiCreditCard}
          title="No payments yet"
          description="Payment attempts will show up here once an invoice is processed."
        />
      ) : (
        <Table columns={COLUMNS}>
          {rows.map((payment) => (
            <TableRow key={payment.id}>
              <TableCell className="font-mono text-xs text-slate-400">
                {payment.gateway_reference || payment.id.slice(0, 8)}
              </TableCell>
              <TableCell className="text-white">{payment.invoiceNumber}</TableCell>
              <TableCell>{formatCurrency(payment.amount, payment.currency)}</TableCell>
              <TableCell className="capitalize">{payment.payment_method?.replace('_', ' ')}</TableCell>
              <TableCell>
                <StatusBadge status={payment.status} />
              </TableCell>
              <TableCell>{formatDateTime(payment.processed_at || payment.created_at)}</TableCell>
            </TableRow>
          ))}
        </Table>
      )}

      <ProcessPaymentModal
        open={Boolean(payingInvoice)}
        onClose={() => setPayingInvoice(null)}
        invoice={payingInvoice}
        onProcessed={load}
      />
    </div>
  );
}
