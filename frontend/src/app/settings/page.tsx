"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Loader2,
  User,
  Lock,
  Bell,
  Moon,
  Sun,
  Monitor,
  Trash2,
  AlertTriangle,
  Save,
  Eye,
  EyeOff,
  Check,
  Shield,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth, useRequireAuth } from "@/hooks/use-auth";

// ============================================================================
// Types
// ============================================================================

/** Shape returned by GET /api/auth/me */
interface MeResponse {
  id: string;
  email: string;
  roles: string[];
  permissions: string[];
  is_admin: boolean;
}

// ============================================================================
// Form Schemas
// ============================================================================

const passwordSchema = z
  .object({
    currentPassword: z.string().min(1, "Current password is required"),
    newPassword: z
      .string()
      .min(8, "Password must be at least 8 characters")
      .regex(/[a-z]/, "Password must contain at least one lowercase letter")
      .regex(/[A-Z]/, "Password must contain at least one uppercase letter")
      .regex(/[0-9]/, "Password must contain at least one number"),
    confirmPassword: z.string(),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: "Passwords don't match",
    path: ["confirmPassword"],
  });

type PasswordFormData = z.infer<typeof passwordSchema>;

// ============================================================================
// Theme Types and Utilities
// ============================================================================

type Theme = "light" | "dark" | "system";

function getInitialTheme(): Theme {
  if (typeof window === "undefined") return "system";
  return (localStorage.getItem("theme") as Theme) || "system";
}

function applyTheme(theme: Theme) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;

  if (theme === "system") {
    const systemTheme = window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
    root.classList.toggle("dark", systemTheme === "dark");
  } else {
    root.classList.toggle("dark", theme === "dark");
  }
}

function useTheme() {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);

  // Apply theme on mount
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const setTheme = useCallback((newTheme: Theme) => {
    setThemeState(newTheme);
    localStorage.setItem("theme", newTheme);
    applyTheme(newTheme);
  }, []);

  return { theme, setTheme };
}

// ============================================================================
// Notification Preferences
// ============================================================================

interface NotificationPreferences {
  emailNotifications: boolean;
  documentProcessed: boolean;
  weeklyDigest: boolean;
  securityAlerts: boolean;
}

// ============================================================================
// Notification Toggle Component (Extracted)
// ============================================================================

