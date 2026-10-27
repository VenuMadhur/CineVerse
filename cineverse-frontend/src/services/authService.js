import { apiClient } from './apiClient';

// Wraps the backend's /auth endpoints exactly as implemented --
// POST /auth/register, POST /auth/login, POST /auth/refresh,
// GET /auth/me. (POST /auth/token is the OAuth2-form variant used
// only by Swagger's Authorize button and is intentionally not used
// here.)
export const authService = {
  register: ({ email, fullName, password, country }) =>
    apiClient
      .post('/auth/register', { email, full_name: fullName, password, country })
      .then((res) => res.data),

  login: ({ email, password }) =>
    apiClient.post('/auth/login', { email, password }).then((res) => res.data),

  refresh: (refreshToken) =>
    apiClient
      .post('/auth/refresh', { refresh_token: refreshToken })
      .then((res) => res.data),

  // The authenticated user's own account details, including
  // is_superuser -- used to decide whether to show admin-only UI.
  getMe: () => apiClient.get('/auth/me').then((res) => res.data),

  // Records a logout event for the Activity Timeline. JWT auth is
  // stateless, so there's no session to invalidate server-side --
  // this call is purely for the audit trail, called best-effort
  // (fire-and-forget) by AuthContext.logout() before it clears the
  // stored tokens.
  logout: () => apiClient.post('/auth/logout').then((res) => res.data),
};
