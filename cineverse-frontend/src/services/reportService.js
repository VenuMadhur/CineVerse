import { apiClient } from './apiClient';

// Wraps the backend's /reports endpoints exactly as implemented
// (Phase 5). Every endpoint is admin-only server-side
// (get_current_superuser); the frontend additionally never renders a
// path to reach them for non-admins (see AdminRoute).
const REPORT_PATHS = {
  revenue: '/reports/revenue',
  customers: '/reports/customers',
  subscriptions: '/reports/subscriptions',
  payments: '/reports/payments',
  refunds: '/reports/refunds',
  'customer-insights': '/reports/customer-insights',
  operational: '/reports/operational',
};

// Only these two report types support date-range filtering on the
// backend (matching exactly what Phase 2's analytics already
// supported) -- not invented here.
export const REPORT_TYPES_WITH_DATE_RANGE = new Set(['revenue', 'payments']);

// Module 3, Phase 3c: the 4 Customer Insights views, each backed by
// the same GET /reports/customer-insights?dimension= endpoint.
export const CUSTOMER_INSIGHT_DIMENSIONS = [
  { value: 'top_paying', label: 'Top Paying Customers' },
  { value: 'near_renewal', label: 'Customers Near Renewal' },
  { value: 'failed_payments', label: 'Customers with Failed Payments' },
  { value: 'past_due', label: 'Customers in Past Due' },
];

// Module 3, Phase 3d: the 4 Operational Report views, each backed by
// GET /reports/operational?dimension=.
export const OPERATIONAL_REPORT_DIMENSIONS = [
  { value: 'retry_queue', label: 'Retry Queue' },
  { value: 'retry_success', label: 'Retry Success' },
  { value: 'retry_failure', label: 'Retry Failure' },
  { value: 'cancelled_due_to_failure', label: 'Cancelled Due to Payment Failure' },
];

export const reportService = {
  /**
   * Downloads a report as a blob, returning both the blob and the
   * filename suggested by the backend's Content-Disposition header
   * (mirrors invoiceService.downloadPdf's pattern from Phase 4).
   */
  download: async (reportType, { format = 'csv', dateFrom, dateTo, dimension } = {}) => {
    const path = REPORT_PATHS[reportType];
    if (!path) throw new Error(`Unknown report type: ${reportType}`);

    const params = { format };
    if (REPORT_TYPES_WITH_DATE_RANGE.has(reportType)) {
      params.date_from = dateFrom || undefined;
      params.date_to = dateTo || undefined;
    }
    if (reportType === 'customer-insights' || reportType === 'operational') {
      params.dimension = dimension;
    }

    const response = await apiClient.get(path, { params, responseType: 'blob' });
    const disposition = response.headers['content-disposition'] || '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : `${reportType}-report.${format}`;
    return { blob: response.data, filename };
  },
};
