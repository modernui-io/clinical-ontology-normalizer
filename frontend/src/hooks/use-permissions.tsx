"use client";

/**
 * Permission-based UI element visibility hook.
 *
 * P1-020: Provides utilities for permission-based rendering:
 * - Check if user has specific permission(s)
 * - PermissionGate component for conditional rendering
 * - Role-based access control utilities
 */

import { useCallback, useMemo, type ReactNode } from "react";
import { useAuth, type User } from "./use-auth";

// ============================================================================
// Permission Constants
// ============================================================================

/**
 * Application permission types organized by domain.
 * These match the backend RBAC service permission names exactly.
 */
export const PERMISSIONS = {
  // Document permissions (matches backend documents:*)
  DOCUMENTS_READ: "documents:read",
  DOCUMENTS_WRITE: "documents:write",
  DOCUMENTS_DELETE: "documents:delete",
  DOCUMENTS_ADMIN: "documents:admin",

  // Patient permissions (matches backend patients:*)
  PATIENTS_READ: "patients:read",
  PATIENTS_WRITE: "patients:write",
  PATIENTS_DELETE: "patients:delete",
  PATIENTS_ADMIN: "patients:admin",

  // Billing permissions (matches backend billing:*)
  BILLING_READ: "billing:read",
  BILLING_WRITE: "billing:write",
  BILLING_DELETE: "billing:delete",
  BILLING_ADMIN: "billing:admin",

  // Coding permissions (matches backend coding:*)
  CODING_READ: "coding:read",
  CODING_WRITE: "coding:write",
  CODING_DELETE: "coding:delete",
  CODING_ADMIN: "coding:admin",

  // Audit permissions (matches backend audit:*)
  AUDIT_READ: "audit:read",
  AUDIT_WRITE: "audit:write",
  AUDIT_EXPORT: "audit:export",
  AUDIT_ADMIN: "audit:admin",

  // Admin permissions (matches backend admin:*)
  ADMIN_READ: "admin:read",
  ADMIN_WRITE: "admin:write",
  ADMIN_MANAGE_USERS: "admin:manage_users",
  ADMIN_MANAGE_ROLES: "admin:manage_roles",

  // Vocabulary permissions (matches backend vocabulary:*)
  VOCABULARY_READ: "vocabulary:read",
  VOCABULARY_WRITE: "vocabulary:write",
  VOCABULARY_ADMIN: "vocabulary:admin",

  // Graphs permissions (matches backend graphs:*)
  GRAPHS_READ: "graphs:read",
  GRAPHS_WRITE: "graphs:write",
  GRAPHS_ADMIN: "graphs:admin",

  // Export permissions (matches backend export:*)
  EXPORT_READ: "export:read",
  EXPORT_WRITE: "export:write",
  EXPORT_ADMIN: "export:admin",

  // LLM permissions (matches backend llm:*)
  LLM_READ: "llm:read",
  LLM_WRITE: "llm:write",
  LLM_ADMIN: "llm:admin",
} as const;

export type Permission = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

/**
 * Role definitions matching backend RBAC service.
 */
export const ROLES = {
  ADMIN: "admin",
  PROVIDER: "provider",
  BILLER: "biller",
  VIEWER: "viewer",
} as const;

export type Role = (typeof ROLES)[keyof typeof ROLES];

/**
 * Default permissions for each role (matching backend rbac_service.py).
 */
