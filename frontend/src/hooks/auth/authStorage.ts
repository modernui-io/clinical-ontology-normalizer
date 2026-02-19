/**
 * Token and user storage helpers for authentication.
 * Handles sessionStorage/localStorage operations with SSR safety.
 *
 * When "Remember me" is checked, tokens are stored in localStorage
 * so they persist across tab closes and browser restarts.
 * Otherwise, sessionStorage is used (cleared when the tab closes).
 */

import type { AuthTokens, User } from "./AuthContext";

// ============================================================================
// Storage Keys
// ============================================================================

const TOKEN_KEY = "auth_tokens";
const USER_KEY = "auth_user";
const PERSIST_KEY = "auth_persist";

// ============================================================================
// Persistence Preference
// ============================================================================

function getStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    const persist = localStorage.getItem(PERSIST_KEY) === "true";
    return persist ? localStorage : sessionStorage;
  } catch {
    return sessionStorage;
  }
}

export function setRememberMe(remember: boolean): void {
  if (typeof window === "undefined") return;
  if (remember) {
    localStorage.setItem(PERSIST_KEY, "true");
  } else {
    localStorage.removeItem(PERSIST_KEY);
  }
}

// ============================================================================
// Token Storage
// ============================================================================

export function getStoredTokens(): AuthTokens | null {
  if (typeof window === "undefined") return null;
  try {
    // Check both storages in case the user switched preference
    const fromLocal = localStorage.getItem(TOKEN_KEY);
    const fromSession = sessionStorage.getItem(TOKEN_KEY);
    const stored = fromLocal || fromSession;
    return stored ? JSON.parse(stored) : null;
  } catch {
    return null;
  }
}

export function setStoredTokens(tokens: AuthTokens | null): void {
  const storage = getStorage();
  if (!storage) return;

  if (tokens) {
    storage.setItem(TOKEN_KEY, JSON.stringify(tokens));
  } else {
    // Clear from both storages on logout
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
  }
}

// ============================================================================
// User Storage
// ============================================================================

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  try {
    const fromLocal = localStorage.getItem(USER_KEY);
    const fromSession = sessionStorage.getItem(USER_KEY);
    const stored = fromLocal || fromSession;
    return stored ? JSON.parse(stored) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user: User | null): void {
  const storage = getStorage();
  if (!storage) return;

  if (user) {
    storage.setItem(USER_KEY, JSON.stringify(user));
  } else {
    // Clear from both storages on logout
    localStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(USER_KEY);
  }
}
