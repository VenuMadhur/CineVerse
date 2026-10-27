import { apiClient } from './apiClient';

// Wraps the backend's /customers endpoints exactly as implemented.
export const customerService = {
  create: ({ name, email, country, phoneNumber, address, state }) =>
    apiClient
      .post('/customers', {
        name,
        email,
        country,
        phone_number: phoneNumber || undefined,
        address: address || undefined,
        state: state || undefined,
      })
      .then((res) => res.data),

  get: (customerId) => apiClient.get(`/customers/${customerId}`).then((res) => res.data),

  // The customer record linked to the currently authenticated user
  // (Phase 1B: backed by Customer.user_id, set server-side on
  // creation). Throws a 404 (via the normal axios error path) if the
  // authenticated user has no linked customer yet.
  getMe: () => apiClient.get('/customers/me').then((res) => res.data),

  update: (customerId, { name, phoneNumber, country, address, state }) =>
    apiClient
      .patch(`/customers/${customerId}`, {
        name: name || undefined,
        phone_number: phoneNumber || undefined,
        country: country || undefined,
        address: address || undefined,
        state: state || undefined,
      })
      .then((res) => res.data),

  list: ({ page = 1, pageSize = 100, search } = {}) =>
    apiClient
      .get('/customers', { params: { page, page_size: pageSize, search: search || undefined } })
      .then((res) => res.data),
};
