import { apiClient } from './apiClient';

// Wraps the backend's /invoices endpoints exactly as implemented.
export const invoiceService = {
  list: ({ customerId, subscriptionId, status, page = 1, pageSize = 50 } = {}) =>
    apiClient
      .get('/invoices', {
        params: {
          customer_id: customerId,
          subscription_id: subscriptionId,
          status,
          page,
          page_size: pageSize,
        },
      })
      .then((res) => res.data),

  get: (invoiceId) => apiClient.get(`/invoices/${invoiceId}`).then((res) => res.data),

  listPayments: (invoiceId) =>
    apiClient.get(`/invoices/${invoiceId}/payments`).then((res) => res.data),

  listRefunds: (invoiceId) =>
    apiClient.get(`/invoices/${invoiceId}/refunds`).then((res) => res.data),

  // Phase 4: downloads the invoice as a PDF (application/pdf, streamed
  // in-memory by the backend -- nothing is persisted server-side).
  // Returns the raw blob plus the filename the backend suggested via
  // Content-Disposition, so the caller doesn't have to know the naming
  // convention.
  downloadPdf: async (invoiceId) => {
    const response = await apiClient.get(`/invoices/${invoiceId}/pdf`, {
      responseType: 'blob',
    });
    const disposition = response.headers['content-disposition'] || '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : `invoice-${invoiceId}.pdf`;
    return { blob: response.data, filename };
  },

  // Phase 6C: asks the backend to email the invoice PDF to the
  // customer. Fire-and-forget from the caller's perspective -- the
  // backend queues it via Celery and returns 202 immediately; actual
  // delivery happens asynchronously.
  emailInvoice: (invoiceId) =>
    apiClient.post(`/invoices/${invoiceId}/email`).then((res) => res.data),
};
