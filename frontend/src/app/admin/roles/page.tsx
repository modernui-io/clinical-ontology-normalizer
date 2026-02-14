"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Key,
  Plus,
  Edit,
  Trash,
  Copy,
  RefreshCw,
  Shield,
  Users,
  Lock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Crown,
  User as UserIcon,
  Building,
  Eye,
  Search,
  Loader2,
} from "lucide-react";

// Types
interface Permission {
  id: string;
  name: string;
  resource: string;
  action: string;
  description: string;
}

interface Role {
  id: string;
  name: string;
  displayName: string;
  description: string;
  isSystemRole: boolean;
  permissions: string[];
  userCount: number;
  createdAt: string;
  updatedAt: string;
}

// Backend API response shape (snake_case)
interface RoleApiResponse {
  id: string;
  name: string;
  description: string | null;
  is_system_role: boolean;
  permissions: string[];
  user_count: number;
}

// Permission catalog - these are the known permissions in the system.
// The backend roles endpoint returns permission names (strings) for each role;
// this catalog provides display metadata for the permission matrix UI.
const permissionCatalog: Permission[] = [
  { id: "p1", name: "documents:read", resource: "documents", action: "read", description: "View clinical documents" },
  { id: "p2", name: "documents:write", resource: "documents", action: "write", description: "Create and edit clinical documents" },
  { id: "p3", name: "documents:delete", resource: "documents", action: "delete", description: "Delete clinical documents" },
  { id: "p4", name: "patients:read", resource: "patients", action: "read", description: "View patient information" },
  { id: "p5", name: "patients:write", resource: "patients", action: "write", description: "Create and edit patient records" },
  { id: "p6", name: "patients:delete", resource: "patients", action: "delete", description: "Delete patient records" },
  { id: "p7", name: "billing:read", resource: "billing", action: "read", description: "View billing information" },
  { id: "p8", name: "billing:write", resource: "billing", action: "write", description: "Create and edit billing records" },
  { id: "p9", name: "coding:read", resource: "coding", action: "read", description: "View medical codes" },
  { id: "p10", name: "coding:write", resource: "coding", action: "write", description: "Assign and modify codes" },
  { id: "p11", name: "audit:read", resource: "audit", action: "read", description: "View audit logs" },
  { id: "p12", name: "audit:export", resource: "audit", action: "export", description: "Export audit logs" },
  { id: "p13", name: "admin:manage_users", resource: "admin", action: "manage_users", description: "Manage user accounts" },
  { id: "p14", name: "admin:manage_roles", resource: "admin", action: "manage_roles", description: "Manage roles and permissions" },
  { id: "p15", name: "vocabulary:read", resource: "vocabulary", action: "read", description: "Search and view vocabulary terms" },
  { id: "p16", name: "graphs:read", resource: "graphs", action: "read", description: "View knowledge graphs" },
  { id: "p17", name: "graphs:write", resource: "graphs", action: "write", description: "Modify knowledge graphs" },
  { id: "p18", name: "export:write", resource: "export", action: "write", description: "Create export jobs" },
  { id: "p19", name: "llm:read", resource: "llm", action: "read", description: "Use LLM features (read)" },
  { id: "p20", name: "llm:write", resource: "llm", action: "write", description: "Use LLM features (generate)" },
];

/** Convert a backend RoleApiResponse (snake_case) to the frontend Role shape (camelCase). */
function mapApiRoleToRole(apiRole: RoleApiResponse): Role {
  // Generate a display name from the role name (e.g., "quality_analyst" -> "Quality Analyst")
  const displayName = apiRole.name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

  return {
    id: apiRole.id,
    name: apiRole.name,
    displayName,
    description: apiRole.description ?? "",
    isSystemRole: apiRole.is_system_role,
    permissions: apiRole.permissions,
    userCount: apiRole.user_count,
    // The backend RoleResponse does not include timestamps; use empty strings as fallback
    createdAt: "",
    updatedAt: "",
  };
}

// Helper functions
const getRoleIcon = (role: string) => {
  switch (role) {
    case "admin":
      return <Crown className="h-4 w-4" />;
    case "provider":
      return <UserIcon className="h-4 w-4" />;
    case "biller":
      return <Building className="h-4 w-4" />;
    case "viewer":
      return <Eye className="h-4 w-4" />;
    default:
      return <Key className="h-4 w-4" />;
  }
};

