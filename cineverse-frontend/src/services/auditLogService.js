import { apiClient } from './apiClient';

// Wraps the backend's /audit-logs endpoints exactly as implemented.
export const auditLogService = {
  listForEntity: (entityType, entityId) =>
    apiClient.get(`/audit-logs/${entityType}/${entityId}`).then((res) => res.data),

  list: ({ entityType, page = 1, pageSize = 20 } = {}) =>
    apiClient
      .get('/audit-logs', { params: { entity_type: entityType, page, page_size: pageSize } })
      .then((res) => res.data),

  // Account-wide Activity Timeline: every event across the caller's
  // own account (registration, logins/logouts, subscriptions,
  // invoices, payments, refunds), chronological. Always scoped to
  // "me" -- no customer_id param, since there's no admin/"see
  // everyone" mode for this endpoint.
  listForMe: ({ page = 1, pageSize = 20 } = {}) =>
    apiClient
      .get('/audit-logs/me', { params: { page, page_size: pageSize } })
      .then((res) => res.data),
};
