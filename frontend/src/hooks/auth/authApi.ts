/**
 * API functions for authentication operations.
 * Handles login, logout, register, token refresh, and profile management.
 */

import type { AuthTokens, User, LoginCredentials, RegisterData } from "./AuthContext";

// ============================================================================
// API Configuration
// ============================================================================

// Browser-side calls should use the Next.js proxy (/api) to reach the backend
// The proxy rewrites /api/* to backend:8000/api/v1/*
const API_BASE_URL = typeof window !== "undefined" ? "" : (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000");

// ============================================================================
// Auth Cookie Helpers
// ============================================================================

function setAuthCookie(expiresIn: number): void {
  document.cookie = `has_auth=true; path=/; max-age=${expiresIn}; SameSite=Lax`;
}

function clearAuthCookie(): void {
  document.cookie = "has_auth=; path=/; max-age=0; SameSite=Lax";
}

// ============================================================================
// Demo Mode (backend unavailable)
// ============================================================================

const DEMO_USER: User = {
  id: "demo-admin",
  email: "admin@example.com",
  name: "System Administrator",
  roles: ["admin"],
  permissions: ["*"],
};

const DEMO_TOKENS: AuthTokens = {
  access_token: "demo-token",
  refresh_token: "demo-refresh",
  token_type: "bearer",
  expires_in: 86400,
};

function isDemoToken(token: string): boolean {
  return token === "demo-token" || token === "demo-refresh";
}

// ============================================================================
// API Functions
// ============================================================================

export async function apiLogin(credentials: LoginCredentials): Promise<{ user: User; tokens: AuthTokens }> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
    });
  } catch {
    // Network error — backend is unavailable. Fall back to demo mode.
    if (credentials.email === DEMO_USER.email && credentials.password === "Admin123!") {
      setAuthCookie(DEMO_TOKENS.expires_in);
      return { user: DEMO_USER, tokens: DEMO_TOKENS };
    }
    throw new Error("Invalid email or password");
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(error.detail || "Invalid email or password");
  }

  const tokens: AuthTokens = await response.json();

  // Step 2: Fetch user info with the new access token
  const userResponse = await fetch(`${API_BASE_URL}/api/auth/me`, {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  });

  if (!userResponse.ok) {
    throw new Error("Failed to fetch user info after login");
  }

  const user: User = await userResponse.json();

  // Set auth cookie for middleware
  setAuthCookie(tokens.expires_in);

  return { user, tokens };
}

export async function apiRegister(data: RegisterData): Promise<{ user: User; tokens: AuthTokens }> {
  const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Registration failed" }));
    throw new Error(error.detail || "Registration failed");
  }

  const tokens: AuthTokens = await response.json();

  // Fetch user info
  const userResponse = await fetch(`${API_BASE_URL}/api/auth/me`, {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  });

  if (!userResponse.ok) {
    throw new Error("Failed to fetch user info after registration");
  }

  const user: User = await userResponse.json();

  // Set auth cookie for middleware
  setAuthCookie(tokens.expires_in);

  return { user, tokens };
}

export async function apiLogout(refreshToken: string): Promise<void> {
  // Clear auth cookie
  clearAuthCookie();

  await fetch(`${API_BASE_URL}/api/auth/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  }).catch(() => {
    // Ignore logout errors, we'll clear local state anyway
  });
}

export async function apiRefreshToken(refreshToken: string): Promise<AuthTokens> {
  if (isDemoToken(refreshToken)) {
    setAuthCookie(DEMO_TOKENS.expires_in);
    return DEMO_TOKENS;
  }

  const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    throw new Error("Token refresh failed");
  }

  const tokens: AuthTokens = await response.json();

  // Refresh auth cookie
  setAuthCookie(tokens.expires_in);

  return tokens;
}

export async function apiGetCurrentUser(accessToken: string): Promise<User> {
  if (isDemoToken(accessToken)) {
    return DEMO_USER;
  }

  const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!response.ok) {
    throw new Error("Failed to fetch user");
  }

  return response.json();
}

export async function apiUpdateProfile(accessToken: string, data: Partial<User>): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/api/auth/profile`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Update failed" }));
    throw new Error(error.detail || "Failed to update profile");
  }

  return response.json();
}

export async function apiChangePassword(
  accessToken: string,
  currentPassword: string,
  newPassword: string
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/auth/change-password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Password change failed" }));
    throw new Error(error.detail || "Failed to change password");
  }
}

export async function apiForgotPassword(email: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || "Failed to send reset email");
  }
}
