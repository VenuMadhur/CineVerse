import { apiClient } from './apiClient';

// Wraps the backend's /analytics endpoints exactly as implemented
// (Phase 2, extended in Module 3). Every endpoint is admin-only
// server-side (get_current_superuser) -- calling these as a non-admin
// will correctly fail with a 403 from the backend; the frontend
// additionally never renders a path to reach them for non-admins
// (see AdminRoute).
//
// getKpis() and getInvoiceAnalytics() added to support AdminAnalyticsPage --
// the backend endpoints /analytics/kpis and /analytics/invoices already
// existed; only the frontend service wrapper was missing.
export const analyticsService = {
  getDashboard: () => apiClient.get('/analytics/dashboard').then((res) => res.data),

  getRevenue: ({ dateFrom, dateTo } = {}) =>
    apiClient
      .get('/analytics/revenue', { params: { date_from: dateFrom, date_to: dateTo } })
      .then((res) => res.data),

  getSubscriptions: () => apiClient.get('/analytics/subscriptions').then((res) => res.data),

  getPayments: ({ dateFrom, dateTo } = {}) =>
    apiClient
      .get('/analytics/payments', { params: { date_from: dateFrom, date_to: dateTo } })
      .then((res) => res.data),

  getRefunds: () => apiClient.get('/analytics/refunds').then((res) => res.data),

  getKpis: ({ dateFrom, dateTo } = {}) =>
    apiClient
      .get('/analytics/kpis', { params: { date_from: dateFrom, date_to: dateTo } })
      .then((res) => res.data),

  getInvoiceAnalytics: () => apiClient.get('/analytics/invoices').then((res) => res.data),

  // Exact database-level active-subscriber count per plan (added to
  // replace the previous client-side, capped-at-100 aggregation).
  getSubscribersByPlan: () =>
    apiClient.get('/analytics/subscribers-by-plan').then((res) => res.data),

  // Current MRR composition by plan -- a snapshot, not a historical trend.
  getMrrByPlan: () => apiClient.get('/analytics/mrr-by-plan').then((res) => res.data),

  // Real monthly refund count + amount, completed refunds only.
  getRefundTrend: ({ dateFrom, dateTo } = {}) =>
    apiClient
      .get('/analytics/refunds/trend', { params: { date_from: dateFrom, date_to: dateTo } })
      .then((res) => res.data),

  // Real monthly new-customer registration count.
  getCustomerTrend: ({ dateFrom, dateTo } = {}) =>
    apiClient
      .get('/analytics/customers/trend', { params: { date_from: dateFrom, date_to: dateTo } })
      .then((res) => res.data),
};
