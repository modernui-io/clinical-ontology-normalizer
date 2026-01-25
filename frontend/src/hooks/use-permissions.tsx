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
 */
export const PERMISSIONS = {
  // Patient-related permissions
  PATIENT_VIEW: "patient:view",
  PATIENT_CREATE: "patient:create",
  PATIENT_EDIT: "patient:edit",
  PATIENT_DELETE: "patient:delete",
  PATIENT_EXPORT: "patient:export",
  PATIENT_PHI_VIEW: "patient:phi:view",

  // Document permissions
  DOCUMENT_VIEW: "document:view",
  DOCUMENT_CREATE: "document:create",
  DOCUMENT_EDIT: "document:edit",
  DOCUMENT_DELETE: "document:delete",
  DOCUMENT_ANNOTATE: "document:annotate",
  DOCUMENT_UPLOAD: "document:upload",

  // Cohort permissions
  COHORT_VIEW: "cohort:view",
  COHORT_CREATE: "cohort:create",
  COHORT_EDIT: "cohort:edit",
  COHORT_DELETE: "cohort:delete",
  COHORT_EXPORT: "cohort:export",

  // Value set permissions
  VALUESET_VIEW: "valueset:view",
  VALUESET_CREATE: "valueset:create",
  VALUESET_EDIT: "valueset:edit",
  VALUESET_DELETE: "valueset:delete",
  VALUESET_PUBLISH: "valueset:publish",

  // ETL permissions
  ETL_VIEW: "etl:view",
  ETL_CREATE: "etl:create",
  ETL_RUN: "etl:run",
  ETL_CONFIGURE: "etl:configure",

  // Data quality permissions
  QUALITY_VIEW: "quality:view",
  QUALITY_RUN: "quality:run",
  QUALITY_CONFIGURE: "quality:configure",

  // Billing permissions
  BILLING_VIEW: "billing:view",
  BILLING_MANAGE: "billing:manage",
  BILLING_EXPORT: "billing:export",

  // Report permissions
  REPORT_VIEW: "report:view",
  REPORT_CREATE: "report:create",
  REPORT_EDIT: "report:edit",
  REPORT_DELETE: "report:delete",
  REPORT_EXPORT: "report:export",
  REPORT_SCHEDULE: "report:schedule",

  // Admin permissions
  ADMIN_USERS: "admin:users",
  ADMIN_ROLES: "admin:roles",
  ADMIN_SETTINGS: "admin:settings",
  ADMIN_AUDIT: "admin:audit",
  ADMIN_API_KEYS: "admin:api-keys",

  // AI/ML permissions
  AI_USE: "ai:use",
  AI_TRAIN: "ai:train",
  AI_CONFIGURE: "ai:configure",

  // Analytics permissions
  ANALYTICS_VIEW: "analytics:view",
  ANALYTICS_EXPORT: "analytics:export",
  ANALYTICS_ADVANCED: "analytics:advanced",
} as const;

export type Permission = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

/**
 * Role definitions with associated permissions.
 */
export const ROLES = {
  ADMIN: "admin",
  ANALYST: "analyst",
  CLINICIAN: "clinician",
  DATA_STEWARD: "data_steward",
  VIEWER: "viewer",
  RESEARCHER: "researcher",
} as const;

export type Role = (typeof ROLES)[keyof typeof ROLES];

/**
 * Default permissions for each role.
 */
export const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  [ROLES.ADMIN]: Object.values(PERMISSIONS),
  [ROLES.ANALYST]: [
    PERMISSIONS.PATIENT_VIEW,
    PERMISSIONS.PATIENT_EXPORT,
    PERMISSIONS.DOCUMENT_VIEW,
    PERMISSIONS.COHORT_VIEW,
    PERMISSIONS.COHORT_CREATE,
    PERMISSIONS.COHORT_EDIT,
    PERMISSIONS.COHORT_EXPORT,
    PERMISSIONS.VALUESET_VIEW,
    PERMISSIONS.QUALITY_VIEW,
    PERMISSIONS.BILLING_VIEW,
    PERMISSIONS.BILLING_EXPORT,
    PERMISSIONS.REPORT_VIEW,
    PERMISSIONS.REPORT_CREATE,
    PERMISSIONS.REPORT_EXPORT,
    PERMISSIONS.ANALYTICS_VIEW,
    PERMISSIONS.ANALYTICS_EXPORT,
    PERMISSIONS.AI_USE,
  ],
  [ROLES.CLINICIAN]: [
    PERMISSIONS.PATIENT_VIEW,
    PERMISSIONS.PATIENT_PHI_VIEW,
    PERMISSIONS.DOCUMENT_VIEW,
    PERMISSIONS.DOCUMENT_CREATE,
    PERMISSIONS.DOCUMENT_ANNOTATE,
    PERMISSIONS.COHORT_VIEW,
    PERMISSIONS.VALUESET_VIEW,
    PERMISSIONS.AI_USE,
    PERMISSIONS.REPORT_VIEW,
  ],
  [ROLES.DATA_STEWARD]: [
    PERMISSIONS.PATIENT_VIEW,
    PERMISSIONS.DOCUMENT_VIEW,
    PERMISSIONS.DOCUMENT_EDIT,
    PERMISSIONS.VALUESET_VIEW,
    PERMISSIONS.VALUESET_CREATE,
    PERMISSIONS.VALUESET_EDIT,
    PERMISSIONS.ETL_VIEW,
    PERMISSIONS.ETL_CONFIGURE,
    PERMISSIONS.QUALITY_VIEW,
    PERMISSIONS.QUALITY_RUN,
    PERMISSIONS.QUALITY_CONFIGURE,
    PERMISSIONS.REPORT_VIEW,
  ],
  [ROLES.VIEWER]: [
    PERMISSIONS.PATIENT_VIEW,
    PERMISSIONS.DOCUMENT_VIEW,
    PERMISSIONS.COHORT_VIEW,
    PERMISSIONS.VALUESET_VIEW,
    PERMISSIONS.QUALITY_VIEW,
    PERMISSIONS.REPORT_VIEW,
    PERMISSIONS.ANALYTICS_VIEW,
  ],
  [ROLES.RESEARCHER]: [
    PERMISSIONS.PATIENT_VIEW,
    PERMISSIONS.PATIENT_EXPORT,
    PERMISSIONS.DOCUMENT_VIEW,
    PERMISSIONS.COHORT_VIEW,
    PERMISSIONS.COHORT_CREATE,
    PERMISSIONS.COHORT_EDIT,
    PERMISSIONS.COHORT_EXPORT,
    PERMISSIONS.VALUESET_VIEW,
    PERMISSIONS.ANALYTICS_VIEW,
    PERMISSIONS.ANALYTICS_EXPORT,
    PERMISSIONS.ANALYTICS_ADVANCED,
    PERMISSIONS.AI_USE,
    PERMISSIONS.REPORT_VIEW,
    PERMISSIONS.REPORT_CREATE,
    PERMISSIONS.REPORT_EXPORT,
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