const getRoleColor = (role: string): string => {
  switch (role) {
    case "admin":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    case "provider":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "biller":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "viewer":
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
    default:
      return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
  }
};

const getResourceTypes = (permissions: Permission[]): string[] => {
  return [...new Set(permissions.map((p) => p.resource))];
};

const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString();
};

export default function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions] = useState<Permission[]>(permissionCatalog);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isRoleDialogOpen, setIsRoleDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [roleToDelete, setRoleToDelete] = useState<Role | null>(null);

  // Form state
  const [formName, setFormName] = useState("");
  const [formDisplayName, setFormDisplayName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formPermissions, setFormPermissions] = useState<string[]>([]);

  const resourceTypes = getResourceTypes(permissions);

  // Fetch roles from backend API
  const fetchRoles = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/users/roles/all");
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`Failed to fetch roles: ${res.status} ${detail}`);
      }
      const data: RoleApiResponse[] = await res.json();
      setRoles(data.map(mapApiRoleToRole));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error loading roles";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load roles on mount
  useEffect(() => {
    fetchRoles();
  }, [fetchRoles]);

  // Filter roles
  const filteredRoles = roles.filter((role) =>
    searchQuery === "" ||
    role.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    role.displayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
    role.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const refreshData = async () => {
    await fetchRoles();
  };

  const openCreateDialog = () => {
    setSelectedRole(null);
    setFormName("");
    setFormDisplayName("");
    setFormDescription("");
    setFormPermissions([]);
    setIsRoleDialogOpen(true);
  };

  const openEditDialog = (role: Role) => {
    setSelectedRole(role);
    setFormName(role.name);
    setFormDisplayName(role.displayName);
    setFormDescription(role.description);
    setFormPermissions([...role.permissions]);
    setIsRoleDialogOpen(true);
  };

  const openCloneDialog = (role: Role) => {
    setSelectedRole(null);
    setFormName(`${role.name}_copy`);
    setFormDisplayName(`${role.displayName} (Copy)`);
    setFormDescription(role.description);
    setFormPermissions([...role.permissions]);
    setIsRoleDialogOpen(true);
  };

  const handleSaveRole = async () => {
    setIsSaving(true);
    try {
      if (selectedRole) {
        // Backend does not currently have a PATCH/PUT endpoint for updating roles.
        // For now, apply the update optimistically on the client side and re-fetch.
        // TODO: Wire to PUT /api/users/roles/{name} once the backend supports it.
        setRoles(
          roles.map((r) =>
            r.id === selectedRole.id
              ? {
                  ...r,
                  displayName: formDisplayName,
                  description: formDescription,
                  permissions: formPermissions,
                  updatedAt: new Date().toISOString(),
                }
              : r
          )
        );
      } else {
        // Create new role via backend
        const res = await fetch("/api/users/roles", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: formName.toLowerCase().replace(/\s+/g, "_"),
            description: formDescription,
            permissions: formPermissions,
          }),
        });
        if (!res.ok) {
          const detail = await res.text();
          throw new Error(`Failed to create role: ${res.status} ${detail}`);
        }
        // Refresh to get the canonical state from the backend
        await fetchRoles();
      }
      setIsRoleDialogOpen(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save role";
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteRole = async () => {
    if (!roleToDelete) return;
    setIsSaving(true);
    try {
      const res = await fetch(`/api/users/roles/${encodeURIComponent(roleToDelete.name)}`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        const detail = await res.text();
        throw new Error(`Failed to delete role: ${res.status} ${detail}`);
      }
      // Refresh roles list from backend
      await fetchRoles();
      setRoleToDelete(null);
      setIsDeleteDialogOpen(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete role";
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const togglePermission = (permName: string) => {
    if (formPermissions.includes(permName)) {
      setFormPermissions(formPermissions.filter((p) => p !== permName));
    } else {
      setFormPermissions([...formPermissions, permName]);
    }
  };

  const toggleResourcePermissions = (resource: string) => {
    const resourcePerms = permissions
      .filter((p) => p.resource === resource)
      .map((p) => p.name);
    const allSelected = resourcePerms.every((p) => formPermissions.includes(p));

    if (allSelected) {
      setFormPermissions(formPermissions.filter((p) => !resourcePerms.includes(p)));
    } else {
      setFormPermissions([
        ...formPermissions,
        ...resourcePerms.filter((p) => !formPermissions.includes(p)),
      ]);
    }
  };

  const totalUsers = roles.reduce((sum, r) => sum + r.userCount, 0);

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Key className="h-6 w-6" />
            Role Management
          </h1>
          <p className="text-muted-foreground">
            Create and manage roles with specific permissions
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={refreshData}
            disabled={isLoading}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          <Button size="sm" onClick={openCreateDialog}>
            <Plus className="mr-2 h-4 w-4" />
            Create Role
          </Button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-950">
          <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 shrink-0" />
          <div className="flex-1">
            <h5 className="font-medium text-red-800 dark:text-red-200">Error</h5>
            <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setError(null)}>
            <XCircle className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Initial Loading State */}
      {isLoading && roles.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-muted-foreground">Loading roles...</p>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Roles</CardTitle>
            <Key className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{roles.length}</div>
            <p className="text-xs text-muted-foreground">
              {roles.filter((r) => r.isSystemRole).length} system roles
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Custom Roles</CardTitle>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {roles.filter((r) => !r.isSystemRole).length}
            </div>
            <p className="text-xs text-muted-foreground">User-created roles</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Users</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalUsers}</div>
            <p className="text-xs text-muted-foreground">Across all roles</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Permissions</CardTitle>
            <Lock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{permissions.length}</div>
            <p className="text-xs text-muted-foreground">
              Across {resourceTypes.length} resources
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <Card>
        <CardContent className="pt-6">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search roles..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8"
            />
          </div>
        </CardContent>
      </Card>

      {/* Roles List */}
      <div className="space-y-4">
        {!isLoading && roles.length === 0 && !error && (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12 gap-3">
              <Shield className="h-10 w-10 text-muted-foreground" />
              <p className="text-muted-foreground">No roles found. Create a role to get started.</p>
            </CardContent>
          </Card>
        )}
        {filteredRoles.map((role) => (
          <Card key={role.id}>
            <CardContent className="pt-6">
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <Badge className={`gap-1 ${getRoleColor(role.name)}`}>
                      {getRoleIcon(role.name)}
                      {role.name}
                    </Badge>
                    {role.isSystemRole && (
                      <Badge variant="outline">System Role</Badge>
                    )}
                    <Badge variant="secondary">
                      <Users className="mr-1 h-3 w-3" />
                      {role.userCount} users
                    </Badge>
                  </div>

                  <h3 className="text-lg font-semibold">{role.displayName}</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    {role.description}
                  </p>

                  <div className="mt-4">
                    <h4 className="text-sm font-medium mb-2">Permissions ({role.permissions.length})</h4>
                    <div className="flex flex-wrap gap-1">
                      {role.permissions.slice(0, 8).map((perm) => (
                        <code
                          key={perm}
                          className="text-xs bg-muted px-1.5 py-0.5 rounded"
                        >
                          {perm}
                        </code>
                      ))}
                      {role.permissions.length > 8 && (
                        <span className="text-xs text-muted-foreground">
                          +{role.permissions.length - 8} more
                        </span>
                      )}
                    </div>
                  </div>

                  {(role.createdAt || role.updatedAt) && (
                    <div className="flex gap-4 mt-4 text-xs text-muted-foreground">
                      {role.createdAt && <span>Created: {formatDate(role.createdAt)}</span>}
                      {role.updatedAt && <span>Updated: {formatDate(role.updatedAt)}</span>}
                    </div>
                  )}
                </div>

                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openEditDialog(role)}
                  >
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openCloneDialog(role)}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                  {!role.isSystemRole && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setRoleToDelete(role);
                        setIsDeleteDialogOpen(true);
                      }}
                      disabled={role.userCount > 0}
                    >
                      <Trash className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Create/Edit Role Dialog */}
      <Dialog open={isRoleDialogOpen} onOpenChange={setIsRoleDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {selectedRole ? "Edit Role" : "Create New Role"}
            </DialogTitle>
            <DialogDescription>
              {selectedRole
                ? "Update the role configuration and permissions"
                : "Define a new role with specific permissions"}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="role-name">Role Name (ID)</Label>
                <Input
                  id="role-name"
                  placeholder="custom_role"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  disabled={selectedRole?.isSystemRole}
                />
                <p className="text-xs text-muted-foreground">
                  Lowercase letters and underscores only
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="role-display-name">Display Name</Label>
                <Input
                  id="role-display-name"
                  placeholder="Custom Role"
                  value={formDisplayName}
                  onChange={(e) => setFormDisplayName(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="role-description">Description</Label>
              <Textarea
                id="role-description"
                placeholder="Describe what this role is for..."
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                rows={2}
              />
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label>Permissions ({formPermissions.length} selected)</Label>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setFormPermissions(permissions.map((p) => p.name))}
                  >
                    Select All
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setFormPermissions([])}
                  >
                    Clear All
                  </Button>
                </div>
              </div>

              <div className="border rounded-lg p-4 space-y-4 max-h-[300px] overflow-y-auto">
                {resourceTypes.map((resource) => {
                  const resourcePerms = permissions.filter(
                    (p) => p.resource === resource
                  );
                  const allSelected = resourcePerms.every((p) =>
                    formPermissions.includes(p.name)
                  );
                  const someSelected = resourcePerms.some((p) =>
                    formPermissions.includes(p.name)
                  );

                  return (
                    <div key={resource} className="space-y-2">
                      <div className="flex items-center space-x-2 border-b pb-2">
                        <Checkbox
                          id={`resource-${resource}`}
                          checked={allSelected}
                          onCheckedChange={() => toggleResourcePermissions(resource)}
                        />
                        <Label
                          htmlFor={`resource-${resource}`}
                          className="font-medium capitalize cursor-pointer"
                        >
                          {resource}
                        </Label>
                        <Badge variant="outline" className="ml-auto">
                          {resourcePerms.filter((p) =>
                            formPermissions.includes(p.name)
                          ).length}
                          /{resourcePerms.length}
                        </Badge>
                      </div>
                      <div className="grid gap-2 pl-6">
                        {resourcePerms.map((perm) => (
                          <div
                            key={perm.id}
                            className="flex items-center space-x-2"
                          >
                            <Checkbox
                              id={`perm-${perm.id}`}
                              checked={formPermissions.includes(perm.name)}
                              onCheckedChange={() => togglePermission(perm.name)}
                            />
                            <Label
                              htmlFor={`perm-${perm.id}`}
                              className="text-sm cursor-pointer flex-1"
                            >
                              <code className="bg-muted px-1 rounded text-xs">
                                {perm.action}
                              </code>
                              <span className="ml-2 text-muted-foreground">
                                {perm.description}
                              </span>
                            </Label>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsRoleDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveRole}
              disabled={!formName || !formDisplayName || isSaving}
            >
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {selectedRole ? "Update Role" : "Create Role"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Role</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete the role &quot;{roleToDelete?.displayName}&quot;?
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>

          {roleToDelete?.userCount && roleToDelete.userCount > 0 && (
            <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950">
              <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
              <div>
                <h5 className="font-medium text-amber-800 dark:text-amber-200">
                  Users Assigned
                </h5>
                <p className="text-sm text-amber-700 dark:text-amber-300">
                  This role has {roleToDelete.userCount} user(s) assigned. You must
                  reassign or remove these users before deleting the role.
                </p>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsDeleteDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteRole}
              disabled={isSaving || (roleToDelete?.userCount ? roleToDelete.userCount > 0 : false)}
            >
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete Role
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Permission Matrix */}
      <Card>
        <CardHeader>
          <CardTitle>Permission Matrix</CardTitle>
          <CardDescription>
            Overview of permissions assigned to each role
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="sticky left-0 bg-background min-w-[200px]">
                    Permission
                  </TableHead>
                  {roles.map((role) => (
                    <TableHead key={role.id} className="text-center min-w-[100px]">
                      <Badge className={`text-xs ${getRoleColor(role.name)}`}>
                        {role.name}
                      </Badge>
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {resourceTypes.map((resource) => (
                  <>
                    <TableRow key={resource} className="bg-muted/50">
                      <TableCell
                        colSpan={roles.length + 1}
                        className="font-medium capitalize"
                      >
                        {resource}
                      </TableCell>
                    </TableRow>
                    {permissions
                      .filter((p) => p.resource === resource)
                      .map((perm) => (
                        <TableRow key={perm.id}>
                          <TableCell className="sticky left-0 bg-background">
                            <div>
                              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                {perm.name}
                              </code>
                              <p className="text-xs text-muted-foreground mt-1">
                                {perm.description}
                              </p>
                            </div>
                          </TableCell>
                          {roles.map((role) => (
                            <TableCell key={role.id} className="text-center">
                              {role.permissions.includes(perm.name) ? (
                                <CheckCircle className="h-5 w-5 text-green-600 mx-auto" />
                              ) : (
                                <XCircle className="h-5 w-5 text-gray-300 mx-auto" />
                              )}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))}
                  </>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
