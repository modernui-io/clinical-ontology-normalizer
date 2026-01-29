"use client";

/**
 * SMART App Management UI
 *
 * Admin interface for managing registered SMART on FHIR applications.
 * Allows viewing, registering, editing, and deleting SMART apps.
 */

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { PermissionGate, PERMISSIONS } from "@/hooks/use-permissions";
import { Plus, Trash2, Edit, Copy, RefreshCw, Shield, Loader2 } from "lucide-react";
import { toast } from "sonner";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getAuthHeaders(token: string | null): HeadersInit {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

interface SMARTApp {
  client_id: string;
  client_name: string;  // API returns client_name
  redirect_uris: string[];
  scope: string;  // API returns scope as string, not scopes array
  app_type: string;
  is_active: boolean;
  is_confidential: boolean;
  created_at: string;
}

interface RegisterAppForm {
  app_name: string;
  redirect_uris: string;
  scopes: string;
  is_confidential: boolean;
}

const DEFAULT_SCOPES = [
  "openid",
  "fhirUser",
  "launch/patient",
  "launch/encounter",
  "patient/*.read",
  "offline_access",
];

// Helper to get token from localStorage directly
function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = localStorage.getItem('auth_tokens');
    if (stored) {
      const tokens = JSON.parse(stored);
      return tokens.access_token || null;
    }
  } catch {
    // Ignore parse errors
  }
  return null;
}