function NotificationToggle({
  id,
  label,
  description,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  description: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <div className="flex items-center justify-between py-3">
      <div className="space-y-0.5">
        <Label htmlFor={id} className="text-sm font-medium cursor-pointer">
          {label}
        </Label>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={onChange}
        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
          checked ? "bg-primary" : "bg-input"
        }`}
      >
        <span
          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-background shadow-lg ring-0 transition-transform ${
            checked ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  );
}

// ============================================================================
// Theme Option Component (Extracted)
// ============================================================================

function ThemeOption({
  value,
  label,
  icon: Icon,
  currentTheme,
  onSelect,
}: {
  value: Theme;
  label: string;
  icon: typeof Sun;
  currentTheme: Theme;
  onSelect: (theme: Theme) => void;
}) {
  const isSelected = currentTheme === value;

  return (
    <button
      type="button"
      onClick={() => onSelect(value)}
      className={`flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-colors ${
        isSelected
          ? "border-primary bg-primary/5"
          : "border-input hover:border-muted-foreground/50"
      }`}
    >
      <div
        className={`p-3 rounded-full ${
          isSelected ? "bg-primary text-primary-foreground" : "bg-muted"
        }`}
      >
        <Icon className="h-5 w-5" />
      </div>
      <span className="text-sm font-medium">{label}</span>
      {isSelected && <Check className="h-4 w-4 text-primary" />}
    </button>
  );
}

// ============================================================================
// Profile Section (wired to GET /api/auth/me)
// ============================================================================

function ProfileSection() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<MeResponse | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState<string | null>(null);

  const fetchProfile = useCallback(async () => {
    setProfileLoading(true);
    setProfileError(null);

    try {
      const storedTokens = localStorage.getItem("auth_tokens");
      const tokens = storedTokens ? JSON.parse(storedTokens) : null;
      const headers: Record<string, string> = {};
      if (tokens?.access_token) {
        headers["Authorization"] = `Bearer ${tokens.access_token}`;
      }

      const res = await fetch("/api/auth/me", { headers });

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: "Failed to load profile" }));
        throw new Error(body.detail || `Server returned ${res.status}`);
      }

      const data: MeResponse = await res.json();
      setProfile(data);
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Failed to load profile");
    } finally {
      setProfileLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  if (profileLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Profile Information
          </CardTitle>
          <CardDescription>Your account details.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="ml-2 text-sm text-muted-foreground">
              Loading profile...
            </span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (profileError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Profile Information
          </CardTitle>
          <CardDescription>Your account details.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4 space-y-3">
            <p className="text-sm text-destructive font-medium">
              Unable to load profile
            </p>
            <p className="text-sm text-muted-foreground">{profileError}</p>
            <Button variant="outline" size="sm" onClick={fetchProfile}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <User className="h-5 w-5" />
          Profile Information
        </CardTitle>
        <CardDescription>Your account details.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Display name from auth context (populated at login) */}
        {user?.name && (
          <div className="space-y-1">
            <Label className="text-sm text-muted-foreground">Full Name</Label>
            <p className="text-sm font-medium">{user.name}</p>
          </div>
        )}

        <div className="space-y-1">
          <Label className="text-sm text-muted-foreground">Email Address</Label>
          <p className="text-sm font-medium">{profile?.email ?? "---"}</p>
        </div>

        <div className="space-y-1">
          <Label className="text-sm text-muted-foreground">User ID</Label>
          <p className="text-sm font-mono text-muted-foreground">
            {profile?.id ?? "---"}
          </p>
        </div>

        <div className="space-y-1">
          <Label className="text-sm text-muted-foreground">Roles</Label>
          <div className="flex flex-wrap gap-2">
            {profile?.roles.length ? (
              profile.roles.map((role) => (
                <span
                  key={role}
                  className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors bg-secondary text-secondary-foreground"
                >
                  {role}
                </span>
              ))
            ) : (
              <span className="text-sm text-muted-foreground">No roles assigned</span>
            )}
          </div>
        </div>

        {profile?.is_admin && (
          <div className="flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 p-3">
            <Shield className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium text-primary">
              Administrator
            </span>
          </div>
        )}

        {profile?.permissions && profile.permissions.length > 0 && (
          <div className="space-y-1">
            <Label className="text-sm text-muted-foreground">Permissions</Label>
            <div className="flex flex-wrap gap-1.5">
              {profile.permissions.map((perm) => (
                <span
                  key={perm}
                  className="inline-flex items-center rounded border px-2 py-0.5 text-xs text-muted-foreground"
                >
                  {perm}
                </span>
              ))}
            </div>
          </div>
        )}
      </CardContent>
      <CardFooter>
        <Button variant="outline" size="sm" onClick={fetchProfile}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </CardFooter>
    </Card>
  );
}

// ============================================================================
// Password Section
// ============================================================================

function PasswordSection() {
  const { changePassword, isLoading, error } = useAuth();
  const [isSaving, setIsSaving] = useState(false);
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const form = useForm<PasswordFormData>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      currentPassword: "",
      newPassword: "",
      confirmPassword: "",
    },
  });

  const onSubmit = async (data: PasswordFormData) => {
    setIsSaving(true);

    const success = await changePassword(data.currentPassword, data.newPassword);

    setIsSaving(false);

    if (success) {
      form.reset();
      toast.success("Password changed", {
        description: "Your password has been updated successfully.",
      });
    } else {
      toast.error("Password change failed", {
        description: error || "Please check your current password and try again.",
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Lock className="h-5 w-5" />
          Change Password
        </CardTitle>
        <CardDescription>
          Update your password to keep your account secure.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="currentPassword"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Current Password</FormLabel>
                  <FormControl>
                    <div className="relative">
                      <Input
                        type={showCurrentPassword ? "text" : "password"}
                        {...field}
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setShowCurrentPassword(!showCurrentPassword)
                        }
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      >
                        {showCurrentPassword ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="newPassword"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>New Password</FormLabel>
                  <FormControl>
                    <div className="relative">
                      <Input
                        type={showNewPassword ? "text" : "password"}
                        {...field}
                      />
                      <button
                        type="button"
                        onClick={() => setShowNewPassword(!showNewPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      >
                        {showNewPassword ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </FormControl>
                  <FormDescription>
                    Must be at least 8 characters with uppercase, lowercase, and
                    numbers.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="confirmPassword"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Confirm New Password</FormLabel>
                  <FormControl>
                    <div className="relative">
                      <Input
                        type={showConfirmPassword ? "text" : "password"}
                        {...field}
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setShowConfirmPassword(!showConfirmPassword)
                        }
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      >
                        {showConfirmPassword ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <Button type="submit" disabled={isSaving || isLoading}>
              {isSaving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Updating...
                </>
              ) : (
                "Update Password"
              )}
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Notifications Section
// ============================================================================

const NOTIFICATION_PREFS_KEY = "notification_preferences";

function getStoredNotificationPrefs(): NotificationPreferences {
  if (typeof window === "undefined") {
    return {
      emailNotifications: true,
      documentProcessed: true,
      weeklyDigest: false,
      securityAlerts: true,
    };
  }
  try {
    const stored = localStorage.getItem(NOTIFICATION_PREFS_KEY);
    if (stored) return JSON.parse(stored);
  } catch {
    // fall through to defaults
  }
  return {
    emailNotifications: true,
    documentProcessed: true,
    weeklyDigest: false,
    securityAlerts: true,
  };
}

function NotificationsSection() {
  const [preferences, setPreferences] = useState<NotificationPreferences>(
    getStoredNotificationPrefs
  );
  const [isSaving, setIsSaving] = useState(false);

  const handleToggle = useCallback((key: keyof NotificationPreferences) => {
    setPreferences((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    // Persist to localStorage (no backend endpoint for notification prefs)
    try {
      localStorage.setItem(NOTIFICATION_PREFS_KEY, JSON.stringify(preferences));
    } catch {
      // localStorage write failed, non-fatal
    }
    setIsSaving(false);
    toast.success("Preferences saved", {
      description: "Your notification preferences have been updated.",
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bell className="h-5 w-5" />
          Notification Preferences
        </CardTitle>
        <CardDescription>
          Choose what notifications you want to receive.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-1">
        <NotificationToggle
          id="email-notifications"
          label="Email Notifications"
          description="Receive notifications via email"
          checked={preferences.emailNotifications}
          onChange={() => handleToggle("emailNotifications")}
        />
        <NotificationToggle
          id="document-processed"
          label="Document Processing Alerts"
          description="Get notified when a document finishes processing"
          checked={preferences.documentProcessed}
          onChange={() => handleToggle("documentProcessed")}
        />
        <NotificationToggle
          id="weekly-digest"
          label="Weekly Digest"
          description="Receive a weekly summary of activity"
          checked={preferences.weeklyDigest}
          onChange={() => handleToggle("weeklyDigest")}
        />
        <NotificationToggle
          id="security-alerts"
          label="Security Alerts"
          description="Important security notifications (recommended)"
          checked={preferences.securityAlerts}
          onChange={() => handleToggle("securityAlerts")}
        />
      </CardContent>
      <CardFooter>
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              Save Preferences
            </>
          )}
        </Button>
      </CardFooter>
    </Card>
  );
}

// ============================================================================
// Appearance Section
// ============================================================================

function AppearanceSection() {
  const { theme, setTheme } = useTheme();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sun className="h-5 w-5" />
          Appearance
        </CardTitle>
        <CardDescription>
          Customize how the application looks on your device.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-4">
          <ThemeOption
            value="light"
            label="Light"
            icon={Sun}
            currentTheme={theme}
            onSelect={setTheme}
          />
          <ThemeOption
            value="dark"
            label="Dark"
            icon={Moon}
            currentTheme={theme}
            onSelect={setTheme}
          />
          <ThemeOption
            value="system"
            label="System"
            icon={Monitor}
            currentTheme={theme}
            onSelect={setTheme}
          />
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Danger Zone Section
// ============================================================================

function DangerZoneSection() {
  const router = useRouter();
  const { logout } = useAuth();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");

  const handleDeleteAccount = async () => {
    if (deleteConfirmText !== "DELETE") {
      toast.error("Confirmation required", {
        description: "Please type DELETE to confirm account deletion.",
      });
      return;
    }

    // This is a placeholder - actual deletion would require backend implementation
    toast.info("Account deletion", {
      description:
        "Account deletion is currently not available. Please contact support.",
    });
    setShowDeleteConfirm(false);
    setDeleteConfirmText("");
  };

  const handleLogoutAllDevices = async () => {
    await logout();
    toast.success("Logged out", {
      description: "You have been logged out from all devices.",
    });
    router.push("/login");
  };

  return (
    <Card className="border-destructive/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-destructive">
          <AlertTriangle className="h-5 w-5" />
          Danger Zone
        </CardTitle>
        <CardDescription>
          Irreversible actions that affect your account.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Logout all devices */}
        <div className="flex items-center justify-between p-4 rounded-lg border">
          <div className="space-y-0.5">
            <p className="text-sm font-medium">Log out of all devices</p>
            <p className="text-sm text-muted-foreground">
              This will log you out from all active sessions.
            </p>
          </div>
          <Button variant="outline" onClick={handleLogoutAllDevices}>
            Log out all
          </Button>
        </div>

        {/* Delete account */}
        <div className="flex items-center justify-between p-4 rounded-lg border border-destructive/50 bg-destructive/5">
          <div className="space-y-0.5">
            <p className="text-sm font-medium">Delete account</p>
            <p className="text-sm text-muted-foreground">
              Permanently delete your account and all associated data.
            </p>
          </div>
          <Button
            variant="destructive"
            onClick={() => setShowDeleteConfirm(!showDeleteConfirm)}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete account
          </Button>
        </div>

        {/* Delete confirmation */}
        {showDeleteConfirm && (
          <div className="p-4 rounded-lg border border-destructive bg-destructive/10 space-y-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
              <div className="space-y-2">
                <p className="text-sm font-medium text-destructive">
                  Are you absolutely sure?
                </p>
                <p className="text-sm text-muted-foreground">
                  This action cannot be undone. This will permanently delete
                  your account and remove all of your data from our servers.
                </p>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="delete-confirm" className="text-sm">
                Type <span className="font-mono font-bold">DELETE</span> to
                confirm
              </Label>
              <Input
                id="delete-confirm"
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
                placeholder="DELETE"
                className="font-mono"
              />
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setDeleteConfirmText("");
                }}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDeleteAccount}
                disabled={deleteConfirmText !== "DELETE"}
              >
                Delete my account
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Settings Page Component
// ============================================================================

export default function SettingsPage() {
  const { isLoading, isAuthenticated } = useRequireAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="container max-w-4xl py-8 px-4 md:px-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground mt-2">
          Manage your account settings and preferences.
        </p>
      </div>

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4 lg:w-auto lg:inline-grid">
          <TabsTrigger value="profile" className="flex items-center gap-2">
            <User className="h-4 w-4" />
            <span className="hidden sm:inline">Profile</span>
          </TabsTrigger>
          <TabsTrigger value="security" className="flex items-center gap-2">
            <Lock className="h-4 w-4" />
            <span className="hidden sm:inline">Security</span>
          </TabsTrigger>
          <TabsTrigger
            value="notifications"
            className="flex items-center gap-2"
          >
            <Bell className="h-4 w-4" />
            <span className="hidden sm:inline">Notifications</span>
          </TabsTrigger>
          <TabsTrigger value="appearance" className="flex items-center gap-2">
            <Sun className="h-4 w-4" />
            <span className="hidden sm:inline">Appearance</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="space-y-6">
          <ProfileSection />
        </TabsContent>

        <TabsContent value="security" className="space-y-6">
          <PasswordSection />
          <DangerZoneSection />
        </TabsContent>

        <TabsContent value="notifications" className="space-y-6">
          <NotificationsSection />
        </TabsContent>

        <TabsContent value="appearance" className="space-y-6">
          <AppearanceSection />
        </TabsContent>
      </Tabs>
    </div>
  );
}
