"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
  Shield,
  Users,
  Key,
  Plus,
  Edit,
  Trash,
  Search,
  UserPlus,
  Settings,
  CheckCircle,
  XCircle,
  Crown,
  User as UserIcon,
  Building,
  Lock,
  RefreshCw,
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
  description: string;
  isSystemRole: boolean;
  permissions: string[];
  userCount: number;
}

interface UserWithRoles {
  id: string;
  email: string;
  name: string;
  roles: string[];
  isActive: boolean;
  lastLogin: string | null;
  createdAt: string;
}

// Mock Data
const mockPermissions: Permission[] = [
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

const mockRoles: Role[] = [
  {
    id: "role-1",
    name: "admin",
    description: "Full system access - can manage users, roles, and all data",
    isSystemRole: true,
    permissions: mockPermissions.map((p) => p.name),
    userCount: 3,
  },
  {
    id: "role-2",
    name: "provider",
    description: "Clinical data access - can view and modify patient data",
    isSystemRole: true,
    permissions: [
      "documents:read", "documents:write",
      "patients:read", "patients:write",
      "billing:read",
      "coding:read",
      "vocabulary:read",
      "graphs:read", "graphs:write",
      "export:write",
      "llm:read", "llm:write",
    ],
    userCount: 15,
  },
  {
    id: "role-3",
    name: "biller",
    description: "Billing and coding access - can manage billing codes and HCC analysis",
    isSystemRole: true,
    permissions: [
      "documents:read",
      "patients:read",
      "billing:read", "billing:write",
      "coding:read", "coding:write",
      "vocabulary:read",
      "export:write",
    ],
    userCount: 8,
  },
  {
    id: "role-4",
    name: "viewer",
    description: "Read-only access - can view non-sensitive data",
    isSystemRole: true,
    permissions: [
      "documents:read",
      "vocabulary:read",
      "graphs:read",
    ],
    userCount: 12,
  },
  {
    id: "role-5",
    name: "quality_analyst",
    description: "Quality measures access - can view and analyze quality metrics",
    isSystemRole: false,
    permissions: [
      "documents:read",
      "patients:read",
      "billing:read",
      "vocabulary:read",
      "graphs:read",
      "export:write",
    ],
    userCount: 4,
  },
];

const mockUsers: UserWithRoles[] = [
  {
    id: "user-001",
    email: "admin@hospital.org",
    name: "Admin User",
    roles: ["admin"],
    isActive: true,
    lastLogin: "2026-01-19T14:32:00Z",
    createdAt: "2025-01-15T10:00:00Z",
  },
  {
    id: "user-002",
    email: "dr.smith@hospital.org",
    name: "Dr. John Smith",
    roles: ["provider"],
    isActive: true,
    lastLogin: "2026-01-19T13:45:00Z",
    createdAt: "2025-02-20T09:30:00Z",
  },
  {
    id: "user-003",
    email: "mary.johnson@hospital.org",
    name: "Mary Johnson",
    roles: ["biller"],
    isActive: true,
    lastLogin: "2026-01-19T12:15:00Z",
    createdAt: "2025-03-10T14:00:00Z",
  },
  {
    id: "user-004",
    email: "dr.davis@hospital.org",
    name: "Dr. Sarah Davis",
    roles: ["provider", "quality_analyst"],
    isActive: true,
    lastLogin: "2026-01-19T11:30:00Z",
    createdAt: "2025-04-05T11:00:00Z",
  },
  {
    id: "user-005",
    email: "bob.williams@hospital.org",
    name: "Bob Williams",
    roles: ["viewer"],
    isActive: true,
    lastLogin: "2026-01-18T16:00:00Z",
    createdAt: "2025-05-12T08:30:00Z",
  },
  {
    id: "user-006",
    email: "lisa.brown@hospital.org",
    name: "Lisa Brown",
    roles: ["biller", "viewer"],
    isActive: false,
    lastLogin: "2025-12-15T10:00:00Z",
    createdAt: "2025-06-01T13:00:00Z",
  },
];

// Helper functions
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

const getRoleIcon = (role: string) => {
  switch (role) {
    case "admin":
      return <Crown className="h-4 w-4" />;
    case "provider":
      return <UserIcon className="h-4 w-4" />;
    case "biller":
      return <Building className="h-4 w-4" />;
    case "viewer":
      return <UserIcon className="h-4 w-4" />;
    default:
      return <Key className="h-4 w-4" />;
  }
};

const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString();
};

