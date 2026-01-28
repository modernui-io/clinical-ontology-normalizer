"use client";

/**
 * Authentication hook for managing user authentication state.
 *
 * This hook provides:
 * - User authentication state (isAuthenticated, user)
 * - Login, logout, and register functions
 * - Token management with automatic refresh
 * - Persistent session storage
 */

import { useState, useCallback, useEffect, createContext, useContext, type ReactNode } from "react";

// ============================================================================
// Types
// ============================================================================

export interface User {
  id: string;
  email: string;
  name: string;
  roles: string[];
  permissions: string[];
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginCredentials {
  email: string;
  password: string;
  remember_me?: boolean;
}

export interface RegisterData {
  email: string;
  password: string;
  name: string;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

export interface AuthContextType extends AuthState {
  login: (credentials: LoginCredentials) => Promise<boolean>;
  logout: () => Promise<void>;
  register: (data: RegisterData) => Promise<boolean>;
  updateProfile: (data: Partial<User>) => Promise<boolean>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<boolean>;
  forgotPassword: (email: string) => Promise<boolean>;
  clearError: () => void;
}

// ============================================================================
// API Configuration
// ============================================================================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ============================================================================
// Storage helpers
// ============================================================================

const TOKEN_KEY = "auth_tokens";
const USER_KEY = "auth_user";

function getStoredTokens(): AuthTokens | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem(TOKEN_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch {
    return null;
  }
}

function setStoredTokens(tokens: AuthTokens | null): void {
  if (typeof window === "undefined") return;
  if (tokens) {
    localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem(USER_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch {
    return null;
  }
}

function setStoredUser(user: User | null): void {
  if (typeof window === "undefined") return;
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(USER_KEY);
  }
}

// ============================================================================
// API Functions
// ============================================================================

async function apiLogin(credentials: LoginCredentials): Promise<{ user: User; tokens: AuthTokens }> {
  // Step 1: Login to get tokens
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(error.detail || "Invalid email or password");
  }

  const tokens: AuthTokens = await response.json();

  // Step 2: Fetch user info with the new access token
  const userResponse = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  });

  if (!userResponse.ok) {
    throw new Error("Failed to fetch user info after login");
  }

  const user: User = await userResponse.json();

  // Set auth cookie for middleware
  document.cookie = `has_auth=true; path=/; max-age=${tokens.expires_in}; SameSite=Lax`;

  return { user, tokens };
}

async function apiRegister(data: RegisterData): Promise<{ user: User; tokens: AuthTokens }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
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
  const userResponse = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  });

  if (!userResponse.ok) {
    throw new Error("Failed to fetch user info after registration");
  }

  const user: User = await userResponse.json();

  // Set auth cookie for middleware
  document.cookie = `has_auth=true; path=/; max-age=${tokens.expires_in}; SameSite=Lax`;

  return { user, tokens };
}

async function apiLogout(refreshToken: string): Promise<void> {
  // Clear auth cookie
  document.cookie = "has_auth=; path=/; max-age=0; SameSite=Lax";

  await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  }).catch(() => {
    // Ignore logout errors, we'll clear local state anyway
  });
}

async function apiRefreshToken(refreshToken: string): Promise<AuthTokens> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    throw new Error("Token refresh failed");
  }

  const tokens: AuthTokens = await response.json();

  // Refresh auth cookie
  document.cookie = `has_auth=true; path=/; max-age=${tokens.expires_in}; SameSite=Lax`;

  return tokens;
}

async function apiGetCurrentUser(accessToken: string): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!response.ok) {
    throw new Error("Failed to fetch user");
  }

  return response.json();
}

async function apiUpdateProfile(accessToken: string, data: Partial<User>): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/profile`, {
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

async function apiChangePassword(
  accessToken: string,
  currentPassword: string,
  newPassword: string
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/change-password`, {
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

async function apiForgotPassword(email: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || "Failed to send reset email");
  }
}

