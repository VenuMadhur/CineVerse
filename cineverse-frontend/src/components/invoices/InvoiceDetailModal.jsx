import { useCallback, useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { FiDownload, FiPrinter, FiMail } from 'react-icons/fi';
import Modal from '../common/Modal';
import Spinner from '../common/Spinner';
import StatusBadge from '../common/StatusBadge';
import ProcessPaymentModal from '../payments/ProcessPaymentModal';
import RequestRefundModal from '../refunds/RequestRefundModal';
import { invoiceService } from '../../services/invoiceService';
import { downloadBlob, printBlob } from '../../utils/download';
import { formatCurrency, formatDate, titleCase, extractErrorMessage } from '../../utils/formatters';

const REFUND_STATUS_LABELS = {
  none: null, // nothing extra to show -- the invoice Status badge already covers this case
  partial: 'Partially Refunded',
  full: 'Fully Refunded',
};

export default function InvoiceDetailModal({ open, onClose, invoiceId, onChanged }) {
  const [invoice, setInvoice] = useState(null);
  const [payments, setPayments] = useState([]);
  const [refunds, setRefunds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [payModalOpen, setPayModalOpen] = useState(false);
  const [refundModalOpen, setRefundModalOpen] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [printing, setPrinting] = useState(false);
  const [emailingInvoice, setEmailingInvoice] = useState(false);

  const load = useCallback(async () => {
    if (!invoiceId) return;
    setLoading(true);
    setError(null);
    try {
      const [invoiceData, paymentsData, refundsData] = await Promise.all([
        invoiceService.get(invoiceId),
        invoiceService.listPayments(invoiceId),
        invoiceService.listRefunds(invoiceId),
      ]);
      setInvoice(invoiceData);
      setPayments(paymentsData);
      setRefunds(refundsData);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [invoiceId]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  // If the parent modal closes for any reason (backdrop click, X
  // button, Escape) while a nested Pay/Refund modal is open, close
  // those too so they can't remain visible on their own.
  useEffect(() => {
    if (!open) {
      setPayModalOpen(false);
      setRefundModalOpen(false);
    }
  }, [open]);

  const handleRefresh = () => {
    load();
    onChanged?.();
  };

  const handleDownloadPdf = async () => {
    setDownloadingPdf(true);
    try {
      const { blob, filename } = await invoiceService.downloadPdf(invoiceId);
      downloadBlob(blob, filename);
    } catch (err) {
      toast.error(extractErrorMessage(err) || 'Failed to download the invoice PDF.');
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handlePrint = async () => {
    setPrinting(true);
    try {
      const { blob } = await invoiceService.downloadPdf(invoiceId);
      printBlob(blob);
    } catch (err) {
      toast.error(extractErrorMessage(err) || 'Failed to open the invoice for printing.');
    } finally {
      setPrinting(false);
    }
  };

  const handleEmailInvoice = async () => {
    setEmailingInvoice(true);
    try {
      await invoiceService.emailInvoice(invoiceId);
      toast.success("Invoice queued for delivery to your email.");
    } catch (err) {
      toast.error(extractErrorMessage(err) || 'Failed to email the invoice.');
    } finally {
      setEmailingInvoice(false);
    }
  };

  const refundStatusLabel = invoice ? REFUND_STATUS_LABELS[invoice.refund_status] : null;

  return (
    <>
      <Modal open={open} onClose={onClose} title={invoice ? invoice.invoice_number : 'Invoice'} maxWidth="max-w-2xl">
        {loading && (
          <div className="flex justify-center py-10">
            <Spinner />
          </div>
        )}
        {error && !loading && <p className="text-sm text-red-400">{error}</p>}

        {invoice && !loading && (
          <div className="space-y-6">
            <div className="flex flex-wrap justify-end gap-2">
              <button
                onClick={handleEmailInvoice}
                disabled={emailingInvoice}
                className="btn-secondary !py-1.5 !px-4 text-sm"
              >
                {emailingInvoice ? (
                  <>
                    <Spinner size="sm" /> Sending…
                  </>
                ) : (
                  <>
                    <FiMail /> Email Invoice
                  </>
                )}
              </button>
              <button onClick={handlePrint} disabled={printing} className="btn-secondary !py-1.5 !px-4 text-sm">
                {printing ? (
                  <>
                    <Spinner size="sm" /> Opening…
                  </>
                ) : (
                  <>
                    <FiPrinter /> Print
                  </>
                )}
              </button>
              <button
                onClick={handleDownloadPdf}
                disabled={downloadingPdf}
                className="btn-secondary !py-1.5 !px-4 text-sm"
              >
                {downloadingPdf ? (
                  <>
                    <Spinner size="sm" /> Downloading…
                  </>
                ) : (
                  <>
                    <FiDownload /> Download PDF
                  </>
                )}
              </button>
            </div>

            {invoice.customer_name && (
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4 text-sm">
                <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Bill To</p>
                <p className="font-medium text-white">{invoice.customer_name}</p>
                <p className="text-slate-400">{invoice.customer_email}</p>
                <p className="text-slate-400">
                  {[invoice.billing_address, invoice.customer_country].filter(Boolean).join(', ')}
                </p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4 rounded-lg border border-white/10 bg-white/[0.03] p-4 text-sm sm:grid-cols-5">
              <div>
                <p className="text-xs text-slate-500">Status</p>
                <div className="flex flex-wrap items-center gap-1.5">
                  <StatusBadge status={invoice.status} />
                  {refundStatusLabel && (
                    <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-400">
                      {refundStatusLabel}
                    </span>
                  )}
                </div>
              </div>
              <div>
                <p className="text-xs text-slate-500">Tax</p>
                <p className="font-medium text-white">
                  {formatCurrency(invoice.tax_amount, invoice.currency)}
                </p>
              </div>
              {Number(invoice.discount_amount) > 0 && (
                <div>
                  <p className="text-xs text-slate-500">Discount</p>
                  <p className="font-medium text-emerald-400">
                    -{formatCurrency(invoice.discount_amount, invoice.currency)}
                  </p>
                </div>
              )}
              <div>
                <p className="text-xs text-slate-500">Total</p>
                <p className="font-bold text-white">
                  {formatCurrency(invoice.total_amount, invoice.currency)}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Issued</p>
                <p className="text-slate-200">{formatDate(invoice.created_at)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Due</p>
                <p className="text-slate-200">{formatDate(invoice.due_date)}</p>
              </div>
              {invoice.paid_at && (
                <div>
                  <p className="text-xs text-slate-500">Paid</p>
                  <p className="text-emerald-400">{formatDate(invoice.paid_at)}</p>
                </div>
              )}
              {invoice.payment_method && (
                <div>
                  <p className="text-xs text-slate-500">Payment Method</p>
                  <p className="capitalize text-slate-200">{invoice.payment_method.replace('_', ' ')}</p>
                </div>
              )}
            </div>

            <div>
              <h4 className="mb-2 text-sm font-semibold text-white">Line Items</h4>
              <div className="overflow-hidden rounded-lg border border-white/10">
                <table className="w-full text-sm">
                  <tbody className="divide-y divide-white/[0.06]">
                    {invoice.line_items.map((item) => (
                      <tr key={item.id}>
                        <td className="px-3 py-2 text-slate-300">
                          {item.description}
                          <span className="ml-2 text-xs text-slate-500">
                            ({titleCase(item.item_type)})
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right text-slate-200">
                          {formatCurrency(item.amount, invoice.currency)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h4 className="mb-2 text-sm font-semibold text-white">Payment History</h4>
              {payments.length === 0 ? (
                <p className="text-sm text-slate-500">No payments yet.</p>
              ) : (
                <ul className="space-y-2">
                  {payments.map((p) => (
                    <li
                      key={p.id}
                      className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2 text-sm"
                    >
                      <span className="text-slate-300">{formatDate(p.processed_at || p.created_at)}</span>
                      <span className="text-slate-400">{formatCurrency(p.amount, p.currency)}</span>
                      <StatusBadge status={p.status} />
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <h4 className="mb-2 text-sm font-semibold text-white">Refund History</h4>
              {refunds.length === 0 ? (
                <p className="text-sm text-slate-500">No refunds issued.</p>
              ) : (
                <ul className="space-y-2">
                  {refunds.map((r) => (
                    <li
                      key={r.id}
                      className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2 text-sm"
                    >
                      <span className="text-slate-300">{formatDate(r.created_at)}</span>
                      <span className="text-slate-400">{formatCurrency(r.amount, r.currency)}</span>
                      <StatusBadge status={r.status} />
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="flex gap-3 border-t border-white/10 pt-4">
              {(invoice.status === 'open' || invoice.status === 'failed') && (
                <button onClick={() => setPayModalOpen(true)} className="btn-primary flex-1">
                  {invoice.status === 'failed' ? 'Retry Payment' : 'Pay Now'}
                </button>
              )}
              {invoice.status === 'paid' && (
                <button onClick={() => setRefundModalOpen(true)} className="btn-secondary flex-1">
                  Request Refund
                </button>
              )}
            </div>
          </div>
        )}
      </Modal>

      <ProcessPaymentModal
        open={payModalOpen}
        onClose={() => setPayModalOpen(false)}
        invoice={invoice}
        onProcessed={handleRefresh}
      />
      <RequestRefundModal
        open={refundModalOpen}
        onClose={() => setRefundModalOpen(false)}
        invoice={invoice}
        onRequested={handleRefresh}
      />
    </>
  );
}
