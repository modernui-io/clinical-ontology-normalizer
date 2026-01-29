"use client";

/**
 * Authentication hook for managing user authentication state.
 *
 * This hook provides:
 * - User authentication state (isAuthenticated, user)
 * - Login, logout, and register functions
 * - Token management with automatic refresh
 * - Persistent session storage
 *
 * @deprecated Import from './auth' instead for better tree-shaking.
 * This file re-exports from the auth module for backwards compatibility.
 */

export {
  // Main exports
  AuthProvider,
  useAuth,
  useRequireAuth,
  // Types
  type User,
  type AuthTokens,
  type LoginCredentials,
  type RegisterData,
  type AuthState,
  type AuthContextType,
  // Password strength
  checkPasswordStrength,
  type PasswordStrength,
} from "./auth";
