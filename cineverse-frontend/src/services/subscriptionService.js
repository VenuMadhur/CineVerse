import { apiClient } from './apiClient';

// Wraps the backend's /subscriptions endpoints exactly as implemented,
// including the Module 2 proration-preview and change-plan flow.
export const subscriptionService = {
  create: ({ customerId, planId }) =>
    apiClient
      .post('/subscriptions', { customer_id: customerId, plan_id: planId })
      .then((res) => res.data),

  list: ({ status, customerId, page = 1, pageSize = 50 } = {}) =>
    apiClient
      .get('/subscriptions', {
        params: { status, customer_id: customerId, page, page_size: pageSize },
      })
      .then((res) => res.data),

  get: (subscriptionId) =>
    apiClient.get(`/subscriptions/${subscriptionId}`).then((res) => res.data),

  activate: (subscriptionId) =>
    apiClient.post(`/subscriptions/${subscriptionId}/activate`).then((res) => res.data),

  previewProration: (subscriptionId, newPlanId) =>
    apiClient
      .post(`/subscriptions/${subscriptionId}/proration-preview`, { new_plan_id: newPlanId })
      .then((res) => res.data),

  changePlan: (subscriptionId, newPlanId) =>
    apiClient
      .post(`/subscriptions/${subscriptionId}/change-plan`, { new_plan_id: newPlanId })
      .then((res) => res.data),

  pause: (subscriptionId) =>
    apiClient.post(`/subscriptions/${subscriptionId}/pause`).then((res) => res.data),

  resume: (subscriptionId) =>
    apiClient.post(`/subscriptions/${subscriptionId}/resume`).then((res) => res.data),

  // QA fix (Finding #8): reverses a not-yet-executed "cancel at end
  // of billing cycle" request.
  undoCancellation: (subscriptionId) =>
    apiClient.post(`/subscriptions/${subscriptionId}/undo-cancellation`).then((res) => res.data),

  cancel: (subscriptionId, { cancellationType, reason }) =>
    apiClient
      .post(`/subscriptions/${subscriptionId}/cancel`, {
        cancellation_type: cancellationType,
        reason: reason || undefined,
      })
      .then((res) => res.data),

  listBillingCycles: (subscriptionId) =>
    apiClient
      .get(`/subscriptions/${subscriptionId}/billing-cycles`)
      .then((res) => res.data),
};
