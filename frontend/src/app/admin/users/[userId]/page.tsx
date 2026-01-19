"use client";

import { useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
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
import { Switch } from "@/components/ui/switch";
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
  ArrowLeft,
  User,
  Mail,
  Calendar,
  Clock,
  Shield,
  Key,
  Activity,
  Save,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Eye,
  Edit,
  Trash,
  Upload,
  Download,
  Search,
  FileText,
  Crown,
  Building,
  Lock,
} from "lucide-react";

// Types
interface UserDetail {
  id: string;
  name: string;
  email: string;
  phone: string;
  department: string;
  role: string;
  status: "active" | "inactive" | "pending";
  lastActive: string | null;
  createdAt: string;
  updatedAt: string;
  mfaEnabled: boolean;
  loginCount: number;
  failedLoginCount: number;
}

interface UserPermission {
  id: string;
  name: string;
  resource: string;
  action: string;
  description: string;
  granted: boolean;
  source: "role" | "direct";
}

interface ActivityLogEntry {
  id: string;
  timestamp: string;
  action: string;
  resource: string;
  details: string;
  ipAddress: string;
  success: boolean;
}

// Mock Data
const getMockUser = (userId: string): UserDetail => ({
  id: userId,
  name: "Dr. John Smith",
  email: "dr.smith@hospital.org",
  phone: "+1 (555) 123-4567",
  department: "Cardiology",
  role: "provider",
  status: "active",
  lastActive: "2026-01-19T14:32:00Z",
  createdAt: "2025-02-20T09:30:00Z",
  updatedAt: "2026-01-15T16:45:00Z",
  mfaEnabled: true,
  loginCount: 245,
  failedLoginCount: 2,
});

const mockPermissions: UserPermission[] = [
  { id: "p1", name: "documents:read", resource: "documents", action: "read", description: "View clinical documents", granted: true, source: "role" },
  { id: "p2", name: "documents:write", resource: "documents", action: "write", description: "Create and edit clinical documents", granted: true, source: "role" },
  { id: "p3", name: "documents:delete", resource: "documents", action: "delete", description: "Delete clinical documents", granted: false, source: "role" },
  { id: "p4", name: "patients:read", resource: "patients", action: "read", description: "View patient information", granted: true, source: "role" },
  { id: "p5", name: "patients:write", resource: "patients", action: "write", description: "Create and edit patient records", granted: true, source: "role" },
  { id: "p6", name: "patients:delete", resource: "patients", action: "delete", description: "Delete patient records", granted: false, source: "role" },
  { id: "p7", name: "billing:read", resource: "billing", action: "read", description: "View billing information", granted: true, source: "role" },
  { id: "p8", name: "billing:write", resource: "billing", action: "write", description: "Create and edit billing records", granted: false, source: "role" },
  { id: "p9", name: "coding:read", resource: "coding", action: "read", description: "View medical codes", granted: true, source: "role" },
  { id: "p10", name: "coding:write", resource: "coding", action: "write", description: "Assign and modify codes", granted: false, source: "role" },
  { id: "p11", name: "audit:read", resource: "audit", action: "read", description: "View audit logs", granted: true, source: "direct" },
  { id: "p12", name: "graphs:read", resource: "graphs", action: "read", description: "View knowledge graphs", granted: true, source: "role" },
  { id: "p13", name: "graphs:write", resource: "graphs", action: "write", description: "Modify knowledge graphs", granted: true, source: "role" },
  { id: "p14", name: "export:write", resource: "export", action: "write", description: "Create export jobs", granted: true, source: "role" },
  { id: "p15", name: "llm:read", resource: "llm", action: "read", description: "Use LLM features (read)", granted: true, source: "role" },
  { id: "p16", name: "llm:write", resource: "llm", action: "write", description: "Use LLM features (generate)", granted: true, source: "role" },
];

