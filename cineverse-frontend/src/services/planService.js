import { apiClient } from './apiClient';

// Wraps the backend's /plans endpoints exactly as implemented.
// Listing/getting plans requires no auth (public plan browsing);
// create/update/archive require an admin token (Phase 1C) -- used by
// the Admin Plans page, never by the customer-facing PlansPage.
export const planService = {
  list: ({ status, page = 1, pageSize = 50 } = {}) =>
    apiClient
      .get('/plans', { params: { status, page, page_size: pageSize } })
      .then((res) => res.data),

  get: (planId) => apiClient.get(`/plans/${planId}`).then((res) => res.data),

  create: ({ name, description, price, currency, billingInterval, trialPeriodDays, featureEntitlements }) =>
    apiClient
      .post('/plans', {
        name,
        description: description || undefined,
        price,
        currency: currency || undefined,
        billing_interval: billingInterval,
        trial_period_days: trialPeriodDays ?? 0,
        feature_entitlements: featureEntitlements || undefined,
      })
      .then((res) => res.data),

  update: (planId, { description, price, billingInterval, trialPeriodDays, featureEntitlements }) =>
    apiClient
      .patch(`/plans/${planId}`, {
        description: description || undefined,
        price: price ?? undefined,
        billing_interval: billingInterval || undefined,
        trial_period_days: trialPeriodDays ?? undefined,
        feature_entitlements: featureEntitlements || undefined,
      })
      .then((res) => res.data),

  archive: (planId) => apiClient.post(`/plans/${planId}/archive`).then((res) => res.data),
  unarchive: (planId) => apiClient.post(`/plans/${planId}/unarchive`).then((res) => res.data),
  remove: (planId) => apiClient.delete(`/plans/${planId}`).then((res) => res.data),
};
