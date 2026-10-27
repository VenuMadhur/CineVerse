import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import Modal from '../common/Modal';
import Spinner from '../common/Spinner';
import { refundService } from '../../services/refundService';
import { formatCurrency, extractErrorMessage } from '../../utils/formatters';

export default function RequestRefundModal({ open, onClose, invoice, onRequested }) {
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Reset any leftover amount/reason from a previous invoice whenever
  // this modal is (re)opened, so switching to a different invoice
  // never shows stale typed-in values.
  useEffect(() => {
    if (open) {
      setAmount('');
      setReason('');
      setSubmitting(false);
    }
  }, [open, invoice?.id]);

  if (!invoice) return null;

  const maxAmount = parseFloat(invoice.total_amount);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!reason.trim()) {
      toast.error('Please provide a reason for the refund.');
      return;
    }
    setSubmitting(true);
    try {
      await refundService.create({
        invoiceId: invoice.id,
        amount: amount ? parseFloat(amount) : undefined,
        reason,
      });
      toast.success('Refund issued successfully.');
      onRequested?.();
      onClose();
    } catch (err) {
      toast.error(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Request Refund">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4 text-sm">
          <div className="flex justify-between py-1">
            <span className="text-slate-400">Invoice</span>
            <span className="text-white">{invoice.invoice_number}</span>
          </div>
          <div className="flex justify-between py-1">
            <span className="text-slate-400">Paid Amount</span>
            <span className="font-bold text-white">
              {formatCurrency(invoice.total_amount, invoice.currency)}
            </span>
          </div>
        </div>

        <div>
          <label className="label-text">Refund amount (optional — leave blank for full refund)</label>
          <input
            type="number"
            step="0.01"
            min="0"
            max={maxAmount}
            className="input-field"
            placeholder={`Up to ${formatCurrency(maxAmount, invoice.currency)}`}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </div>

        <div>
          <label className="label-text">Reason</label>
          <textarea
            className="input-field resize-none"
            rows={3}
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why are you requesting this refund?"
          />
        </div>

        <div className="flex gap-3 pt-1">
          <button type="button" onClick={onClose} className="btn-secondary flex-1">
            Cancel
          </button>
          <button type="submit" disabled={submitting} className="btn-primary flex-1">
            {submitting ? <Spinner size="sm" /> : 'Submit Refund'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
