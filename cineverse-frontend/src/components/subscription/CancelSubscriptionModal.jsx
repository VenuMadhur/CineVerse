import { useState } from 'react';
import toast from 'react-hot-toast';
import Modal from '../common/Modal';
import Spinner from '../common/Spinner';
import { subscriptionService } from '../../services/subscriptionService';
import { extractErrorMessage } from '../../utils/formatters';

export default function CancelSubscriptionModal({ open, onClose, subscription, onCancelled }) {
  const [cancellationType, setCancellationType] = useState('end_of_cycle');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      await subscriptionService.cancel(subscription.id, { cancellationType, reason });
      toast.success(
        cancellationType === 'immediate'
          ? 'Subscription cancelled immediately.'
          : 'Subscription will cancel at the end of your billing cycle.'
      );
      onCancelled?.();
      onClose();
    } catch (err) {
      toast.error(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Cancel Subscription">
      <div className="space-y-4">
        <div className="space-y-2">
          <label
            className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
              cancellationType === 'end_of_cycle'
                ? 'border-[#E50914]/50 bg-[#E50914]/[0.06]'
                : 'border-white/10 hover:bg-white/[0.03]'
            }`}
          >
            <input
              type="radio"
              className="mt-1"
              checked={cancellationType === 'end_of_cycle'}
              onChange={() => setCancellationType('end_of_cycle')}
            />
            <div>
              <p className="font-semibold text-white">Cancel at end of billing cycle</p>
              <p className="text-xs text-slate-400">
                Keep access until your current cycle ends, then stop renewing.
              </p>
            </div>
          </label>
          <label
            className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
              cancellationType === 'immediate'
                ? 'border-[#E50914]/50 bg-[#E50914]/[0.06]'
                : 'border-white/10 hover:bg-white/[0.03]'
            }`}
          >
            <input
              type="radio"
              className="mt-1"
              checked={cancellationType === 'immediate'}
              onChange={() => setCancellationType('immediate')}
            />
            <div>
              <p className="font-semibold text-white">Cancel immediately</p>
              <p className="text-xs text-slate-400">
                Access ends now. If you&apos;ve already paid this cycle, the unused portion is
                automatically refunded.
              </p>
            </div>
          </label>
        </div>

        <div>
          <label className="label-text">Reason (optional)</label>
          <textarea
            className="input-field resize-none"
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Tell us why you're leaving..."
          />
        </div>

        <p className="text-xs text-slate-500">
          This can&apos;t be undone from here — to come back, you&apos;ll need to start a new
          subscription.
        </p>

        <div className="flex gap-3 pt-1">
          <button onClick={onClose} className="btn-secondary flex-1">
            Keep Subscription
          </button>
          <button
            onClick={handleConfirm}
            disabled={submitting}
            // Reuses the exact danger-button styling ConfirmDialog already
            // defines (variant="danger") for destructive confirmations --
            // this modal can't use ConfirmDialog directly since it needs
            // the extra radio/textarea fields above, but the confirm
            // button should still look and read as destructive, not like
            // a routine btn-primary action (e.g. "Activate Now").
            className="focus-ring inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-red-600 px-5 py-2.5 font-semibold text-white transition-all duration-200 hover:bg-red-500 active:scale-95 disabled:opacity-50 disabled:pointer-events-none"
          >
            {submitting ? <Spinner size="sm" /> : 'Confirm Cancellation'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
