import { useCallback, useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { FiFileText, FiDownload, FiEye } from 'react-icons/fi';
import PageHeader from '../../components/common/PageHeader';
import FilterChips from '../../components/common/FilterChips';
import Table, { TableRow, TableCell } from '../../components/common/Table';
import { SkeletonTableRows } from '../../components/common/Skeleton';
import Pagination from '../../components/common/Pagination';
import { EmptyState, ErrorState } from '../../components/common/EmptyState';
import StatusBadge from '../../components/common/StatusBadge';
import Modal from '../../components/common/Modal';
import Spinner from '../../components/common/Spinner';
import { invoiceService } from '../../services/invoiceService';
import { formatCurrency, formatDate, extractErrorMessage } from '../../utils/formatters';
import { downloadBlob } from '../../utils/download';
import { INVOICE_STATUS_LABELS } from '../../utils/constants';

const PAGE_SIZE = 10;
const COLUMNS = [
  'Invoice #',
  'Customer ID',
  'Amount',
  'Currency',
  'Status',
  'Due Date',
  'Created',
  'Actions',
];
const STATUS_OPTIONS = ['', 'open', 'paid', 'failed', 'void', 'refunded', 'draft'];

/**
 * Admin view of every invoice on the platform. Reuses invoiceService
 * -- the same GET /invoices the customer-facing InvoicesPage calls,
 * without a customer_id filter (admins see everything). Adds status
 * filter and PDF download, reusing invoiceService.downloadPdf() which
 * already existed for the customer-facing invoice detail view.
 */
export default function AdminInvoicesPage() {
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [detailInvoice, setDetailInvoice] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [downloading, setDownloading] = useState(null); // invoice id being downloaded

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await invoiceService.list({
        status: status || undefined,
        page,
        pageSize: PAGE_SIZE,
      });
      setResult(data);
    } catch (err) {
      setError(err?.response?.data?.error?.message || 'Failed to load invoices.');
    } finally {
      setLoading(false);
    }
  }, [status, page]);

  useEffect(() => {
    load();
  }, [load]);

  const handleView = async (invoice) => {
    setDetailLoading(true);
    setDetailInvoice(invoice); // open modal immediately with basic data
    try {
      const detail = await invoiceService.get(invoice.id);
      setDetailInvoice(detail);
    } catch {
      // keep the basic data we already have
    } finally {
      setDetailLoading(false);
    }
  };

  const handleDownload = async (invoice) => {
    setDownloading(invoice.id);
    try {
      const { blob, filename } = await invoiceService.downloadPdf(invoice.id);
      downloadBlob(blob, filename);
      toast.success('PDF downloaded.');
    } catch (err) {
      toast.error(extractErrorMessage(err) || 'Failed to download PDF.');
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader title="Invoices" subtitle="Every invoice on the platform." />

      <FilterChips
        options={STATUS_OPTIONS}
        value={status}
        onChange={(s) => {
          setStatus(s);
          setPage(1);
        }}
        formatLabel={(s) => (s ? (INVOICE_STATUS_LABELS[s] || s) : 'All')}
      />

      {loading && (
        <Table columns={COLUMNS}>
          <SkeletonTableRows rows={PAGE_SIZE} columns={COLUMNS.length} />
        </Table>
      )}
      {error && !loading && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && result.items.length === 0 && (
        <EmptyState icon={FiFileText} title="No invoices found" />
      )}

      {!loading && !error && result.items.length > 0 && (
        <>
          <Table columns={COLUMNS}>
            {result.items.map((inv) => (
              <TableRow key={inv.id}>
                <TableCell className="font-mono text-xs font-medium text-white">
                  {inv.invoice_number}
                </TableCell>
                <TableCell className="font-mono text-xs text-slate-400" title={inv.customer_id}>
                  {inv.customer_id.slice(0, 8)}
                </TableCell>
                <TableCell>{formatCurrency(inv.total_amount, inv.currency)}</TableCell>
                <TableCell className="font-mono text-xs text-slate-400">{inv.currency}</TableCell>
                <TableCell>
                  <StatusBadge status={inv.status} />
                </TableCell>
                <TableCell>{formatDate(inv.due_date)}</TableCell>
                <TableCell>{formatDate(inv.created_at)}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <button
                      className="focus-ring btn-ghost !p-1.5 text-slate-300 hover:text-white"
                      title="View line items"
                      aria-label={`View line items for invoice ${inv.invoice_number}`}
                      onClick={() => handleView(inv)}
                    >
                      <FiEye size={15} />
                    </button>
                    <button
                      className="focus-ring btn-ghost !p-1.5 text-slate-300 hover:text-white"
                      title="Download PDF"
                      aria-label={`Download PDF for invoice ${inv.invoice_number}`}
                      onClick={() => handleDownload(inv)}
                      disabled={downloading === inv.id}
                    >
                      {downloading === inv.id ? (
                        <Spinner size="sm" />
                      ) : (
                        <FiDownload size={15} />
                      )}
                    </button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </Table>
          <Pagination page={page} pageSize={PAGE_SIZE} total={result.total} onPageChange={setPage} />
        </>
      )}

      {/* Invoice Detail Modal */}
      <Modal
        open={Boolean(detailInvoice)}
        onClose={() => setDetailInvoice(null)}
        title={`Invoice ${detailInvoice?.invoice_number || ''}`}
        maxWidth="max-w-2xl"
      >
        {detailInvoice && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs text-slate-500">Status</p>
                <StatusBadge status={detailInvoice.status} />
              </div>
              <div>
                <p className="text-xs text-slate-500">Currency</p>
                <p className="font-mono text-white">{detailInvoice.currency}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Subtotal</p>
                <p className="text-white">{formatCurrency(detailInvoice.subtotal, detailInvoice.currency)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Tax</p>
                <p className="text-white">{formatCurrency(detailInvoice.tax_amount, detailInvoice.currency)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Total</p>
                <p className="text-lg font-bold text-white">
                  {formatCurrency(detailInvoice.total_amount, detailInvoice.currency)}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Due Date</p>
                <p className="text-white">{formatDate(detailInvoice.due_date)}</p>
              </div>
            </div>

            {detailInvoice.line_items && detailInvoice.line_items.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Line Items
                </p>
                <div className="divide-y divide-white/5 rounded-lg border border-white/10">
                  {detailInvoice.line_items.map((li) => (
                    <div key={li.id} className="flex items-center justify-between px-4 py-2.5 text-sm">
                      <div>
                        <p className="text-white">{li.description}</p>
                        <p className="text-xs capitalize text-slate-500">
                          {li.item_type.replace(/_/g, ' ')}
                        </p>
                      </div>
                      <p className={li.amount < 0 ? 'text-sky-400' : 'text-white'}>
                        {formatCurrency(li.amount, detailInvoice.currency)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {detailLoading && (
              <div className="flex justify-center py-4">
                <Spinner />
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button
                onClick={() => handleDownload(detailInvoice)}
                disabled={downloading === detailInvoice.id}
                className="btn-primary flex-1"
              >
                {downloading === detailInvoice.id ? (
                  <Spinner size="sm" />
                ) : (
                  <><FiDownload size={16} /> Download PDF</>
                )}
              </button>
              <button onClick={() => setDetailInvoice(null)} className="btn-secondary flex-1">
                Close
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
