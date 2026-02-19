/**
 * Auth module exports.
 * Re-exports all authentication-related types, hooks, and utilities.
 */

// Main context, provider, and hooks
export {
  AuthProvider,
  useAuth,
  useRequireAuth,
  type User,
  type AuthTokens,
  type LoginCredentials,
  type RegisterData,
  type AuthState,
  type AuthContextType,
} from "./AuthContext";

// Storage utilities
export {
  getStoredTokens,
  setStoredTokens,
  getStoredUser,
  setStoredUser,
  setRememberMe,
} from "./authStorage";

// API functions
export {
  apiLogin,
  apiLogout,
  apiRegister,
  apiRefreshToken,
  apiGetCurrentUser,
  apiUpdateProfile,
  apiChangePassword,
  apiForgotPassword,
} from "./authApi";

// Password strength utilities
export {
  checkPasswordStrength,
  type PasswordStrength,
} from "./usePasswordStrength";
