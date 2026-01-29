/**
 * Token and user storage helpers for authentication.
 * Handles localStorage operations with SSR safety.
 */

import type { AuthTokens, User } from "./AuthContext";

// ============================================================================
// Storage Keys
// ============================================================================

const TOKEN_KEY = "auth_tokens";
const USER_KEY = "auth_user";

// ============================================================================
// Token Storage
// ============================================================================

export function getStoredTokens(): AuthTokens | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem(TOKEN_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch {
    return null;
  }
}

export function setStoredTokens(tokens: AuthTokens | null): void {
  if (typeof window === "undefined") return;
  if (tokens) {
    localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

// ============================================================================
// User Storage
// ============================================================================

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem(USER_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user: User | null): void {
  if (typeof window === "undefined") return;
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(USER_KEY);
  }
}
