/**
 * Tests for usePermissions hook and PermissionGate component.
 *
 * Tests:
 * - Permission checking (single, all, any)
 * - Role checking
 * - PermissionGate conditional rendering
 * - Role-based permission expansion
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import {
  usePermissions,
  PermissionGate,
  PERMISSIONS,
  ROLES,
  ROLE_PERMISSIONS,
  getPermissionDisplayName,
  getRoleDisplayName,
  groupPermissionsByDomain,
  withPermission,
} from "@/hooks/use-permissions";
import { AuthProvider, type User } from "@/hooks/use-auth";

// Mock the auth hook
const mockUser: User = {
  id: "user-123",
  email: "test@example.com",
  name: "Test User",
  roles: ["provider"],
  permissions: ["custom:permission"],
};

// Create wrapper with AuthProvider
const createWrapper =
  (user: User | null) =>
  ({ children }: { children: React.ReactNode }) => {
    // Mock the auth context
    return (
      <MockAuthContext user={user}>
        {children}
      </MockAuthContext>
    );
  };

// Mock auth context component
function MockAuthContext({ children, user }: { children: React.ReactNode; user: User | null }) {
  // Create a simple mock context
  const React = require("react");

  // We need to mock useAuth directly in the module
  jest.doMock("@/hooks/use-auth", () => ({
    useAuth: () => ({
      user,
      isAuthenticated: !!user,
      isLoading: false,
      error: null,
      login: jest.fn(),
      logout: jest.fn(),
      register: jest.fn(),
      updateProfile: jest.fn(),
      changePassword: jest.fn(),
      forgotPassword: jest.fn(),
      clearError: jest.fn(),
    }),
  }));

  return <>{children}</>;
}

// Test component that uses the hook
function TestPermissionsComponent({ user }: { user: User | null }) {
  // Mock useAuth to return the user
  jest.spyOn(require("@/hooks/use-auth"), "useAuth").mockReturnValue({
    user,
    isAuthenticated: !!user,
    isLoading: false,
    error: null,
    login: jest.fn(),
    logout: jest.fn(),
    register: jest.fn(),
    updateProfile: jest.fn(),
    changePassword: jest.fn(),
    forgotPassword: jest.fn(),
    clearError: jest.fn(),
  });

  const permissions = usePermissions();

  return (
    <div>
      <span data-testid="has-documents-read">
        {permissions.hasPermission(PERMISSIONS.DOCUMENTS_READ) ? "yes" : "no"}
      </span>
      <span data-testid="has-admin-read">
        {permissions.hasPermission(PERMISSIONS.ADMIN_READ) ? "yes" : "no"}
      </span>
      <span data-testid="is-admin">{permissions.isAdmin ? "yes" : "no"}</span>
      <span data-testid="all-permissions-count">{permissions.allPermissions.length}</span>
    </div>
  );
}

// Mock useAuth for all tests
jest.mock("@/hooks/use-auth", () => ({
  useAuth: jest.fn(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const mockUseAuth = require("@/hooks/use-auth").useAuth as jest.Mock;

describe("usePermissions Hook", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Permission checking", () => {
    it("should return false for all permissions when user is null", () => {
      mockUseAuth.mockReturnValue({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });

      const TestComponent = () => {
        const { hasPermission, allPermissions } = usePermissions();
        return (
          <div>
            <span data-testid="has-perm">
              {hasPermission(PERMISSIONS.DOCUMENTS_READ) ? "yes" : "no"}
            </span>
            <span data-testid="count">{allPermissions.length}</span>
          </div>
        );
      };

      render(<TestComponent />);

      expect(screen.getByTestId("has-perm")).toHaveTextContent("no");
      expect(screen.getByTestId("count")).toHaveTextContent("0");
    });

    it("should include role-based permissions", () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: "user-123",
          email: "test@example.com",
          name: "Test User",
          roles: ["provider"],
          permissions: [],
        },
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });

      const TestComponent = () => {
        const { hasPermission, allPermissions } = usePermissions();
        return (
          <div>
            <span data-testid="has-documents-read">
              {hasPermission(PERMISSIONS.DOCUMENTS_READ) ? "yes" : "no"}
            </span>
            <span data-testid="has-patients-read">
              {hasPermission(PERMISSIONS.PATIENTS_READ) ? "yes" : "no"}
            </span>
            <span data-testid="count">{allPermissions.length}</span>
          </div>
        );
      };

      render(<TestComponent />);

      // Provider role should have these permissions
      expect(screen.getByTestId("has-documents-read")).toHaveTextContent("yes");
      expect(screen.getByTestId("has-patients-read")).toHaveTextContent("yes");
    });

    it("should include direct permissions", () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: "user-123",
          email: "test@example.com",
          name: "Test User",
          roles: [],
          permissions: ["custom:special"],
        },
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });

      const TestComponent = () => {
        const { hasPermission, allPermissions } = usePermissions();
        return (
          <div>
            <span data-testid="has-custom">
              {hasPermission("custom:special" as any) ? "yes" : "no"}
            </span>
            <span data-testid="count">{allPermissions.length}</span>
          </div>
        );
      };

      render(<TestComponent />);

      expect(screen.getByTestId("has-custom")).toHaveTextContent("yes");
      expect(screen.getByTestId("count")).toHaveTextContent("1");
    });

    it("should check hasAllPermissions correctly", () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: "user-123",
          email: "test@example.com",
          name: "Test User",
          roles: ["provider"],
          permissions: [],
        },
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });

      const TestComponent = () => {
        const { hasAllPermissions } = usePermissions();
        return (
          <div>
            <span data-testid="has-all-provider">
              {hasAllPermissions([PERMISSIONS.DOCUMENTS_READ, PERMISSIONS.PATIENTS_READ])
                ? "yes"
                : "no"}
            </span>
            <span data-testid="has-all-with-admin">
              {hasAllPermissions([PERMISSIONS.DOCUMENTS_READ, PERMISSIONS.ADMIN_READ])
                ? "yes"
                : "no"}
            </span>
          </div>
        );
      };

      render(<TestComponent />);

      expect(screen.getByTestId("has-all-provider")).toHaveTextContent("yes");
      expect(screen.getByTestId("has-all-with-admin")).toHaveTextContent("no");
    });

    it("should check hasAnyPermission correctly", () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: "user-123",
          email: "test@example.com",
          name: "Test User",
          roles: ["viewer"],
          permissions: [],
        },
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });

      const TestComponent = () => {
        const { hasAnyPermission } = usePermissions();
        return (
          <div>
            <span data-testid="has-any-read">
              {hasAnyPermission([PERMISSIONS.DOCUMENTS_READ, PERMISSIONS.ADMIN_READ])
                ? "yes"
                : "no"}
            </span>
            <span data-testid="has-any-admin">
              {hasAnyPermission([PERMISSIONS.ADMIN_READ, PERMISSIONS.ADMIN_WRITE])
                ? "yes"
                : "no"}
            </span>
          </div>
        );
      };

      render(<TestComponent />);

      expect(screen.getByTestId("has-any-read")).toHaveTextContent("yes");
      expect(screen.getByTestId("has-any-admin")).toHaveTextContent("no");
    });
  });

  describe("Role checking", () => {
    it("should check hasRole correctly", () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: "user-123",
          email: "test@example.com",
          name: "Test User",
          roles: ["provider", "biller"],
          permissions: [],
        },
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });

      const TestComponent = () => {
        const { hasRole, hasAnyRole, isAdmin } = usePermissions();
        return (
          <div>
            <span data-testid="has-provider">{hasRole(ROLES.PROVIDER) ? "yes" : "no"}</span>
            <span data-testid="has-admin">{hasRole(ROLES.ADMIN) ? "yes" : "no"}</span>
            <span data-testid="has-any-role">
              {hasAnyRole([ROLES.ADMIN, ROLES.PROVIDER]) ? "yes" : "no"}
            </span>
            <span data-testid="is-admin">{isAdmin ? "yes" : "no"}</span>
          </div>
        );
      };

      render(<TestComponent />);

      expect(screen.getByTestId("has-provider")).toHaveTextContent("yes");
      expect(screen.getByTestId("has-admin")).toHaveTextContent("no");
      expect(screen.getByTestId("has-any-role")).toHaveTextContent("yes");
      expect(screen.getByTestId("is-admin")).toHaveTextContent("no");
    });

    it("should recognize admin role", () => {
      mockUseAuth.mockReturnValue({
        user: {
          id: "user-123",
          email: "admin@example.com",
          name: "Admin User",
          roles: ["admin"],
          permissions: [],
        },
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });

      const TestComponent = () => {
        const { isAdmin, allPermissions } = usePermissions();
        return (
          <div>
            <span data-testid="is-admin">{isAdmin ? "yes" : "no"}</span>
            <span data-testid="has-all-perms">
              {allPermissions.length === Object.values(PERMISSIONS).length ? "yes" : "no"}
            </span>
          </div>
        );
      };

      render(<TestComponent />);

      expect(screen.getByTestId("is-admin")).toHaveTextContent("yes");
      expect(screen.getByTestId("has-all-perms")).toHaveTextContent("yes");
    });
  });
});

describe("PermissionGate Component", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should render children when user has permission", () => {
    mockUseAuth.mockReturnValue({
      user: {
        id: "user-123",
        email: "test@example.com",
        name: "Test User",
        roles: ["provider"],
        permissions: [],
      },
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });

    render(
      <PermissionGate permission={PERMISSIONS.DOCUMENTS_READ}>
        <span>Protected Content</span>
      </PermissionGate>
    );

    expect(screen.getByText("Protected Content")).toBeInTheDocument();
  });

  it("should not render children when user lacks permission", () => {
    mockUseAuth.mockReturnValue({
      user: {
        id: "user-123",
        email: "test@example.com",
        name: "Test User",
        roles: ["viewer"],
        permissions: [],
      },
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });

    render(
      <PermissionGate permission={PERMISSIONS.ADMIN_READ}>
        <span>Admin Content</span>
      </PermissionGate>
    );

    expect(screen.queryByText("Admin Content")).not.toBeInTheDocument();
  });

  it("should render fallback when user lacks permission", () => {
    mockUseAuth.mockReturnValue({
      user: {
        id: "user-123",
        email: "test@example.com",
        name: "Test User",
        roles: ["viewer"],
        permissions: [],
      },
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });

    render(
      <PermissionGate
        permission={PERMISSIONS.ADMIN_READ}
        fallback={<span>Access Denied</span>}
      >
        <span>Admin Content</span>
      </PermissionGate>
    );

    expect(screen.queryByText("Admin Content")).not.toBeInTheDocument();
    expect(screen.getByText("Access Denied")).toBeInTheDocument();
  });

  it("should hide content when user is not authenticated", () => {
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });

    render(
      <PermissionGate permission={PERMISSIONS.DOCUMENTS_READ}>
        <span>Protected Content</span>
      </PermissionGate>
    );

    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });

  it("should check multiple permissions with mode='all'", () => {
    mockUseAuth.mockReturnValue({
      user: {
        id: "user-123",
        email: "test@example.com",
        name: "Test User",
        roles: ["provider"],
        permissions: [],
      },
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });

    render(
      <PermissionGate
        permission={[PERMISSIONS.DOCUMENTS_READ, PERMISSIONS.ADMIN_READ]}
        mode="all"
      >
        <span>All Permissions Required</span>
      </PermissionGate>
    );

    // Provider doesn't have admin:read, so should not render
    expect(screen.queryByText("All Permissions Required")).not.toBeInTheDocument();
  });

  it("should check multiple permissions with mode='any'", () => {
    mockUseAuth.mockReturnValue({
      user: {
        id: "user-123",
        email: "test@example.com",
        name: "Test User",
        roles: ["provider"],
        permissions: [],
      },
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });

    render(
      <PermissionGate
        permission={[PERMISSIONS.DOCUMENTS_READ, PERMISSIONS.ADMIN_READ]}
        mode="any"
      >
        <span>Any Permission Sufficient</span>
      </PermissionGate>
    );

    // Provider has documents:read, so should render
    expect(screen.getByText("Any Permission Sufficient")).toBeInTheDocument();
  });

  it("should check role-based access", () => {
    mockUseAuth.mockReturnValue({
      user: {
        id: "user-123",
        email: "admin@example.com",
        name: "Admin User",
        roles: ["admin"],
        permissions: [],
      },
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });

    render(
      <PermissionGate role={ROLES.ADMIN}>
        <span>Admin Only</span>
      </PermissionGate>
    );

    expect(screen.getByText("Admin Only")).toBeInTheDocument();
  });
});

describe("Utility Functions", () => {
  describe("getPermissionDisplayName", () => {
    it("should format permission names correctly", () => {
      expect(getPermissionDisplayName("documents:read")).toBe("Documents - Read");
      expect(getPermissionDisplayName("admin:manage_users")).toBe("Admin - Manage_users");
    });
  });

  describe("getRoleDisplayName", () => {
    it("should format role names correctly", () => {
      expect(getRoleDisplayName("admin")).toBe("Admin");
      expect(getRoleDisplayName("provider")).toBe("Provider");
    });
  });

  describe("groupPermissionsByDomain", () => {
    it("should group permissions by domain", () => {
      const grouped = groupPermissionsByDomain();

      expect(grouped.documents).toContain(PERMISSIONS.DOCUMENTS_READ);
      expect(grouped.documents).toContain(PERMISSIONS.DOCUMENTS_WRITE);
      expect(grouped.patients).toContain(PERMISSIONS.PATIENTS_READ);
      expect(grouped.admin).toContain(PERMISSIONS.ADMIN_READ);
    });
  });
});

describe("ROLE_PERMISSIONS constants", () => {
  it("should have admin role with all permissions", () => {
    expect(ROLE_PERMISSIONS[ROLES.ADMIN]).toEqual(Object.values(PERMISSIONS));
  });

  it("should have provider role with clinical permissions", () => {
    const providerPerms = ROLE_PERMISSIONS[ROLES.PROVIDER];
    expect(providerPerms).toContain(PERMISSIONS.DOCUMENTS_READ);
    expect(providerPerms).toContain(PERMISSIONS.PATIENTS_READ);
    expect(providerPerms).not.toContain(PERMISSIONS.ADMIN_READ);
  });

  it("should have biller role with billing permissions", () => {
    const billerPerms = ROLE_PERMISSIONS[ROLES.BILLER];
    expect(billerPerms).toContain(PERMISSIONS.BILLING_READ);
    expect(billerPerms).toContain(PERMISSIONS.BILLING_WRITE);
    expect(billerPerms).not.toContain(PERMISSIONS.ADMIN_READ);
  });

  it("should have viewer role with read-only permissions", () => {
    const viewerPerms = ROLE_PERMISSIONS[ROLES.VIEWER];
    expect(viewerPerms).toContain(PERMISSIONS.DOCUMENTS_READ);
    expect(viewerPerms).not.toContain(PERMISSIONS.DOCUMENTS_WRITE);
    expect(viewerPerms).not.toContain(PERMISSIONS.ADMIN_READ);
  });
});
