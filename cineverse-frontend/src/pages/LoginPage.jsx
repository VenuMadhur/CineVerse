import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { motion } from 'framer-motion';
import { FiLock, FiMail } from 'react-icons/fi';
import { useAuth } from '../hooks/useAuth';
import { authService } from '../services/authService';
import { extractErrorMessage } from '../utils/formatters';
import Spinner from '../components/common/Spinner';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [submitting, setSubmitting] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm();

  const onSubmit = async ({ email, password }) => {
    setSubmitting(true);
    try {
      await login(email, password);
      toast.success('Welcome back!');
      // Route admins straight to the Admin Dashboard. Checked directly
      // via getMe() here (not AuthContext's isSuperuser) since that's
      // updated by a separate effect that may not have resolved yet at
      // this exact moment -- calling it directly avoids any race.
      //
      // Issue 3 fix: this check previously only ran when
      // location.state?.from was absent, so an admin who wasn't yet
      // logged in and tried to visit a *customer* route directly (a
      // bookmark, a typed URL) would get redirected to /login with
      // that customer route as `from`, then land right back on it
      // after logging in -- ProtectedRoute doesn't block admins from
      // customer routes (see ProtectedRoute.jsx), so they'd hit
      // CustomerSetupGate and see "Complete your billing profile"
      // instead of ever reaching the admin dashboard. Now the
      // superuser check always runs; an admin's `from` is only
      // honored if it's actually an admin route (preserves
      // deep-linking back to a specific admin page after a session
      // expiry), otherwise they always go to /admin/dashboard.
      const fromPath = location.state?.from?.pathname;
      let destination = fromPath || '/dashboard';
      try {
        const me = await authService.getMe();
        if (me.is_superuser) {
          destination = fromPath?.startsWith('/admin') ? fromPath : '/admin/dashboard';
        }
      } catch {
        // Fall through to the customer destination already set above.
      }
      navigate(destination, { replace: true });
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
        <h1 className="mb-1 text-2xl font-bold text-white">Sign In</h1>
        <p className="mb-6 text-sm text-slate-400">Welcome back to CineVerse.</p>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
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
            <label className="label-text">Password</label>
            <div className="relative">
              <FiLock className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="password"
                className="input-field pl-10"
                placeholder="••••••••"
                {...register('password', { required: 'Password is required' })}
              />
            </div>
            {errors.password && (
              <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>
            )}
          </div>

          <button type="submit" disabled={submitting} className="btn-primary w-full py-3">
            {submitting ? <Spinner size="sm" /> : 'Sign In'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          New to CineVerse?{' '}
          <Link to="/register" className="font-semibold text-white hover:text-[#E50914]">
            Create an account
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
