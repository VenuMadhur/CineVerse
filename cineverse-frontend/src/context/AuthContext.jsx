import { useCallback, useEffect, useMemo, useState } from 'react';
import { authService } from '../services/authService';
import { clearTokens, setTokens } from '../services/apiClient';
import { STORAGE_KEYS } from '../utils/constants';
import { getUserIdFromToken, isTokenExpired } from '../utils/jwt';

import { AuthContext } from './AuthContextStore';

export function AuthProvider({ children }) {
  const resolveUserIdFromStorage = useCallback(() => {
    const accessToken = localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
    const refreshToken = localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);

    if (accessToken && !isTokenExpired(accessToken)) {
      return getUserIdFromToken(accessToken);
    }
    if (refreshToken) {
      return getUserIdFromToken(refreshToken);
    }
    return null;
  }, []);

  const [userId, setUserId] = useState(() => {
    const accessToken = localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
    const refreshToken = localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);

    if (accessToken && !isTokenExpired(accessToken)) {
      return getUserIdFromToken(accessToken);
    }
    if (refreshToken) {
      return getUserIdFromToken(refreshToken);
    }
    return null;
  });
  const [lastKnownEmail, setLastKnownEmail] = useState(null); // in-memory only, used to bridge to Customer right after login/register
  const [initializing] = useState(false);
  const [isSuperuser, setIsSuperuser] = useState(false);
  const [roleLoading, setRoleLoading] = useState(true);
  const [accountInfo, setAccountInfo] = useState(null); // { email, fullName } from GET /auth/me


  useEffect(() => {
    // Only used to re-sync if storage changes in another tab
    setUserId(resolveUserIdFromStorage());
  }, [resolveUserIdFromStorage]);

  // QA fix (Issue 1: "Exit to Customer App sometimes doesn't
  // synchronize"): localStorage is shared across every tab of the
  // same origin, but React state is per-tab. If a customer is logged
  // in in one tab and a different account logs in (e.g. as admin) in
  // another, the first tab's AuthContext/CustomerContext never learn
  // the token underneath them changed -- they keep rendering
  // whichever account *used to be* logged in until something forces a
  // refetch. The browser's native `storage` event fires in every
  // *other* tab exactly when this happens (never the tab that made
  // the change), so listening for it and re-resolving the current
  // user from the now-current tokens keeps every open tab honest
  // about who is actually logged in.
  useEffect(() => {
    const handleStorage = (event) => {
      if (event.key !== STORAGE_KEYS.ACCESS_TOKEN && event.key !== STORAGE_KEYS.REFRESH_TOKEN) {
        return;
      }
      setUserId(resolveUserIdFromStorage());
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, [resolveUserIdFromStorage]);

  // Whenever the authenticated user changes (login, register, logout,
  // or session restore on mount), (re)load the account's role via
  // GET /auth/me. Drives AdminRoute and any admin-only UI. Also
  // captures email/full_name from the same response -- e.g. for
  // AdminTopbar -- so nothing else needs a second call to the same
  // endpoint.
  useEffect(() => {
    let cancelled = false;

    if (!userId) {
      setIsSuperuser(false);
      setAccountInfo(null);
      setRoleLoading(false);
      return undefined;
    }

    setRoleLoading(true);
    authService
      .getMe()
      .then((me) => {
        if (!cancelled) {
          setIsSuperuser(Boolean(me.is_superuser));
          setAccountInfo({ email: me.email, fullName: me.full_name });
        }
      })
      .catch(() => {
        // Token invalid/expired, network error, etc. -- fail closed
        // (never grant admin access) rather than crash the app.
        if (!cancelled) {
          setIsSuperuser(false);
          setAccountInfo(null);
        }
      })
      .finally(() => {
        if (!cancelled) setRoleLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [userId]);

  // If the refresh flow ever fails outright, apiClient dispatches this
  // event so every consumer of AuthContext logs out in sync.
  useEffect(() => {
    const handleSessionExpired = () => {
      setUserId(null);
      setLastKnownEmail(null);
    };
    window.addEventListener('cv:session-expired', handleSessionExpired);
    return () => window.removeEventListener('cv:session-expired', handleSessionExpired);
  }, []);

  const login = useCallback(async (email, password) => {
    const tokens = await authService.login({ email, password });
    setTokens(tokens);
    setUserId(getUserIdFromToken(tokens.access_token));
    setLastKnownEmail(email);
    return tokens;
  }, []);

  const register = useCallback(async ({ email, fullName, password, country }) => {
    await authService.register({ email, fullName, password, country });
    // Registration only creates the account; log in immediately after
    // to obtain tokens, exactly as a real user would.
    const tokens = await authService.login({ email, password });
    const newUserId = getUserIdFromToken(tokens.access_token);
    setTokens(tokens);
    setUserId(newUserId);
    setLastKnownEmail(email);
    // Return userId directly (not just tokens) so callers like
    // RegisterPage can pass it straight through to provisionCustomer
    // instead of reading it back out of context -- avoids a stale-
    // closure race where the caller's `userId` reference from context
    // is still the pre-registration value.
    return { ...tokens, userId: newUserId };
  }, []);

  const logout = useCallback(() => {
    // Best-effort: records the logout event for the Activity Timeline.
    // Must fire before clearTokens() below, since the endpoint requires
    // the (about to be cleared) auth token. Never awaited and never
    // allowed to block or fail the actual logout -- a slow network or
    // a dead backend must never prevent someone from logging out.
    authService.logout().catch(() => {});
    clearTokens();
    setUserId(null);
    setLastKnownEmail(null);
    setIsSuperuser(false);
    setAccountInfo(null);
  }, []);

  const value = useMemo(
    () => ({
      userId,
      isAuthenticated: Boolean(userId),
      initializing,
      lastKnownEmail,
      isSuperuser,
      roleLoading,
      accountInfo,
      login,
      register,
      logout,
    }),
    [
      userId,
      initializing,
      lastKnownEmail,
      isSuperuser,
      roleLoading,
      accountInfo,
      login,
      register,
      logout,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