export default function SMARTAppsPage() {
  const [apps, setApps] = useState<SMARTApp[]>([]);
  const [loading, setLoading] = useState(true);
  const [registerOpen, setRegisterOpen] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [newCredentials, setNewCredentials] = useState<{ client_id: string; client_secret?: string } | null>(null);
  const [form, setForm] = useState<RegisterAppForm>({
    app_name: "",
    redirect_uris: "http://localhost:3000/smart/callback",
    scopes: DEFAULT_SCOPES.join(" "),
    is_confidential: false,
  });

  useEffect(() => {
    loadApps();
  }, []);

  async function loadApps() {
    setLoading(true);
    try {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE_URL}/api/v1/smart-server/apps`, {
        headers: getAuthHeaders(token),
      });
      if (response.ok) {
        const data = await response.json();
        // API returns array directly, not wrapped in { apps: [...] }
        setApps(Array.isArray(data) ? data : (data.apps || []));
      }
    } catch (err) {
      toast.error("Failed to load SMART apps");
    } finally {
      setLoading(false);
    }
  }

  async function registerApp() {
    setRegistering(true);
    try {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE_URL}/api/v1/smart-server/apps`, {
        method: "POST",
        headers: getAuthHeaders(token),
        body: JSON.stringify({
          app_name: form.app_name,
          redirect_uris: form.redirect_uris.split("\n").map((u) => u.trim()).filter(Boolean),
          scopes: form.scopes.split(/[\s,]+/).filter(Boolean),
          grant_types: ["authorization_code"],
          is_confidential: form.is_confidential,
        }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "Registration failed");
      }

      const result = await response.json();
      setNewCredentials({
        client_id: result.client_id,
        client_secret: result.client_secret,
      });

      await loadApps();
      toast.success("SMART app registered successfully");

      // Reset form
      setForm({
        app_name: "",
        redirect_uris: "http://localhost:3000/smart/callback",
        scopes: DEFAULT_SCOPES.join(" "),
        is_confidential: false,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to register app");
    } finally {
      setRegistering(false);
    }
  }

  async function deleteApp(clientId: string) {
    if (!confirm("Are you sure you want to delete this app?")) return;

    try {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE_URL}/api/v1/smart-server/apps/${clientId}`, {
        method: "DELETE",
        headers: getAuthHeaders(token),
      });

      if (!response.ok) {
        throw new Error("Failed to delete app");
      }

      await loadApps();
      toast.success("SMART app deleted");
    } catch (err) {
      toast.error("Failed to delete app");
    }
  }

  function copyToClipboard(text: string, label: string) {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied to clipboard`);
  }

  return (
    <PermissionGate permission={PERMISSIONS.ADMIN_MANAGE_USERS} fallback={
      <div className="p-6">
        <Card>
          <CardContent className="py-8 text-center">
            <Shield className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
            <p className="text-lg font-medium">Admin Access Required</p>
            <p className="text-muted-foreground">You need admin permissions to manage SMART apps.</p>
          </CardContent>
        </Card>
      </div>
    }>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">SMART on FHIR Apps</h1>
            <p className="text-muted-foreground">Manage registered SMART applications</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={loadApps} disabled={loading}>
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
            <Dialog open={registerOpen} onOpenChange={setRegisterOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Register App
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-lg">
                <DialogHeader>
                  <DialogTitle>Register SMART App</DialogTitle>
                  <DialogDescription>
                    Register a new SMART on FHIR application
                  </DialogDescription>
                </DialogHeader>

                {newCredentials ? (
                  <div className="space-y-4">
                    <div className="rounded-lg bg-green-500/10 border border-green-500/20 p-4">
                      <p className="text-sm font-medium text-green-500 mb-2">App Registered Successfully!</p>
                      <p className="text-xs text-muted-foreground mb-4">
                        {newCredentials.client_secret
                          ? "Save these credentials - the client secret will not be shown again."
                          : "This is a public client - no client secret required."}
                      </p>
                    </div>

                    <div className="space-y-3">
                      <div>
                        <Label className="text-xs text-muted-foreground">Client ID</Label>
                        <div className="flex gap-2">
                          <Input value={newCredentials.client_id} readOnly className="font-mono text-sm" />
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => copyToClipboard(newCredentials.client_id, "Client ID")}
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>

                      {newCredentials.client_secret && (
                        <div>
                          <Label className="text-xs text-muted-foreground">Client Secret</Label>
                          <div className="flex gap-2">
                            <Input value={newCredentials.client_secret} readOnly className="font-mono text-sm" />
                            <Button
                              variant="outline"
                              size="icon"
                              onClick={() => copyToClipboard(newCredentials.client_secret!, "Client Secret")}
                            >
                              <Copy className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>

                    <DialogFooter>
                      <Button onClick={() => { setNewCredentials(null); setRegisterOpen(false); }}>
                        Done
                      </Button>
                    </DialogFooter>
                  </div>
                ) : (
                  <>
                    <div className="space-y-4">
                      <div>
                        <Label htmlFor="app_name">Application Name</Label>
                        <Input
                          id="app_name"
                          value={form.app_name}
                          onChange={(e) => setForm({ ...form, app_name: e.target.value })}
                          placeholder="My SMART App"
                        />
                      </div>

                      <div>
                        <Label htmlFor="redirect_uris">Redirect URIs (one per line)</Label>
                        <textarea
                          id="redirect_uris"
                          value={form.redirect_uris}
                          onChange={(e) => setForm({ ...form, redirect_uris: e.target.value })}
                          className="w-full min-h-[80px] px-3 py-2 rounded-md border bg-background text-sm"
                          placeholder="http://localhost:3000/callback"
                        />
                      </div>

                      <div>
                        <Label htmlFor="scopes">Scopes (space or comma separated)</Label>
                        <textarea
                          id="scopes"
                          value={form.scopes}
                          onChange={(e) => setForm({ ...form, scopes: e.target.value })}
                          className="w-full min-h-[60px] px-3 py-2 rounded-md border bg-background text-sm"
                        />
                      </div>

                      <div className="flex items-center gap-2">
                        <Checkbox
                          id="is_confidential"
                          checked={form.is_confidential}
                          onCheckedChange={(checked) => setForm({ ...form, is_confidential: checked === true })}
                        />
                        <Label htmlFor="is_confidential" className="text-sm">
                          Confidential client (can securely store client secret)
                        </Label>
                      </div>
                    </div>

                    <DialogFooter>
                      <Button variant="outline" onClick={() => setRegisterOpen(false)}>
                        Cancel
                      </Button>
                      <Button onClick={registerApp} disabled={registering || !form.app_name}>
                        {registering ? (
                          <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            Registering...
                          </>
                        ) : (
                          "Register"
                        )}
                      </Button>
                    </DialogFooter>
                  </>
                )}
              </DialogContent>
            </Dialog>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Registered Applications</CardTitle>
            <CardDescription>
              {apps.length} app{apps.length !== 1 ? "s" : ""} registered
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : apps.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No SMART apps registered. Click "Register App" to add one.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Client ID</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Scopes</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {apps.map((app) => (
                    <TableRow key={app.client_id}>
                      <TableCell className="font-medium">{app.client_name}</TableCell>
                      <TableCell>
                        <code className="text-xs bg-muted px-1 py-0.5 rounded">
                          {app.client_id.slice(0, 12)}...
                        </code>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 ml-1"
                          onClick={() => copyToClipboard(app.client_id, "Client ID")}
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                      </TableCell>
                      <TableCell>
                        <Badge variant={app.is_confidential ? "default" : "secondary"}>
                          {app.is_confidential ? "Confidential" : "Public"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="text-xs text-muted-foreground">
                          {app.scope.split(' ').filter(Boolean).length} scope{app.scope.split(' ').filter(Boolean).length !== 1 ? "s" : ""}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant={app.is_active ? "default" : "destructive"}>
                          {app.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive"
                          onClick={() => deleteApp(app.client_id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </PermissionGate>
  );
}
