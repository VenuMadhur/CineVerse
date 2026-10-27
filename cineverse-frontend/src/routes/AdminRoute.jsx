import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { FullPageSpinner } from '../components/common/Spinner';

/**
 * Gates admin-only routes. Mirrors ProtectedRoute's auth check (not
 * logged in -> /login) and additionally requires isSuperuser (loaded
 * via GET /auth/me in AuthContext) -- a logged-in but non-admin user
 * is redirected to their own dashboard rather than shown a dedicated
 * "forbidden" page, since building that page is out of scope for this
 * phase (no Admin Dashboard exists yet for this route to protect).
 *
 * Usage (once an admin page exists to nest under it):
 *   <Route element={<AdminRoute />}>
 *     <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
 *   </Route>
 */
export default function AdminRoute() {
  const { isAuthenticated, initializing, isSuperuser, roleLoading } = useAuth();
  const location = useLocation();

  if (initializing || roleLoading) return <FullPageSpinner />;

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!isSuperuser) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