export const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  [ROLES.ADMIN]: Object.values(PERMISSIONS),
  [ROLES.PROVIDER]: [
    // Clinical document access
    PERMISSIONS.DOCUMENTS_READ,
    PERMISSIONS.DOCUMENTS_WRITE,
    // Patient information access
    PERMISSIONS.PATIENTS_READ,
    PERMISSIONS.PATIENTS_WRITE,
    // Read billing/coding info but not modify
    PERMISSIONS.BILLING_READ,
    PERMISSIONS.CODING_READ,
    // Vocabulary lookup
    PERMISSIONS.VOCABULARY_READ,
    // Knowledge graph access
    PERMISSIONS.GRAPHS_READ,
    PERMISSIONS.GRAPHS_WRITE,
    // Export patient data
    PERMISSIONS.EXPORT_READ,
    PERMISSIONS.EXPORT_WRITE,
    // Use LLM features
    PERMISSIONS.LLM_READ,
    PERMISSIONS.LLM_WRITE,
  ],
  [ROLES.BILLER]: [
    // Read clinical documents for coding
    PERMISSIONS.DOCUMENTS_READ,
    // Read patient information for billing
    PERMISSIONS.PATIENTS_READ,
    // Full billing access
    PERMISSIONS.BILLING_READ,
    PERMISSIONS.BILLING_WRITE,
    // Full coding access
    PERMISSIONS.CODING_READ,
    PERMISSIONS.CODING_WRITE,
    // Vocabulary for code lookup
    PERMISSIONS.VOCABULARY_READ,
    // Export billing data
    PERMISSIONS.EXPORT_READ,
    PERMISSIONS.EXPORT_WRITE,
  ],
  [ROLES.VIEWER]: [
    // Read-only access to documents (no PHI by default)
    PERMISSIONS.DOCUMENTS_READ,
    // Read vocabulary
    PERMISSIONS.VOCABULARY_READ,
    // Read graphs
    PERMISSIONS.GRAPHS_READ,
  ],
};

// ============================================================================
// Permission Hook
// ============================================================================

export interface PermissionContext {
  /** Current user */
  user: User | null;
  /** Check if user has a specific permission */
  hasPermission: (permission: Permission) => boolean;
  /** Check if user has ALL of the specified permissions */
  hasAllPermissions: (permissions: Permission[]) => boolean;
  /** Check if user has ANY of the specified permissions */
  hasAnyPermission: (permissions: Permission[]) => boolean;
  /** Check if user has a specific role */
  hasRole: (role: Role) => boolean;
  /** Check if user has ANY of the specified roles */
  hasAnyRole: (roles: Role[]) => boolean;
  /** Check if user is an admin */
  isAdmin: boolean;
  /** Get all user permissions (from user + roles) */
  allPermissions: Permission[];
}

/**
 * Hook for checking user permissions.
 */
export function usePermissions(): PermissionContext {
  const { user } = useAuth();

  // Compute all permissions from user permissions + role-based permissions
  const allPermissions = useMemo(() => {
    if (!user) return [];

    const permSet = new Set<Permission>();

    // Add direct permissions
    user.permissions?.forEach((p) => permSet.add(p as Permission));

    // Add role-based permissions
    user.roles?.forEach((role) => {
      const rolePerms = ROLE_PERMISSIONS[role as Role];
      if (rolePerms) {
        rolePerms.forEach((p) => permSet.add(p));
      }
    });

    return Array.from(permSet);
  }, [user]);

  const hasPermission = useCallback(
    (permission: Permission): boolean => {
      return allPermissions.includes(permission);
    },
    [allPermissions]
  );

  const hasAllPermissions = useCallback(
    (permissions: Permission[]): boolean => {
      return permissions.every((p) => allPermissions.includes(p));
    },
    [allPermissions]
  );

  const hasAnyPermission = useCallback(
    (permissions: Permission[]): boolean => {
      return permissions.some((p) => allPermissions.includes(p));
    },
    [allPermissions]
  );

  const hasRole = useCallback(
    (role: Role): boolean => {
      return user?.roles?.includes(role) ?? false;
    },
    [user]
  );

  const hasAnyRole = useCallback(
    (roles: Role[]): boolean => {
      return roles.some((role) => user?.roles?.includes(role));
    },
    [user]
  );

  const isAdmin = useMemo(() => {
    return user?.roles?.includes(ROLES.ADMIN) ?? false;
  }, [user]);

  return {
    user,
    hasPermission,
    hasAllPermissions,
    hasAnyPermission,
    hasRole,
    hasAnyRole,
    isAdmin,
    allPermissions,
  };
}

