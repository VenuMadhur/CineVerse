import { useState } from 'react';
import toast from 'react-hot-toast';
import { useForm } from 'react-hook-form';
import { useCustomer } from '../../hooks/useCustomer';
import { useAuth } from '../../hooks/useAuth';
import { COUNTRIES } from '../../utils/constants';
import { extractErrorMessage } from '../../utils/formatters';
import Spinner from '../common/Spinner';

/**
 * Renders children as normal once a Customer record is resolved.
 * If (rare edge case) none could be found or auto-created, shows a
 * one-time setup form backed entirely by the existing POST /customers
 * endpoint -- no new backend functionality involved.
 */
export default function CustomerSetupGate({ children }) {
  const { loadingCustomer, needsSetup, provisionCustomer } = useCustomer();
  const { lastKnownEmail } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    defaultValues: { name: '', email: lastKnownEmail || '', country: 'US' },
  });

  if (loadingCustomer) {
    return (
      <div className="flex justify-center py-24">
        <Spinner size="lg" />
      </div>
    );
  }

  if (needsSetup) {
    const onSubmit = async (values) => {
      setSubmitting(true);
      try {
        await provisionCustomer(values);
        toast.success('Billing profile created!');
      } catch (err) {
        toast.error(extractErrorMessage(err));
      } finally {
        setSubmitting(false);
      }
    };

    return (
      <div className="mx-auto max-w-md">
        <div className="glass-card animate-scale-in p-6">
          <h2 className="mb-1 text-xl font-bold text-white">Complete your billing profile</h2>
          <p className="mb-6 text-sm text-slate-400">
            We couldn&apos;t find a billing record for your account yet. Just a couple of
            details to get set up.
          </p>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="label-text">Full name</label>
              <input
                className="input-field"
                {...register('name', { required: 'Name is required' })}
              />
              {errors.name && <p className="mt-1 text-xs text-red-400">{errors.name.message}</p>}
            </div>
            <div>
              <label className="label-text">Email</label>
              <input
                type="email"
                className="input-field"
                {...register('email', { required: 'Email is required' })}
              />
              {errors.email && (
                <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>
              )}
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
            </div>
            <button type="submit" disabled={submitting} className="btn-primary w-full">
              {submitting ? <Spinner size="sm" /> : 'Continue to CineVerse'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return children;
}
