import { lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import PublicLayout from '../layouts/PublicLayout';
import AppLayout from '../layouts/AppLayout';
import AdminLayout from '../layouts/AdminLayout';
import ProtectedRoute from './ProtectedRoute';
import AdminRoute from './AdminRoute';
import { FullPageSpinner } from '../components/common/Spinner';

import LandingPage from '../pages/LandingPage';
import LoginPage from '../pages/LoginPage';
import RegisterPage from '../pages/RegisterPage';
import NotFoundPage from '../pages/NotFoundPage';

// Everything reached only after logging in is lazy-loaded: these pages
// (especially the admin ones) are the bulk of the JS bundle size, and
// most visitors -- anyone just viewing the marketing landing page --
// never need them at all. Landing/Login/Register/NotFound stay eager
// since they're small and on the very first paint's critical path.
const DashboardPage = lazy(() => import('../pages/DashboardPage'));
const PlansPage = lazy(() => import('../pages/PlansPage'));
const MoviesPage = lazy(() => import('../pages/MoviesPage'));
const SeriesPage = lazy(() => import('../pages/SeriesPage'));
const TitleDetailPage = lazy(() => import('../pages/TitleDetailPage'));
const PreviewPage = lazy(() => import('../pages/PreviewPage'));
const WatchNowPage = lazy(() => import('../pages/WatchNowPage'));
const SubscriptionsPage = lazy(() => import('../pages/SubscriptionsPage'));
const InvoicesPage = lazy(() => import('../pages/InvoicesPage'));
const PaymentsPage = lazy(() => import('../pages/PaymentsPage'));
const RefundsPage = lazy(() => import('../pages/RefundsPage'));
const ProfilePage = lazy(() => import('../pages/ProfilePage'));
const ActivityPage = lazy(() => import('../pages/ActivityPage'));

const AdminDashboardPage = lazy(() => import('../pages/admin/AdminDashboardPage'));
const AdminCustomersPage = lazy(() => import('../pages/admin/AdminCustomersPage'));
const AdminCustomerDetailPage = lazy(() => import('../pages/admin/AdminCustomerDetailPage'));
const AdminPlansPage = lazy(() => import('../pages/admin/AdminPlansPage'));
const AdminSubscriptionsPage = lazy(() => import('../pages/admin/AdminSubscriptionsPage'));
const AdminInvoicesPage = lazy(() => import('../pages/admin/AdminInvoicesPage'));
const AdminPaymentsPage = lazy(() => import('../pages/admin/AdminPaymentsPage'));
const AdminRefundsPage = lazy(() => import('../pages/admin/AdminRefundsPage'));
const AdminReportsPage = lazy(() => import('../pages/admin/AdminReportsPage'));
const AdminAnalyticsPage = lazy(() => import('../pages/admin/AdminAnalyticsPage'));
const AdminAuditLogPage = lazy(() => import('../pages/admin/AdminAuditLogPage'));
const AdminRetryPage = lazy(() => import('../pages/admin/AdminRetryPage'));

export default function AppRoutes() {
  return (
    <Routes>
      {/* Public: landing + auth pages share the Navbar/Footer chrome */}
      <Route element={<PublicLayout />}>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      {/* Protected: sidebar + topbar app shell, requires a valid session */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route
            path="/dashboard"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <DashboardPage />
              </Suspense>
            }
          />
          <Route
            path="/plans"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <PlansPage />
              </Suspense>
            }
          />
          <Route
            path="/movies"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <MoviesPage />
              </Suspense>
            }
          />
          <Route
            path="/movies/:id"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <TitleDetailPage />
              </Suspense>
            }
          />
          <Route
            path="/series"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <SeriesPage />
              </Suspense>
            }
          />
          <Route
            path="/series/:id"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <TitleDetailPage />
              </Suspense>
            }
          />
          <Route
            path="/watch/:id"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <WatchNowPage />
              </Suspense>
            }
          />
          <Route
            path="/preview/:id"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <PreviewPage />
              </Suspense>
            }
          />
          <Route
            path="/subscriptions"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <SubscriptionsPage />
              </Suspense>
            }
          />
          <Route
            path="/invoices"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <InvoicesPage />
              </Suspense>
            }
          />
          <Route
            path="/payments"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <PaymentsPage />
              </Suspense>
            }
          />
          <Route
            path="/refunds"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <RefundsPage />
              </Suspense>
            }
          />
          <Route
            path="/profile"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <ProfilePage />
              </Suspense>
            }
          />
          <Route
            path="/activity"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <ActivityPage />
              </Suspense>
            }
          />
        </Route>
      </Route>

      {/* Admin: separate app shell, requires isSuperuser (Phase 1C's
          AdminRoute) -- a logged-in non-admin is redirected to
          /dashboard, never shown any admin content. */}
      <Route element={<AdminRoute />}>
        <Route element={<AdminLayout />}>
          <Route
            path="/admin/dashboard"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <AdminDashboardPage />
              </Suspense>
            }
          />
          <Route
            path="/admin/customers"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <AdminCustomersPage />
              </Suspense>
            }
          />
          <Route
            path="/admin/customers/:customerId"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <AdminCustomerDetailPage />
              </Suspense>
            }
          />
          <Route
            path="/admin/plans"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <AdminPlansPage />
              </Suspense>
            }
          />
          <Route
            path="/admin/subscriptions"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <AdminSubscriptionsPage />
              </Suspense>
            }
          />
          <Route
            path="/admin/invoices"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <AdminInvoicesPage />
              </Suspense>
            }
          />
          <Route
            path="/admin/payments"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <AdminPaymentsPage />
              </Suspense>
            }
          />
          <Route
            path="/admin/refunds"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <AdminRefundsPage />
              </Suspense>
            }
          />
          <Route
            path="/admin/reports"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <AdminReportsPage />
              </Suspense>
            }
          />
          <Route
            path="/admin/analytics"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <AdminAnalyticsPage />
              </Suspense>
            }
          />
          <Route
            path="/admin/audit-log"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <AdminAuditLogPage />
              </Suspense>
            }
          />
          <Route
            path="/admin/retry-config"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <AdminRetryPage />
              </Suspense>
            }
          />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
