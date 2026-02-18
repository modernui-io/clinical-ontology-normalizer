/**
 * Token and user storage helpers for authentication.
 * Handles sessionStorage operations with SSR safety.
 *
 * Security: Uses sessionStorage instead of localStorage to limit XSS exposure.
 * sessionStorage is scoped to the browser tab and cleared when the tab closes,
 * reducing the window for token theft via injected scripts.
 * For production, pair with httpOnly cookie-based token transport.
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
    const stored = sessionStorage.getItem(TOKEN_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch {
    return null;
  }
}

export function setStoredTokens(tokens: AuthTokens | null): void {
  if (typeof window === "undefined") return;
  if (tokens) {
    sessionStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
  } else {
    sessionStorage.removeItem(TOKEN_KEY);
  }
}

// ============================================================================
// User Storage
// ============================================================================

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = sessionStorage.getItem(USER_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user: User | null): void {
  if (typeof window === "undefined") return;
  if (user) {
    sessionStorage.setItem(USER_KEY, JSON.stringify(user));
  } else {
    sessionStorage.removeItem(USER_KEY);
  }
}
