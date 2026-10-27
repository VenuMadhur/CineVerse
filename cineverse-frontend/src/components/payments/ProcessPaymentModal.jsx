import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { FiCheckCircle, FiXCircle } from 'react-icons/fi';
import Modal from '../common/Modal';
import Spinner from '../common/Spinner';
import { paymentService } from '../../services/paymentService';
import { formatCurrency, extractErrorMessage } from '../../utils/formatters';

export default function ProcessPaymentModal({ open, onClose, invoice, onProcessed }) {
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  // Reset any leftover result/submitting state from a previous invoice
  // whenever this modal is (re)opened, so switching to a different
  // invoice never shows a stale success/failure banner.
  useEffect(() => {
    if (open) {
      setResult(null);
      setSubmitting(false);
    }
  }, [open, invoice?.id]);

  const handlePay = async () => {
    setSubmitting(true);
    setResult(null);
    try {
      const response = await paymentService.process({ invoiceId: invoice.id });
      setResult(response);
      if (response.status === 'succeeded') {
        toast.success('Payment successful!');
      } else {
        toast.error('Payment was declined by the gateway.');
      }
      onProcessed?.();
    } catch (err) {
      toast.error(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (!invoice) return null;

  const succeeded = result?.status === 'succeeded';
  const failed = result && !succeeded;

  return (
    <Modal open={open} onClose={onClose} title="Process Payment">
      <div className="space-y-4">
        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4 text-sm">
          <div className="flex justify-between py-1">
            <span className="text-slate-400">Invoice</span>
            <span className="text-white">{invoice.invoice_number}</span>
          </div>
          <div className="flex justify-between py-1">
            <span className="text-slate-400">Amount Due</span>
            <span className="font-bold text-white">
              {formatCurrency(invoice.total_amount, invoice.currency)}
            </span>
          </div>
        </div>

        {result && (
          <div
            className={`flex items-start gap-3 rounded-lg px-4 py-3 text-sm ${
              succeeded ? 'bg-emerald-500/10 text-emerald-300' : 'bg-red-500/10 text-red-300'
            }`}
          >
            {succeeded ? (
              <FiCheckCircle className="mt-0.5 flex-shrink-0" size={18} />
            ) : (
              <FiXCircle className="mt-0.5 flex-shrink-0" size={18} />
            )}
            <div>
              <p className="font-semibold">{result.message}</p>
              <p className="mt-1 text-xs opacity-80">Transaction: {result.transaction_id}</p>
            </div>
          </div>
        )}

        <p className="text-xs text-slate-500">
          Payments are processed through CineVerse&apos;s mock payment gateway for demonstration
          purposes.
        </p>

        <div className="flex gap-3 pt-1">
          <button onClick={onClose} className="btn-secondary flex-1">
            {succeeded ? 'Done' : 'Close'}
          </button>
          {!succeeded && (
            <button onClick={handlePay} disabled={submitting} className="btn-primary flex-1">
              {submitting ? <Spinner size="sm" /> : failed ? 'Try Again' : 'Pay Now'}
            </button>
          )}
        </div>
      </div>
    </Modal>
  );
}