const mockActivityLog: ActivityLogEntry[] = [
  { id: "a1", timestamp: "2026-01-19T14:32:00Z", action: "read", resource: "patient", details: "Viewed patient record P001", ipAddress: "192.168.1.100", success: true },
  { id: "a2", timestamp: "2026-01-19T14:28:15Z", action: "update", resource: "clinical_fact", details: "Updated clinical fact fact-123", ipAddress: "192.168.1.100", success: true },
  { id: "a3", timestamp: "2026-01-19T14:15:30Z", action: "search", resource: "patient", details: "Searched patients: diabetes", ipAddress: "192.168.1.100", success: true },
  { id: "a4", timestamp: "2026-01-19T13:45:00Z", action: "read", resource: "document", details: "Viewed discharge summary doc-456", ipAddress: "192.168.1.100", success: true },
  { id: "a5", timestamp: "2026-01-19T13:20:45Z", action: "export", resource: "report", details: "Exported patient summary report", ipAddress: "192.168.1.100", success: true },
  { id: "a6", timestamp: "2026-01-19T12:55:10Z", action: "login", resource: "session", details: "Logged in successfully", ipAddress: "192.168.1.100", success: true },
  { id: "a7", timestamp: "2026-01-18T16:45:00Z", action: "logout", resource: "session", details: "Logged out", ipAddress: "192.168.1.100", success: true },
  { id: "a8", timestamp: "2026-01-18T15:30:20Z", action: "update", resource: "patient", details: "Updated patient demographics P002", ipAddress: "192.168.1.100", success: true },
  { id: "a9", timestamp: "2026-01-18T14:10:00Z", action: "read", resource: "knowledge_graph", details: "Viewed knowledge graph for P001", ipAddress: "192.168.1.100", success: true },
  { id: "a10", timestamp: "2026-01-18T09:00:15Z", action: "login", resource: "session", details: "Login failed - invalid password", ipAddress: "192.168.1.100", success: false },
];

const availableRoles = [
  { id: "admin", name: "Admin", description: "Full system access" },
  { id: "provider", name: "Provider", description: "Clinical data access" },
  { id: "biller", name: "Biller", description: "Billing and coding access" },
  { id: "viewer", name: "Viewer", description: "Read-only access" },
  { id: "quality_analyst", name: "Quality Analyst", description: "Quality measures access" },
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
      return <User className="h-4 w-4" />;
    case "biller":
      return <Building className="h-4 w-4" />;
    case "viewer":
      return <Eye className="h-4 w-4" />;
    default:
      return <Key className="h-4 w-4" />;
  }
};

