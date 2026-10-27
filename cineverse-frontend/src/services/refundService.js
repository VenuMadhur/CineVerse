import { apiClient } from './apiClient';

// Wraps the backend's /refunds endpoints exactly as implemented.
export const refundService = {
  create: ({ invoiceId, amount, reason }) =>
    apiClient
      .post('/refunds', { invoice_id: invoiceId, amount: amount || undefined, reason })
      .then((res) => res.data),

  list: ({ customerId, invoiceId, page = 1, pageSize = 50 } = {}) =>
    apiClient
      .get('/refunds', {
        params: { customer_id: customerId, invoice_id: invoiceId, page, page_size: pageSize },
      })
      .then((res) => res.data),

  get: (refundId) => apiClient.get(`/refunds/${refundId}`).then((res) => res.data),
};