const formatDateTime = (dateString: string | null): string => {
  if (!dateString) return "Never";
  return new Date(dateString).toLocaleString();
};

const getResourceTypes = (permissions: Permission[]): string[] => {
  return [...new Set(permissions.map((p) => p.resource))];
};

export default function AccessControlPage() {
  const [roles, setRoles] = useState<Role[]>(mockRoles);
  const [users] = useState<UserWithRoles[]>(mockUsers);
  const [permissions] = useState<Permission[]>(mockPermissions);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [isRoleDialogOpen, setIsRoleDialogOpen] = useState(false);
  const [isInviteDialogOpen, setIsInviteDialogOpen] = useState(false);
  const [newRoleName, setNewRoleName] = useState("");
  const [newRoleDescription, setNewRoleDescription] = useState("");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRoles, setInviteRoles] = useState<string[]>([]);

  const resourceTypes = getResourceTypes(permissions);

  const filteredUsers = users.filter(
    (u) =>
      searchQuery === "" ||
      u.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const refreshData = async () => {
    setIsLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsLoading(false);
  };

  const openRoleDialog = (role?: Role) => {
    if (role) {
      setSelectedRole(role);
      setNewRoleName(role.name);
      setNewRoleDescription(role.description);
      setSelectedPermissions(role.permissions);
    } else {
      setSelectedRole(null);
      setNewRoleName("");
      setNewRoleDescription("");
      setSelectedPermissions([]);
    }
    setIsRoleDialogOpen(true);
  };

  const handleSaveRole = () => {
    if (selectedRole) {
      // Update existing role
      setRoles(
        roles.map((r) =>
          r.id === selectedRole.id
            ? { ...r, description: newRoleDescription, permissions: selectedPermissions }
            : r
        )
      );
    } else {
      // Create new role
      const newRole: Role = {
        id: `role-${Date.now()}`,
        name: newRoleName.toLowerCase().replace(/\s+/g, "_"),
        description: newRoleDescription,
        isSystemRole: false,
        permissions: selectedPermissions,
        userCount: 0,
      };
      setRoles([...roles, newRole]);
    }
    setIsRoleDialogOpen(false);
  };

  const handleDeleteRole = (roleId: string) => {
    const role = roles.find((r) => r.id === roleId);
    if (role?.isSystemRole) {
      alert("System roles cannot be deleted");
      return;
    }
    setRoles(roles.filter((r) => r.id !== roleId));
  };

  const togglePermission = (permName: string) => {
    if (selectedPermissions.includes(permName)) {
      setSelectedPermissions(selectedPermissions.filter((p) => p !== permName));
    } else {
      setSelectedPermissions([...selectedPermissions, permName]);
    }
  };

  const toggleResourcePermissions = (resource: string) => {
    const resourcePerms = permissions
      .filter((p) => p.resource === resource)
      .map((p) => p.name);
    const allSelected = resourcePerms.every((p) => selectedPermissions.includes(p));

    if (allSelected) {
      setSelectedPermissions(selectedPermissions.filter((p) => !resourcePerms.includes(p)));
    } else {
      setSelectedPermissions([
        ...selectedPermissions,
        ...resourcePerms.filter((p) => !selectedPermissions.includes(p)),
      ]);
    }
  };

  const handleInviteUser = () => {
    console.log("Invite user:", inviteEmail, inviteRoles);
    setIsInviteDialogOpen(false);
    setInviteEmail("");
    setInviteRoles([]);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Shield className="h-6 w-6" />
            Access Control
          </h1>
          <p className="text-muted-foreground">
            Manage users, roles, and permissions for the application
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
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Users</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{users.length}</div>
            <p className="text-xs text-muted-foreground">
              {users.filter((u) => u.isActive).length} active
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Roles</CardTitle>
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

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Admin Users</CardTitle>
            <Crown className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {users.filter((u) => u.roles.includes("admin")).length}
            </div>
            <p className="text-xs text-muted-foreground">Full access users</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs defaultValue="users" className="space-y-4">
        <TabsList>
          <TabsTrigger value="users" className="gap-2">
            <Users className="h-4 w-4" />
            Users
          </TabsTrigger>
          <TabsTrigger value="roles" className="gap-2">
            <Key className="h-4 w-4" />
            Roles
          </TabsTrigger>
          <TabsTrigger value="permissions" className="gap-2">
            <Lock className="h-4 w-4" />
            Permissions Matrix
          </TabsTrigger>
        </TabsList>

        {/* Users Tab */}
        <TabsContent value="users" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>User Management</CardTitle>
                  <CardDescription>
                    Manage user accounts and role assignments
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <div className="relative">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search users..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-8 w-[200px]"
                    />
                  </div>
                  <Dialog open={isInviteDialogOpen} onOpenChange={setIsInviteDialogOpen}>
                    <DialogTrigger asChild>
                      <Button size="sm">
                        <UserPlus className="mr-2 h-4 w-4" />
                        Invite User
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Invite New User</DialogTitle>
                        <DialogDescription>
                          Send an invitation to a new user to join the system
                        </DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4 py-4">
                        <div className="space-y-2">
                          <Label htmlFor="invite-email">Email Address</Label>
                          <Input
                            id="invite-email"
                            type="email"
                            placeholder="user@hospital.org"
                            value={inviteEmail}
                            onChange={(e) => setInviteEmail(e.target.value)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Assign Roles</Label>
                          <div className="grid gap-2">
                            {roles.map((role) => (
                              <div
                                key={role.id}
                                className="flex items-center space-x-2"
                              >
                                <Checkbox
                                  id={`invite-role-${role.id}`}
                                  checked={inviteRoles.includes(role.name)}
                                  onCheckedChange={(checked) => {
                                    if (checked) {
                                      setInviteRoles([...inviteRoles, role.name]);
                                    } else {
                                      setInviteRoles(
                                        inviteRoles.filter((r) => r !== role.name)
                                      );
                                    }
                                  }}
                                />
                                <Label
                                  htmlFor={`invite-role-${role.id}`}
                                  className="flex items-center gap-2"
                                >
                                  <Badge className={getRoleColor(role.name)}>
                                    {role.name}
                                  </Badge>
                                  <span className="text-sm text-muted-foreground">
                                    {role.description}
                                  </span>
                                </Label>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                      <DialogFooter>
                        <Button
                          variant="outline"
                          onClick={() => setIsInviteDialogOpen(false)}
                        >
                          Cancel
                        </Button>
                        <Button onClick={handleInviteUser}>
                          Send Invitation
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Roles</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Last Login</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredUsers.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell>
                        <div>
                          <div className="font-medium">{user.name}</div>
                          <div className="text-sm text-muted-foreground">
                            {user.email}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {user.roles.map((role) => (
                            <Badge
                              key={role}
                              className={`gap-1 ${getRoleColor(role)}`}
                            >
                              {getRoleIcon(role)}
                              {role}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell>
                        {user.isActive ? (
                          <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                            <CheckCircle className="mr-1 h-3 w-3" />
                            Active
                          </Badge>
                        ) : (
                          <Badge className="bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200">
                            <XCircle className="mr-1 h-3 w-3" />
                            Inactive
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-sm">
                        {formatDateTime(user.lastLogin)}
                      </TableCell>
                      <TableCell className="text-sm">
                        {formatDate(user.createdAt)}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button variant="outline" size="sm">
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button variant="outline" size="sm">
                            <Settings className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Roles Tab */}
        <TabsContent value="roles" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Role Management</CardTitle>
                  <CardDescription>
                    Create and manage roles with specific permissions
                  </CardDescription>
                </div>
                <Dialog open={isRoleDialogOpen} onOpenChange={setIsRoleDialogOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm" onClick={() => openRoleDialog()}>
                      <Plus className="mr-2 h-4 w-4" />
                      Create Role
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
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
                    <div className="space-y-4 py-4">
                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                          <Label htmlFor="role-name">Role Name</Label>
                          <Input
                            id="role-name"
                            placeholder="custom_role"
                            value={newRoleName}
                            onChange={(e) => setNewRoleName(e.target.value)}
                            disabled={selectedRole?.isSystemRole}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="role-description">Description</Label>
                          <Input
                            id="role-description"
                            placeholder="Role description..."
                            value={newRoleDescription}
                            onChange={(e) => setNewRoleDescription(e.target.value)}
                          />
                        </div>
                      </div>

                      <div className="space-y-2">
                        <Label>Permissions</Label>
                        <div className="border rounded-lg p-4 space-y-4 max-h-[300px] overflow-y-auto">
                          {resourceTypes.map((resource) => {
                            const resourcePerms = permissions.filter(
                              (p) => p.resource === resource
                            );
                            const allSelected = resourcePerms.every((p) =>
                              selectedPermissions.includes(p.name)
                            );
                            const someSelected = resourcePerms.some((p) =>
                              selectedPermissions.includes(p.name)
                            );

                            return (
                              <div key={resource} className="space-y-2">
                                <div className="flex items-center space-x-2 border-b pb-2">
                                  <Checkbox
                                    id={`resource-${resource}`}
                                    checked={allSelected}
                                    // @ts-expect-error - indeterminate is valid but not typed
                                    indeterminate={someSelected && !allSelected}
                                    onCheckedChange={() =>
                                      toggleResourcePermissions(resource)
                                    }
                                  />
                                  <Label
                                    htmlFor={`resource-${resource}`}
                                    className="font-medium capitalize"
                                  >
                                    {resource}
                                  </Label>
                                </div>
                                <div className="grid gap-2 pl-6">
                                  {resourcePerms.map((perm) => (
                                    <div
                                      key={perm.id}
                                      className="flex items-center space-x-2"
                                    >
                                      <Checkbox
                                        id={`perm-${perm.id}`}
                                        checked={selectedPermissions.includes(
                                          perm.name
                                        )}
                                        onCheckedChange={() =>
                                          togglePermission(perm.name)
                                        }
                                      />
                                      <Label
                                        htmlFor={`perm-${perm.id}`}
                                        className="text-sm"
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
                      <Button onClick={handleSaveRole}>
                        {selectedRole ? "Update Role" : "Create Role"}
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {roles.map((role) => (
                  <div
                    key={role.id}
                    className="flex items-start justify-between p-4 border rounded-lg"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <Badge className={`gap-1 ${getRoleColor(role.name)}`}>
                          {getRoleIcon(role.name)}
                          {role.name}
                        </Badge>
                        {role.isSystemRole && (
                          <Badge variant="outline">System Role</Badge>
                        )}
                        <Badge variant="secondary">
                          {role.userCount} users
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {role.description}
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {role.permissions.slice(0, 5).map((perm) => (
                          <code
                            key={perm}
                            className="text-xs bg-muted px-1.5 py-0.5 rounded"
                          >
                            {perm}
                          </code>
                        ))}
                        {role.permissions.length > 5 && (
                          <span className="text-xs text-muted-foreground">
                            +{role.permissions.length - 5} more
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openRoleDialog(role)}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      {!role.isSystemRole && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDeleteRole(role.id)}
                        >
                          <Trash className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Permissions Matrix Tab */}
        <TabsContent value="permissions" className="space-y-4">
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
                      <TableHead className="sticky left-0 bg-background">
                        Permission
                      </TableHead>
                      {roles.map((role) => (
                        <TableHead key={role.id} className="text-center">
                          <Badge className={getRoleColor(role.name)}>
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
        </TabsContent>
      </Tabs>
    </div>
  );
}