const getStatusColor = (status: string): string => {
  switch (status) {
    case "active":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "inactive":
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
    case "pending":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

const getActionIcon = (action: string) => {
  switch (action) {
    case "read":
      return <Eye className="h-4 w-4" />;
    case "update":
      return <Edit className="h-4 w-4" />;
    case "delete":
      return <Trash className="h-4 w-4" />;
    case "export":
      return <Download className="h-4 w-4" />;
    case "search":
      return <Search className="h-4 w-4" />;
    case "login":
    case "logout":
      return <User className="h-4 w-4" />;
    default:
      return <FileText className="h-4 w-4" />;
  }
};

const formatDateTime = (dateString: string | null): string => {
  if (!dateString) return "Never";
  return new Date(dateString).toLocaleString();
};

const formatTimeAgo = (dateString: string | null): string => {
  if (!dateString) return "Never";
  const now = new Date();
  const date = new Date(dateString);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
};

const getResourceTypes = (permissions: UserPermission[]): string[] => {
  return [...new Set(permissions.map((p) => p.resource))];
};

export default function UserDetailPage({
  params,
}: {
  params: Promise<{ userId: string }>;
}) {
  const { userId } = use(params);
  const router = useRouter();
  const [user, setUser] = useState<UserDetail>(getMockUser(userId));
  const [permissions, setPermissions] = useState<UserPermission[]>(mockPermissions);
  const [activityLog] = useState<ActivityLogEntry[]>(mockActivityLog);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isResetPasswordDialogOpen, setIsResetPasswordDialogOpen] = useState(false);
  const [isDeactivateDialogOpen, setIsDeactivateDialogOpen] = useState(false);

  // Form state
  const [editedName, setEditedName] = useState(user.name);
  const [editedEmail, setEditedEmail] = useState(user.email);
  const [editedPhone, setEditedPhone] = useState(user.phone);
  const [editedDepartment, setEditedDepartment] = useState(user.department);
  const [editedRole, setEditedRole] = useState(user.role);
  const [editedMfaEnabled, setEditedMfaEnabled] = useState(user.mfaEnabled);

  const resourceTypes = getResourceTypes(permissions);

  const handleSave = async () => {
    setIsSaving(true);
    await new Promise((resolve) => setTimeout(resolve, 1500));
    setUser({
      ...user,
      name: editedName,
      email: editedEmail,
      phone: editedPhone,
      department: editedDepartment,
      role: editedRole,
      mfaEnabled: editedMfaEnabled,
      updatedAt: new Date().toISOString(),
    });
    setIsSaving(false);
  };

  const handleResetPassword = async () => {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsResetPasswordDialogOpen(false);
    // In production, this would send a password reset email
  };

  const handleDeactivate = async () => {
    setUser({
      ...user,
      status: user.status === "active" ? "inactive" : "active",
    });
    setIsDeactivateDialogOpen(false);
  };

  const toggleDirectPermission = (permId: string) => {
    setPermissions(
      permissions.map((p) =>
        p.id === permId
          ? { ...p, granted: !p.granted, source: p.granted ? "direct" as const : "direct" as const }
          : p
      )
    );
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <User className="h-6 w-6" />
              User Details
            </h1>
            <p className="text-muted-foreground">
              Edit user profile and manage permissions
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setIsLoading(true);
              setTimeout(() => setIsLoading(false), 1000);
            }}
            disabled={isLoading}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          <Button size="sm" onClick={handleSave} disabled={isSaving}>
            <Save className={`mr-2 h-4 w-4 ${isSaving ? "animate-pulse" : ""}`} />
            {isSaving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </div>

      {/* User Overview Card */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
            <div className="flex items-start gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary text-primary-foreground text-xl font-bold">
                {user.name
                  .split(" ")
                  .map((n) => n[0])
                  .join("")
                  .toUpperCase()
                  .slice(0, 2)}
              </div>
              <div>
                <h2 className="text-xl font-semibold">{user.name}</h2>
                <p className="text-muted-foreground">{user.email}</p>
                <div className="flex items-center gap-2 mt-2">
                  <Badge className={`gap-1 ${getRoleColor(user.role)}`}>
                    {getRoleIcon(user.role)}
                    {user.role.replace("_", " ")}
                  </Badge>
                  <Badge className={getStatusColor(user.status)}>
                    {user.status === "active" ? (
                      <CheckCircle className="mr-1 h-3 w-3" />
                    ) : user.status === "inactive" ? (
                      <XCircle className="mr-1 h-3 w-3" />
                    ) : (
                      <Clock className="mr-1 h-3 w-3" />
                    )}
                    {user.status}
                  </Badge>
                  {user.mfaEnabled && (
                    <Badge variant="outline" className="gap-1">
                      <Shield className="h-3 w-3" />
                      MFA Enabled
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <div className="text-center">
                <div className="text-2xl font-bold">{user.loginCount}</div>
                <div className="text-xs text-muted-foreground">Total Logins</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-amber-600">
                  {user.failedLoginCount}
                </div>
                <div className="text-xs text-muted-foreground">Failed Attempts</div>
              </div>
              <div className="text-center">
                <div className="text-sm font-medium">
                  {formatTimeAgo(user.lastActive)}
                </div>
                <div className="text-xs text-muted-foreground">Last Active</div>
              </div>
              <div className="text-center">
                <div className="text-sm font-medium">
                  {new Date(user.createdAt).toLocaleDateString()}
                </div>
                <div className="text-xs text-muted-foreground">Created</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs defaultValue="profile" className="space-y-4">
        <TabsList>
          <TabsTrigger value="profile" className="gap-2">
            <User className="h-4 w-4" />
            Profile
          </TabsTrigger>
          <TabsTrigger value="role" className="gap-2">
            <Key className="h-4 w-4" />
            Role & Permissions
          </TabsTrigger>
          <TabsTrigger value="activity" className="gap-2">
            <Activity className="h-4 w-4" />
            Activity Log
          </TabsTrigger>
          <TabsTrigger value="security" className="gap-2">
            <Shield className="h-4 w-4" />
            Security
          </TabsTrigger>
        </TabsList>

        {/* Profile Tab */}
        <TabsContent value="profile" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Edit Profile</CardTitle>
              <CardDescription>
                Update user profile information
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="name">Full Name</Label>
                  <Input
                    id="name"
                    value={editedName}
                    onChange={(e) => setEditedName(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="email">Email Address</Label>
                  <Input
                    id="email"
                    type="email"
                    value={editedEmail}
                    onChange={(e) => setEditedEmail(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="phone">Phone Number</Label>
                  <Input
                    id="phone"
                    value={editedPhone}
                    onChange={(e) => setEditedPhone(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="department">Department</Label>
                  <Input
                    id="department"
                    value={editedDepartment}
                    onChange={(e) => setEditedDepartment(e.target.value)}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Account Actions</CardTitle>
              <CardDescription>
                Manage account status and security settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-medium">Account Status</h4>
                  <p className="text-sm text-muted-foreground">
                    {user.status === "active"
                      ? "User can access the system"
                      : "User cannot access the system"}
                  </p>
                </div>
                <Dialog
                  open={isDeactivateDialogOpen}
                  onOpenChange={setIsDeactivateDialogOpen}
                >
                  <DialogTrigger asChild>
                    <Button
                      variant={user.status === "active" ? "destructive" : "default"}
                    >
                      {user.status === "active" ? (
                        <>
                          <XCircle className="mr-2 h-4 w-4" />
                          Deactivate Account
                        </>
                      ) : (
                        <>
                          <CheckCircle className="mr-2 h-4 w-4" />
                          Reactivate Account
                        </>
                      )}
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>
                        {user.status === "active"
                          ? "Deactivate Account"
                          : "Reactivate Account"}
                      </DialogTitle>
                      <DialogDescription>
                        {user.status === "active"
                          ? "This will prevent the user from accessing the system. They can be reactivated at any time."
                          : "This will allow the user to access the system again."}
                      </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                      <Button
                        variant="outline"
                        onClick={() => setIsDeactivateDialogOpen(false)}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant={user.status === "active" ? "destructive" : "default"}
                        onClick={handleDeactivate}
                      >
                        {user.status === "active" ? "Deactivate" : "Reactivate"}
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>

              <div className="flex items-center justify-between border-t pt-4">
                <div>
                  <h4 className="font-medium">Reset Password</h4>
                  <p className="text-sm text-muted-foreground">
                    Send a password reset email to the user
                  </p>
                </div>
                <Dialog
                  open={isResetPasswordDialogOpen}
                  onOpenChange={setIsResetPasswordDialogOpen}
                >
                  <DialogTrigger asChild>
                    <Button variant="outline">
                      <Key className="mr-2 h-4 w-4" />
                      Reset Password
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Reset Password</DialogTitle>
                      <DialogDescription>
                        A password reset link will be sent to {user.email}
                      </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                      <Button
                        variant="outline"
                        onClick={() => setIsResetPasswordDialogOpen(false)}
                      >
                        Cancel
                      </Button>
                      <Button onClick={handleResetPassword}>
                        Send Reset Email
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Role & Permissions Tab */}
        <TabsContent value="role" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Role Assignment</CardTitle>
              <CardDescription>
                Change the user&apos;s role to update their base permissions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <Label>Select Role</Label>
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {availableRoles.map((role) => (
                    <div
                      key={role.id}
                      className={`flex items-start gap-3 rounded-lg border p-4 cursor-pointer transition-colors ${
                        editedRole === role.id
                          ? "border-primary bg-primary/5"
                          : "hover:bg-muted/50"
                      }`}
                      onClick={() => setEditedRole(role.id)}
                    >
                      <div className="mt-0.5">
                        {getRoleIcon(role.id)}
                      </div>
                      <div>
                        <div className="font-medium flex items-center gap-2">
                          {role.name}
                          {editedRole === role.id && (
                            <CheckCircle className="h-4 w-4 text-primary" />
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {role.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Permissions</CardTitle>
              <CardDescription>
                Permissions inherited from role and directly assigned
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {resourceTypes.map((resource) => {
                  const resourcePerms = permissions.filter(
                    (p) => p.resource === resource
                  );

                  return (
                    <div key={resource} className="space-y-3">
                      <h4 className="font-medium capitalize border-b pb-2">
                        {resource}
                      </h4>
                      <div className="grid gap-2 pl-4">
                        {resourcePerms.map((perm) => (
                          <div
                            key={perm.id}
                            className="flex items-center justify-between py-1"
                          >
                            <div className="flex items-center gap-3">
                              <Checkbox
                                checked={perm.granted}
                                onCheckedChange={() =>
                                  toggleDirectPermission(perm.id)
                                }
                              />
                              <div>
                                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                  {perm.name}
                                </code>
                                <p className="text-sm text-muted-foreground">
                                  {perm.description}
                                </p>
                              </div>
                            </div>
                            <Badge
                              variant="outline"
                              className={
                                perm.source === "role"
                                  ? "text-blue-600"
                                  : "text-purple-600"
                              }
                            >
                              {perm.source === "role" ? "From Role" : "Direct"}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Activity Log Tab */}
        <TabsContent value="activity" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Activity Log</CardTitle>
              <CardDescription>
                Recent actions performed by this user
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Resource</TableHead>
                    <TableHead>Details</TableHead>
                    <TableHead>IP Address</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {activityLog.map((entry) => (
                    <TableRow key={entry.id}>
                      <TableCell>
                        <div>
                          <div className="text-sm font-medium">
                            {formatTimeAgo(entry.timestamp)}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {formatDateTime(entry.timestamp)}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="gap-1">
                          {getActionIcon(entry.action)}
                          {entry.action}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">{entry.resource}</Badge>
                      </TableCell>
                      <TableCell className="max-w-[200px]">
                        <p className="text-sm truncate" title={entry.details}>
                          {entry.details}
                        </p>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {entry.ipAddress}
                      </TableCell>
                      <TableCell>
                        {entry.success ? (
                          <CheckCircle className="h-5 w-5 text-green-600" />
                        ) : (
                          <XCircle className="h-5 w-5 text-red-600" />
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security Tab */}
        <TabsContent value="security" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Security Settings</CardTitle>
              <CardDescription>
                Configure security options for this user
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-medium">Two-Factor Authentication</h4>
                  <p className="text-sm text-muted-foreground">
                    Require MFA for login
                  </p>
                </div>
                <Switch
                  checked={editedMfaEnabled}
                  onCheckedChange={setEditedMfaEnabled}
                />
              </div>

              <div className="border-t pt-6">
                <h4 className="font-medium mb-4">Login History</h4>
                <div className="grid gap-4 md:grid-cols-3">
                  <Card>
                    <CardContent className="pt-6">
                      <div className="text-center">
                        <div className="text-3xl font-bold text-green-600">
                          {user.loginCount}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          Successful Logins
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-6">
                      <div className="text-center">
                        <div className="text-3xl font-bold text-amber-600">
                          {user.failedLoginCount}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          Failed Attempts
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-6">
                      <div className="text-center">
                        <div className="text-lg font-medium">
                          {formatTimeAgo(user.lastActive)}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          Last Login
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>

              <div className="border-t pt-6">
                <h4 className="font-medium mb-2">Security Alerts</h4>
                {user.failedLoginCount > 0 ? (
                  <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950">
                    <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
                    <div>
                      <h5 className="font-medium text-amber-800 dark:text-amber-200">
                        Failed Login Attempts
                      </h5>
                      <p className="text-sm text-amber-700 dark:text-amber-300">
                        This user has {user.failedLoginCount} failed login
                        attempt(s). Consider reviewing their security settings.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-950">
                    <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                    <div>
                      <h5 className="font-medium text-green-800 dark:text-green-200">
                        No Security Issues
                      </h5>
                      <p className="text-sm text-green-700 dark:text-green-300">
                        This user has no recent security alerts.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