// ============================================================================
// PermissionGate Component
// ============================================================================

export interface PermissionGateProps {
  /** Permission(s) required - if array, uses 'all' or 'any' based on `mode` */
  permission?: Permission | Permission[];
  /** Role(s) required - if array, uses 'any' mode */
  role?: Role | Role[];
  /** Mode for checking multiple permissions: 'all' or 'any' */
  mode?: "all" | "any";
  /** Content to render if permission check passes */
  children: ReactNode;
  /** Fallback content if permission check fails */
  fallback?: ReactNode;
  /** If true, shows fallback only when user is authenticated but lacks permission */
  hideWhenUnauthenticated?: boolean;
}

/**
 * Component for conditionally rendering content based on user permissions.
 *
 * @example
 * ```tsx
 * <PermissionGate permission={PERMISSIONS.PATIENT_EDIT}>
 *   <Button>Edit Patient</Button>
 * </PermissionGate>
 *
 * <PermissionGate
 *   permission={[PERMISSIONS.REPORT_CREATE, PERMISSIONS.REPORT_EXPORT]}
 *   mode="any"
 *   fallback={<span>Insufficient permissions</span>}
 * >
 *   <ReportBuilder />
 * </PermissionGate>
 * ```
 */
export function PermissionGate({
  permission,
  role,
  mode = "all",
  children,
  fallback = null,
  hideWhenUnauthenticated = true,
}: PermissionGateProps): ReactNode {
  const { user } = useAuth();
  const { hasPermission, hasAllPermissions, hasAnyPermission, hasRole, hasAnyRole } =
    usePermissions();

  // Handle unauthenticated users
  if (!user) {
    return hideWhenUnauthenticated ? null : fallback;
  }

  // Check permissions
  let hasRequiredPermission = true;
  if (permission) {
    const permissions = Array.isArray(permission) ? permission : [permission];
    hasRequiredPermission =
      mode === "all" ? hasAllPermissions(permissions) : hasAnyPermission(permissions);
  }

  // Check roles
  let hasRequiredRole = true;
  if (role) {
    const roles = Array.isArray(role) ? role : [role];
    hasRequiredRole = hasAnyRole(roles);
  }

  // Both permission and role must pass if both are specified
  if (hasRequiredPermission && hasRequiredRole) {
    return children;
  }

  return fallback;
}

// ============================================================================
// Higher-Order Component
// ============================================================================

export interface WithPermissionOptions {
  permission?: Permission | Permission[];
  role?: Role | Role[];
  mode?: "all" | "any";
  fallback?: ReactNode;
}

/**
 * Higher-order component for permission-based component wrapping.
 *
 * @example
 * ```tsx
 * const ProtectedReportBuilder = withPermission(ReportBuilder, {
 *   permission: PERMISSIONS.REPORT_CREATE,
 *   fallback: <AccessDenied />,
 * });
 * ```
 */
export function withPermission<P extends object>(
  Component: React.ComponentType<P>,
  options: WithPermissionOptions
) {
  return function PermissionWrappedComponent(props: P) {
    return (
      <PermissionGate {...options}>
        <Component {...props} />
      </PermissionGate>
    );
  };
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Get the display name for a permission.
 */
export function getPermissionDisplayName(permission: Permission): string {
  const parts = permission.split(":");
  return parts
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" - ");
}

/**
 * Get the display name for a role.
 */
export function getRoleDisplayName(role: Role): string {
  return role
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/**
 * Group permissions by domain.
 */
export function groupPermissionsByDomain(): Record<string, Permission[]> {
  const grouped: Record<string, Permission[]> = {};

  Object.values(PERMISSIONS).forEach((permission) => {
    const domain = permission.split(":")[0];
    if (!grouped[domain]) {
      grouped[domain] = [];
    }
    grouped[domain].push(permission);
  });

  return grouped;
}
