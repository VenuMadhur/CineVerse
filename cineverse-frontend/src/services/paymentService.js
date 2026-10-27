import { apiClient } from './apiClient';

// Wraps the backend's /payments endpoints exactly as implemented.
// Status filter added to list() to support the admin payments page
// filter chips -- the backend PaymentRepository already had status
// support; the API layer now exposes it as a query param.
export const paymentService = {
  process: ({ invoiceId, amount }) =>
    apiClient
      .post('/payments/process', { invoice_id: invoiceId, amount: amount || undefined })
      .then((res) => res.data),

  list: ({ invoiceId, customerId, status, page = 1, pageSize = 50 } = {}) =>
    apiClient
      .get('/payments', {
        params: {
          invoice_id: invoiceId,
          customer_id: customerId,
          status: status || undefined,
          page,
          page_size: pageSize,
        },
      })
      .then((res) => res.data),

  get: (paymentId) => apiClient.get(`/payments/${paymentId}`).then((res) => res.data),
};
