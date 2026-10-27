import { useCallback, useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import toast from 'react-hot-toast';
import { FiSave, FiCalendar, FiRefreshCw, FiFileText, FiCreditCard, FiRotateCcw } from 'react-icons/fi';
import PageHeader from '../components/common/PageHeader';
import Spinner from '../components/common/Spinner';
import StatusBadge from '../components/common/StatusBadge';
import { useCustomer } from '../hooks/useCustomer';
import { subscriptionService } from '../services/subscriptionService';
import { planService } from '../services/planService';
import { invoiceService } from '../services/invoiceService';
import { refundService } from '../services/refundService';
import { COUNTRIES } from '../utils/constants';
import { extractErrorMessage, formatDate, formatCurrency } from '../utils/formatters';

export default function ProfilePage() {
  const { customer, updateCustomer } = useCustomer();
  const [submitting, setSubmitting] = useState(false);
  const [subscription, setSubscription] = useState(null);
  const [plan, setPlan] = useState(null);
  const [renewalDate, setRenewalDate] = useState(null);
  const [customerStats, setCustomerStats] = useState(null);

  // Real subscription/plan/renewal data -- same proven pattern already
  // used on DashboardPage, not a new data source or duplicated logic.
  const loadSubscriptionSummary = useCallback(async () => {
    if (!customer) return;
    try {
      const subsResult = await subscriptionService.list({ customerId: customer.id, pageSize: 5 });
      const latestSub = subsResult.items.find((s) => s.status !== 'cancelled') || subsResult.items[0] || null;
      if (latestSub) {
        setSubscription(latestSub);
        const [planData, cycles] = await Promise.all([
          planService.get(latestSub.plan_id),
          subscriptionService.listBillingCycles(latestSub.id),
        ]);
        setPlan(planData);
        const unbilled = cycles.find((c) => !c.is_billed);
        setRenewalDate(unbilled?.next_billing_date || cycles[0]?.next_billing_date || null);
      }

      // Customer Summary -- total counts only (not full lists), reusing
      // the exact same invoice/refund endpoints already used elsewhere;
      // paid invoices' total_amount summed client-side for "total spent"
      // since there's no dedicated backend aggregate for a single
      // customer's lifetime spend.
      const [totalInvoices, paidInvoices, refunds] = await Promise.all([
        invoiceService.list({ customerId: customer.id, pageSize: 1 }),
        invoiceService.list({ customerId: customer.id, status: 'paid', pageSize: 100 }),
        refundService.list({ customerId: customer.id, pageSize: 1 }),
      ]);
      const totalSpent = paidInvoices.items.reduce((sum, inv) => sum + Number(inv.total_amount), 0);
      const currency = paidInvoices.items[0]?.currency || 'USD';
      setCustomerStats({
        totalInvoices: totalInvoices.total,
        totalSpent,
        currency,
        totalRefunds: refunds.total,
      });
    } catch {
      // Non-critical summary data -- the profile form below still
      // works fully even if this fails to load.
    }
  }, [customer]);

  useEffect(() => {
    loadSubscriptionSummary();
  }, [loadSubscriptionSummary]);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm({
    defaultValues: {
      name: customer?.name || '',
      phoneNumber: customer?.phone_number || '',
      country: customer?.country || 'US',
      state: customer?.state || '',
      address: customer?.address || '',
    },
  });

  // react-hook-form only reads `defaultValues` once, at mount. If the
  // customer record changes while this page stays mounted (e.g. the
  // server echoes back a normalized value after a save), sync the
  // form's fields to match instead of continuing to show whatever was
  // captured at first render.
  useEffect(() => {
    if (customer) {
      reset({
        name: customer.name || '',
        phoneNumber: customer.phone_number || '',
        country: customer.country || 'US',
        state: customer.state || '',
        address: customer.address || '',
      });
    }
  }, [customer, reset]);

  const onSubmit = async (values) => {
    setSubmitting(true);
    try {
      await updateCustomer(values);
      toast.success('Profile updated!');
    } catch (err) {
      toast.error(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (!customer) return null;

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Profile" subtitle="Manage your account and billing details." />

      <div className="glass-card mb-6 flex flex-col gap-5 p-6 sm:flex-row sm:items-center">
        <div className="flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#E50914] to-[#7a0510] text-2xl font-bold text-white">
          {customer.name?.charAt(0).toUpperCase() || '?'}
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-lg font-bold text-white">{customer.name}</h2>
          <p className="truncate text-sm text-slate-400">{customer.email}</p>
        </div>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:flex sm:gap-6">
          <div>
            <p className="text-xs text-slate-500">Current Plan</p>
            <p className="font-medium text-white">{plan?.name || '—'}</p>
          </div>
          <div>
            <p className="flex items-center gap-1 text-xs text-slate-500">
              <FiCalendar size={11} /> Member Since
            </p>
            <p className="font-medium text-white">{formatDate(customer.created_at)}</p>
          </div>
          <div>
            <p className="flex items-center gap-1 text-xs text-slate-500">
              <FiRefreshCw size={11} /> Renewal Date
            </p>
            <p className="font-medium text-white">{renewalDate ? formatDate(renewalDate) : '—'}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Subscription Status</p>
            {subscription ? <StatusBadge status={subscription.status} /> : <p className="text-white">—</p>}
          </div>
        </div>
      </div>

      {customerStats && (
        <div className="glass-card mb-6 p-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Customer Summary
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="flex items-center gap-3">
              <div className="icon-badge icon-badge-info h-10 w-10">
                <FiFileText size={16} />
              </div>
              <div>
                <p className="text-xs text-slate-500">Total Invoices</p>
                <p className="font-bold text-white">{customerStats.totalInvoices}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="icon-badge icon-badge-success h-10 w-10">
                <FiCreditCard size={16} />
              </div>
              <div>
                <p className="text-xs text-slate-500">Total Spent</p>
                <p className="font-bold text-white">
                  {formatCurrency(customerStats.totalSpent, customerStats.currency)}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="icon-badge icon-badge-warning h-10 w-10">
                <FiRotateCcw size={16} />
              </div>
              <div>
                <p className="text-xs text-slate-500">Total Refunds</p>
                <p className="font-bold text-white">{customerStats.totalRefunds}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="glass-card mb-6 p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Account
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <p className="text-xs text-slate-500">Name</p>
            <p className="font-medium text-white">{customer.name}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Email</p>
            <p className="font-medium text-white">{customer.email}</p>
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-600">
          Email cannot be changed from here. Your name and billing details below can be updated
          anytime.
        </p>
      </div>

      <div className="glass-card p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Billing Information
        </h2>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="label-text">Full name</label>
            <input className="input-field" {...register('name', { required: 'Name is required' })} />
            {errors.name && <p className="mt-1 text-xs text-red-400">{errors.name.message}</p>}
          </div>

          <div>
            <label className="label-text">Phone number</label>
            <input className="input-field" placeholder="+1 555 123 4567" {...register('phoneNumber')} />
          </div>

          <div>
            <label className="label-text">Country</label>
            <select className="input-field" {...register('country', { required: true })}>
              {COUNTRIES.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-slate-500">Used for tax calculation on invoices.</p>
          </div>

          <div>
            <label className="label-text">State / Province</label>
            <input className="input-field" placeholder="California" {...register('state')} />
          </div>

          <div>
            <label className="label-text">Address</label>
            <textarea className="input-field resize-none" rows={2} {...register('address')} />
          </div>

          <button
            type="submit"
            disabled={submitting || !isDirty}
            className="btn-primary w-full sm:w-auto"
          >
            {submitting ? <Spinner size="sm" /> : (
              <>
                <FiSave /> Save Changes
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
