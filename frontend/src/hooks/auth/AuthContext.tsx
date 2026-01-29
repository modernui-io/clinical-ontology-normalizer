"use client";

/**
 * Authentication context and provider.
 * Manages user authentication state, login, logout, and token refresh.
 */

import { useState, useCallback, useEffect, createContext, useContext, type ReactNode } from "react";
import { getStoredTokens, setStoredTokens, getStoredUser, setStoredUser } from "./authStorage";
import {
  apiLogin,
  apiLogout,
  apiRegister,
  apiRefreshToken,
  apiUpdateProfile,
  apiChangePassword,
  apiForgotPassword,
} from "./authApi";

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
// Hooks
// ============================================================================

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return context;
}

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
