import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import Modal from '../common/Modal';
import Spinner from '../common/Spinner';
import { planService } from '../../services/planService';
import { extractErrorMessage } from '../../utils/formatters';

const BILLING_INTERVALS = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'annual', label: 'Annual' },
];

/**
 * Create or edit a Plan. Reuses planService.create/update -- the same
 * POST/PATCH /plans endpoints the backend has had since Module 1,
 * admin-only since Phase 1C. `plan` is null for create, or an
 * existing plan object for edit.
 *
 * Fix: added a `currency` field (create only) so admins can create
 * plans in any currency. The label was also corrected from "Price (USD)"
 * to just "Price" since the actual currency is now shown alongside.
 * Currency cannot be changed after creation (immutable on the backend
 * model -- the Plan.currency column has no update path in PlanUpdate).
 */
export default function PlanFormModal({ open, onClose, plan, onSaved }) {
  const isEdit = Boolean(plan);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [price, setPrice] = useState('');
  const [currency, setCurrency] = useState('USD');
  const [billingInterval, setBillingInterval] = useState('monthly');
  const [trialDays, setTrialDays] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setName(plan?.name || '');
      setDescription(plan?.description || '');
      setPrice(plan?.price ?? '');
      setCurrency(plan?.currency || 'USD');
      setBillingInterval(plan?.billing_interval || 'monthly');
      setTrialDays(plan?.trial_period_days ?? 0);
    }
  }, [open, plan]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const upperCurrency = currency.trim().toUpperCase();
    if (upperCurrency.length !== 3) {
      toast.error('Currency must be a 3-letter ISO code (e.g. USD, EUR, INR).');
      return;
    }
    setSubmitting(true);
    try {
      if (isEdit) {
        await planService.update(plan.id, {
          description,
          price: parseFloat(price),
          billingInterval,
          trialPeriodDays: parseInt(trialDays, 10),
        });
        toast.success('Plan updated.');
      } else {
        await planService.create({
          name,
          description,
          price: parseFloat(price),
          currency: upperCurrency,
          billingInterval,
          trialPeriodDays: parseInt(trialDays, 10),
        });
        toast.success('Plan created.');
      }
      onSaved?.();
      onClose();
    } catch (err) {
      toast.error(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? 'Edit Plan' : 'Create Plan'}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="label-text">Plan name</label>
          <input
            className="input-field"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={isEdit}
            required
          />
          {isEdit && (
            <p className="mt-1 text-xs text-slate-500">Name can&apos;t be changed after creation.</p>
          )}
        </div>

        <div>
          <label className="label-text">Description</label>
          <textarea
            className="input-field resize-none"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label-text">Price</label>
            <input
              type="number"
              step="0.01"
              min="0"
              className="input-field"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label-text">Currency</label>
            <input
              type="text"
              maxLength={3}
              className="input-field"
              placeholder="USD"
              value={currency}
              onChange={(e) => setCurrency(e.target.value.toUpperCase())}
              disabled={isEdit}
              style={{ textTransform: 'uppercase' }}
            />
            {isEdit ? (
              <p className="mt-1 text-xs text-slate-500">Currency can&apos;t be changed after creation.</p>
            ) : (
              <p className="mt-1 text-xs text-slate-500">3-letter ISO code (USD, EUR, INR…)</p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label-text">Trial days</label>
            <input
              type="number"
              min="0"
              className="input-field"
              value={trialDays}
              onChange={(e) => setTrialDays(e.target.value)}
            />
          </div>
          <div>
            <label className="label-text">Billing interval</label>
            <select
              className="input-field"
              value={billingInterval}
              onChange={(e) => setBillingInterval(e.target.value)}
            >
              {BILLING_INTERVALS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex gap-3 pt-1">
          <button type="button" onClick={onClose} className="btn-secondary flex-1">
            Cancel
          </button>
          <button type="submit" disabled={submitting} className="btn-primary flex-1">
            {submitting ? <Spinner size="sm" /> : isEdit ? 'Save Changes' : 'Create Plan'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
