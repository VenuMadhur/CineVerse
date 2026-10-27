import { jwtDecode } from 'jwt-decode';

/**
 * Decodes a JWT access token client-side to read its claims (sub, exp,
 * type). This is NOT signature verification -- the backend is always
 * the source of truth for whether a token is valid; this is purely for
 * UI convenience (e.g. reading the user id to key the customer map, or
 * checking expiry to decide whether to refresh proactively).
 */
export function decodeToken(token) {
  if (!token) return null;
  try {
    return jwtDecode(token);
  } catch {
    return null;
  }
}

export function getUserIdFromToken(token) {
  const payload = decodeToken(token);
  return payload?.sub ?? null;
}

export function isTokenExpired(token) {
  const payload = decodeToken(token);
  if (!payload?.exp) return true;
  const nowInSeconds = Date.now() / 1000;
  return payload.exp < nowInSeconds;
}