// ============================================================================
// Auth Context
// ============================================================================

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
    error: null,
  });
  const [tokens, setTokens] = useState<AuthTokens | null>(null);

  // Initialize auth state from storage
  useEffect(() => {
    const storedTokens = getStoredTokens();
    const storedUser = getStoredUser();

    if (storedTokens && storedUser) {
      setTokens(storedTokens);
      setState({
        user: storedUser,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } else {
      setState((prev) => ({ ...prev, isLoading: false }));
    }
  }, []);

  // Token refresh effect
  useEffect(() => {
    if (!tokens) return;

    // Refresh token 1 minute before expiration
    const refreshInterval = (tokens.expires_in - 60) * 1000;
    if (refreshInterval <= 0) return;

    const timeout = setTimeout(async () => {
      try {
        const newTokens = await apiRefreshToken(tokens.refresh_token);
        setTokens(newTokens);
        setStoredTokens(newTokens);
      } catch {
        // Token refresh failed, log out
        setTokens(null);
        setStoredTokens(null);
        setStoredUser(null);
        setState({
          user: null,
          isAuthenticated: false,
          isLoading: false,
          error: "Session expired. Please log in again.",
        });
      }
    }, refreshInterval);

    return () => clearTimeout(timeout);
  }, [tokens]);

  const login = useCallback(async (credentials: LoginCredentials): Promise<boolean> => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      const { user, tokens: newTokens } = await apiLogin(credentials);

      setTokens(newTokens);
      setStoredTokens(newTokens);
      setStoredUser(user);

      setState({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });

      return true;
    } catch (error) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : "Login failed",
      }));
      return false;
    }
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    if (tokens?.refresh_token) {
      await apiLogout(tokens.refresh_token);
    }

    setTokens(null);
    setStoredTokens(null);
    setStoredUser(null);

    setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
  }, [tokens]);

  const register = useCallback(async (data: RegisterData): Promise<boolean> => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      const { user, tokens: newTokens } = await apiRegister(data);

      setTokens(newTokens);
      setStoredTokens(newTokens);
      setStoredUser(user);

      setState({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });

      return true;
    } catch (error) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : "Registration failed",
      }));
      return false;
    }
  }, []);

  const updateProfile = useCallback(
    async (data: Partial<User>): Promise<boolean> => {
      if (!tokens?.access_token) return false;

      setState((prev) => ({ ...prev, isLoading: true, error: null }));

      try {
        const updatedUser = await apiUpdateProfile(tokens.access_token, data);

        setStoredUser(updatedUser);
        setState((prev) => ({
          ...prev,
          user: updatedUser,
          isLoading: false,
        }));

        return true;
      } catch (error) {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: error instanceof Error ? error.message : "Update failed",
        }));
        return false;
      }
    },
    [tokens]
  );

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string): Promise<boolean> => {
      if (!tokens?.access_token) return false;

      setState((prev) => ({ ...prev, isLoading: true, error: null }));

      try {
        await apiChangePassword(tokens.access_token, currentPassword, newPassword);
        setState((prev) => ({ ...prev, isLoading: false }));
        return true;
      } catch (error) {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: error instanceof Error ? error.message : "Password change failed",
        }));
        return false;
      }
    },
    [tokens]
  );

  const forgotPassword = useCallback(async (email: string): Promise<boolean> => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      await apiForgotPassword(email);
      setState((prev) => ({ ...prev, isLoading: false }));
      return true;
    } catch (error) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : "Request failed",
      }));
      return false;
    }
  }, []);

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  const value: AuthContextType = {
    ...state,
    login,
    logout,
    register,
    updateProfile,
    changePassword,
    forgotPassword,
    clearError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ============================================================================
// Hook
// ============================================================================

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return context;
}

// ============================================================================
// Utility Hook for Protected Routes
// ============================================================================

export function useRequireAuth(redirectTo: string = "/login") {
  const auth = useAuth();

  useEffect(() => {
    if (!auth.isLoading && !auth.isAuthenticated) {
      // Store the current URL to redirect back after login
      if (typeof window !== "undefined") {
        sessionStorage.setItem("redirectAfterLogin", window.location.pathname);
        window.location.href = redirectTo;
      }
    }
  }, [auth.isLoading, auth.isAuthenticated, redirectTo]);

  return auth;
}

// ============================================================================
// Password Strength Utility
// ============================================================================

export interface PasswordStrength {
  score: number; // 0-4
  label: "Very Weak" | "Weak" | "Fair" | "Strong" | "Very Strong";
  suggestions: string[];
  color: string;
}

export function checkPasswordStrength(password: string): PasswordStrength {
  let score = 0;
  const suggestions: string[] = [];

  if (password.length === 0) {
    return {
      score: 0,
      label: "Very Weak",
      suggestions: ["Enter a password"],
      color: "bg-gray-200",
    };
  }

  // Length checks
  if (password.length >= 8) score++;
  else suggestions.push("Use at least 8 characters");

  if (password.length >= 12) score++;

  // Character type checks
  if (/[a-z]/.test(password)) score += 0.5;
  else suggestions.push("Add lowercase letters");

  if (/[A-Z]/.test(password)) score += 0.5;
  else suggestions.push("Add uppercase letters");

  if (/[0-9]/.test(password)) score += 0.5;
  else suggestions.push("Add numbers");

  if (/[^a-zA-Z0-9]/.test(password)) score += 0.5;
  else suggestions.push("Add special characters");

  // Normalize score to 0-4
  score = Math.min(4, Math.round(score));

  const labels: PasswordStrength["label"][] = [
    "Very Weak",
    "Weak",
    "Fair",
    "Strong",
    "Very Strong",
  ];

  const colors = [
    "bg-red-500",
    "bg-orange-500",
    "bg-yellow-500",
    "bg-lime-500",
    "bg-green-500",
  ];

  return {
    score,
    label: labels[score],
    suggestions: score < 3 ? suggestions : [],
    color: colors[score],
  };
}
