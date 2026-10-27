import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { motion } from 'framer-motion';
import { FiLock, FiMail, FiUser, FiGlobe } from 'react-icons/fi';
import { useAuth } from '../hooks/useAuth';

import { COUNTRIES } from '../utils/constants';
import { extractErrorMessage } from '../utils/formatters';
import Spinner from '../components/common/Spinner';

export default function RegisterPage() {
  const { register: registerUser } = useAuth();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm({ defaultValues: { country: 'US' } });

  const password = watch('password');

  const onSubmit = async ({ fullName, email, password, country }) => {
    setSubmitting(true);
    try {
      // 1. Create the auth account and linked billing Customer atomically.
      // 2. Log in (existing /auth endpoints).
      await registerUser({ email, fullName, password, country });
      toast.success('Account created! Welcome to CineVerse.');
      navigate('/dashboard', { replace: true });
    } catch (err) {
      toast.error(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4 pt-24 pb-12">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="glass-card w-full max-w-md bg-black/40 p-8"
      >
        <h1 className="mb-1 text-2xl font-bold text-white">Create Your Account</h1>
        <p className="mb-6 text-sm text-slate-400">Start streaming in minutes.</p>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="label-text">Full name</label>
            <div className="relative">
              <FiUser className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                className="input-field pl-10"
                placeholder="Jamie Rivera"
                {...register('fullName', { required: 'Name is required' })}
              />
            </div>
            {errors.fullName && (
              <p className="mt-1 text-xs text-red-400">{errors.fullName.message}</p>
            )}
          </div>

          <div>
            <label className="label-text">Email</label>
            <div className="relative">
              <FiMail className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="email"
                className="input-field pl-10"
                placeholder="you@example.com"
                {...register('email', { required: 'Email is required' })}
              />
            </div>
            {errors.email && <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>}
          </div>

          <div>
            <label className="label-text">Country</label>
            <div className="relative">
              <FiGlobe className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <select className="input-field pl-10" {...register('country', { required: true })}>
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <p className="mt-1 text-xs text-slate-500">Used for billing &amp; tax calculation.</p>
          </div>

          <div>
            <label className="label-text">Password</label>
            <div className="relative">
              <FiLock className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="password"
                className="input-field pl-10"
                placeholder="At least 8 characters"
                {...register('password', {
                  required: 'Password is required',
                  minLength: { value: 8, message: 'Minimum 8 characters' },
                })}
              />
            </div>
            {errors.password && (
              <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>
            )}
          </div>

          <div>
            <label className="label-text">Confirm password</label>
            <div className="relative">
              <FiLock className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="password"
                className="input-field pl-10"
                placeholder="Re-enter your password"
                {...register('confirmPassword', {
                  required: 'Please confirm your password',
                  validate: (value) => value === password || 'Passwords do not match',
                })}
              />
            </div>
            {errors.confirmPassword && (
              <p className="mt-1 text-xs text-red-400">{errors.confirmPassword.message}</p>
            )}
          </div>

          <button type="submit" disabled={submitting} className="btn-primary w-full py-3">
            {submitting ? <Spinner size="sm" /> : 'Create Account'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          Already have an account?{' '}
          <Link to="/login" className="font-semibold text-white hover:text-[#E50914]">
            Sign in
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
