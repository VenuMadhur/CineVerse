import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { FiArrowRight } from 'react-icons/fi';
import Modal from '../common/Modal';
import Spinner from '../common/Spinner';
import { subscriptionService } from '../../services/subscriptionService';
import { formatCurrency, extractErrorMessage } from '../../utils/formatters';

/**
 * All proration math is calculated by the backend
 * (POST /subscriptions/{id}/proration-preview) -- this component only
 * renders whatever the backend returns and, on confirmation, calls the
 * existing change-plan endpoint. No proration logic lives here.
 */
export default function ProrationModal({ open, onClose, subscription, currentPlan, targetPlan, onChanged }) {
  const [preview, setPreview] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    if (!open || !subscription || !targetPlan) return;
    let cancelled = false;

    setLoadingPreview(true);
    setError(null);
    setPreview(null);

    subscriptionService
      .previewProration(subscription.id, targetPlan.id)
      .then((result) => {
        if (!cancelled) setPreview(result);
      })
      .catch((err) => {
        if (!cancelled) setError(extractErrorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoadingPreview(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, subscription, targetPlan, retryCount]);

  if (!targetPlan) return null;

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      await subscriptionService.changePlan(subscription.id, targetPlan.id);
      toast.success(`Switched to ${targetPlan.name}!`);
      onChanged?.();
      onClose();
    } catch (err) {
      toast.error(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const netAmount = preview ? parseFloat(preview.net_amount) : 0;
  const isCredit = netAmount < 0;

  return (
    <Modal open={open} onClose={onClose} title="Confirm Plan Change">
      <div className="mb-5 flex items-center justify-center gap-3 text-center">
        <div className="flex-1">
          <p className="text-xs uppercase tracking-wide text-slate-500">Current Plan</p>
          <p className="font-bold text-white">{currentPlan?.name}</p>
        </div>
        <FiArrowRight className="text-slate-500" />
        <div className="flex-1">
          <p className="text-xs uppercase tracking-wide text-slate-500">New Plan</p>
          <p className="font-bold text-[#E50914]">{targetPlan.name}</p>
        </div>
      </div>

      {loadingPreview && (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      )}

      {error && !loadingPreview && (
        <div className="space-y-3">
          <p className="rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</p>
          <button onClick={() => setRetryCount((c) => c + 1)} className="btn-secondary w-full">
            Try Again
          </button>
        </div>
      )}

      {preview && !loadingPreview && !error && (
        <div className="space-y-3">
          {!preview.applicable ? (
            <p className="rounded-lg bg-white/[0.04] px-4 py-3 text-sm text-slate-400">
              {preview.reason || 'No proration applies to this change — your plan will simply switch.'}
            </p>
          ) : (
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4 text-sm">
              <div className="flex justify-between py-1.5 text-slate-400">
                <span>Days remaining in cycle</span>
                <span className="text-slate-200">{preview.remaining_days} / {preview.cycle_total_days}</span>
              </div>
              <div className="flex justify-between py-1.5 text-slate-400">
                <span>Unused credit (current plan)</span>
                <span className="text-emerald-400">
                  −{formatCurrency(preview.old_plan_unused_credit, targetPlan.currency)}
                </span>
              </div>
              <div className="flex justify-between py-1.5 text-slate-400">
                <span>New plan (remaining period)</span>
                <span className="text-slate-200">
                  {formatCurrency(preview.new_plan_remaining_cost, targetPlan.currency)}
                </span>
              </div>
              <div className="mt-2 flex justify-between border-t border-white/10 pt-2 font-bold">
                <span className="text-white">
                  {isCredit ? 'Credit issued' : 'Additional charge today'}
                </span>
                <span className={isCredit ? 'text-emerald-400' : 'text-white'}>
                  {formatCurrency(Math.abs(netAmount), targetPlan.currency)}
                </span>
              </div>
              {isCredit && (
                <p className="mt-2 text-xs text-slate-500">
                  Since this is a downgrade credit, no charge is made today. This credit is applied
                  only to today's plan change and isn't banked as an account balance for future
                  invoices.
                </p>
              )}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button onClick={onClose} className="btn-secondary flex-1">
              Cancel
            </button>
            <button onClick={handleConfirm} disabled={submitting} className="btn-primary flex-1">
              {submitting ? <Spinner size="sm" /> : 'Confirm Change'}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
