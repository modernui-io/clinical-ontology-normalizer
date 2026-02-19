"use client";

/**
 * Data Sources Management UI
 *
 * Admin interface for managing external data source connections.
 * Supports FHIR servers, HIEs, aggregators, and file uploads.
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { PermissionGate, PERMISSIONS } from "@/hooks/use-permissions";
import {
  Plus,
  Trash2,
  Edit,
  RefreshCw,
  Shield,
  Loader2,
  Server,
  Database,
  Cloud,
  Upload,
  Radio,
  CheckCircle,
  XCircle,
  AlertCircle,
  HelpCircle,
  Play,
} from "lucide-react";
import { toast } from "sonner";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getAuthHeaders(token: string | null): HeadersInit {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem("auth_tokens");
    if (stored) {
      const tokens = JSON.parse(stored);
      return tokens.access_token || null;
    }
  } catch {
    // Ignore parse errors
  }
  return null;
}

type SourceType = "fhir_server" | "hie" | "aggregator" | "file_upload" | "hl7_feed" | "database" | "ccda";
type HealthStatus = "healthy" | "degraded" | "offline" | "unknown";
type AuthMethod = "none" | "basic" | "bearer_token" | "oauth2_client_credentials" | "oauth2_authorization_code" | "api_key" | "smart_backend";

interface DataSource {
  id: string;
  name: string;
  description: string | null;
  source_type: SourceType;
  auth_method: AuthMethod;
  is_active: boolean;
  health_status: HealthStatus;
  last_health_check_at: string | null;
  last_health_message: string | null;
  last_connected_at: string | null;
  total_records_imported: number;
  default_batch_size: number;
  default_timeout_seconds: number;
  default_retry_count: number;
  created_at: string;
  updated_at: string;
  base_url: string | null;
  client_id: string | null;
  has_client_secret: boolean;
  has_api_key: boolean;
  token_url: string | null;
  scopes: string[];
  timeout_seconds: number;
  verify_ssl: boolean;
}

interface DataSourceForm {
  name: string;
  description: string;
  source_type: SourceType;
  auth_method: AuthMethod;
  base_url: string;
  client_id: string;
  client_secret: string;
  api_key: string;
  username: string;
  password: string;
  token_url: string;
  scopes: string;
  timeout_seconds: number;
  verify_ssl: boolean;
  default_batch_size: number;
  default_retry_count: number;
}

const SOURCE_TYPE_OPTIONS: { value: SourceType; label: string; icon: React.ReactNode }[] = [
  { value: "fhir_server", label: "FHIR Server", icon: <Server className="h-4 w-4" /> },
  { value: "hie", label: "Health Information Exchange", icon: <Cloud className="h-4 w-4" /> },
  { value: "aggregator", label: "Data Aggregator", icon: <Database className="h-4 w-4" /> },
  { value: "file_upload", label: "File Upload", icon: <Upload className="h-4 w-4" /> },
  { value: "hl7_feed", label: "HL7 Feed", icon: <Radio className="h-4 w-4" /> },
  { value: "database", label: "Database", icon: <Database className="h-4 w-4" /> },
  { value: "ccda", label: "C-CDA Import", icon: <Server className="h-4 w-4" /> },
];

const AUTH_METHOD_OPTIONS: { value: AuthMethod; label: string }[] = [
  { value: "none", label: "No Authentication" },
  { value: "basic", label: "Basic Auth" },
  { value: "bearer_token", label: "Bearer Token / API Key" },
  { value: "api_key", label: "API Key (Header)" },
  { value: "oauth2_client_credentials", label: "OAuth2 Client Credentials" },
  { value: "smart_backend", label: "SMART Backend Services" },
];

const HEALTH_STATUS_CONFIG: Record<HealthStatus, { label: string; variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }> = {
  healthy: { label: "Healthy", variant: "default", icon: <CheckCircle className="h-3 w-3" /> },
  degraded: { label: "Degraded", variant: "secondary", icon: <AlertCircle className="h-3 w-3" /> },
  offline: { label: "Offline", variant: "destructive", icon: <XCircle className="h-3 w-3" /> },
  unknown: { label: "Unknown", variant: "outline", icon: <HelpCircle className="h-3 w-3" /> },
};

const DEFAULT_FORM: DataSourceForm = {
  name: "",
  description: "",
  source_type: "fhir_server",
  auth_method: "none",
  base_url: "",
  client_id: "",
  client_secret: "",
  api_key: "",
  username: "",
  password: "",
  token_url: "",
  scopes: "",
  timeout_seconds: 30,
  verify_ssl: true,
  default_batch_size: 100,
  default_retry_count: 3,
};

export default function DataSourcesPage() {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [form, setForm] = useState<DataSourceForm>(DEFAULT_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    loadSources();
  }, []);

  async function loadSources() {
    setLoading(true);
    try {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE_URL}/api/v1/data-sources`, {
        headers: getAuthHeaders(token),
      });
      if (response.ok) {
        const data = await response.json();
        setSources(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      toast.error("Failed to load data sources");
    } finally {
      setLoading(false);
    }
  }

  async function saveSource() {
    setSaving(true);
    try {
      const token = getStoredToken();
      const url = editingId
        ? `${API_BASE_URL}/api/v1/data-sources/${editingId}`
        : `${API_BASE_URL}/api/v1/data-sources`;

      const response = await fetch(url, {
        method: editingId ? "PUT" : "POST",
        headers: getAuthHeaders(token),
        body: JSON.stringify({
          name: form.name,
          description: form.description || null,
          source_type: form.source_type,
          auth_method: form.auth_method,
          base_url: form.base_url || null,
          client_id: form.client_id || null,
          client_secret: form.client_secret || null,
          api_key: form.api_key || null,
          username: form.username || null,
          password: form.password || null,
          token_url: form.token_url || null,
          scopes: form.scopes ? form.scopes.split(/[\s,]+/).filter(Boolean) : [],
          timeout_seconds: form.timeout_seconds,
          verify_ssl: form.verify_ssl,
          default_batch_size: form.default_batch_size,
          default_retry_count: form.default_retry_count,
        }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "Failed to save");
      }

      await loadSources();
      toast.success(editingId ? "Data source updated" : "Data source created");
      closeDialog();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save data source");
    } finally {
      setSaving(false);
    }
  }

  async function deleteSource(id: string) {
    if (!confirm("Are you sure you want to delete this data source?")) return;

    try {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE_URL}/api/v1/data-sources/${id}`, {
        method: "DELETE",
        headers: getAuthHeaders(token),
      });

      if (!response.ok) {
        throw new Error("Failed to delete");
      }

      await loadSources();
      toast.success("Data source deleted");
    } catch (err) {
      toast.error("Failed to delete data source");
    }
  }

  async function testConnection(id: string) {
    setTesting(id);
    try {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE_URL}/api/v1/data-sources/${id}/test`, {
        method: "POST",
        headers: getAuthHeaders(token),
      });

      const result = await response.json();

      if (result.success) {
        toast.success(`Connection successful (${result.latency_ms}ms)`);
      } else {
        toast.error(result.message || "Connection failed");
      }

      await loadSources(); // Refresh to get updated health status
    } catch (err) {
      toast.error("Failed to test connection");
    } finally {
      setTesting(null);
    }
  }

  function openEditDialog(source: DataSource) {
    setEditingId(source.id);
    setForm({
      name: source.name,
      description: source.description || "",
      source_type: source.source_type,
      auth_method: source.auth_method,
      base_url: source.base_url || "",
      client_id: source.client_id || "",
      client_secret: "", // Never prefill secrets
      api_key: "",
      username: "",
      password: "",
      token_url: source.token_url || "",
      scopes: source.scopes?.join(" ") || "",
      timeout_seconds: source.timeout_seconds,
      verify_ssl: source.verify_ssl,
      default_batch_size: source.default_batch_size,
      default_retry_count: source.default_retry_count,
    });
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditingId(null);
    setForm(DEFAULT_FORM);
  }

  function getSourceIcon(type: SourceType) {
    const option = SOURCE_TYPE_OPTIONS.find((o) => o.value === type);
    return option?.icon || <Server className="h-4 w-4" />;
  }

  return (
    <PermissionGate
      permission={PERMISSIONS.ADMIN_MANAGE_USERS}
      hideWhenUnauthenticated={false}
      fallback={
        <div className="p-6">
          <Card>
            <CardContent className="py-8 text-center">
              <Shield className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
              <p className="text-lg font-medium">Admin Access Required</p>
              <p className="text-muted-foreground">You need admin permissions to manage data sources.</p>
            </CardContent>
          </Card>
        </div>
      }
    >
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Data Sources</h1>
            <p className="text-muted-foreground">Configure external data source connections</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={loadSources} disabled={loading}>
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <Button onClick={() => { setEditingId(null); setForm(DEFAULT_FORM); }}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Data Source
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>{editingId ? "Edit Data Source" : "Add Data Source"}</DialogTitle>
                  <DialogDescription>
                    Configure connection to an external data source
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                  {/* Basic Info */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="col-span-2">
                      <Label htmlFor="name">Name</Label>
                      <Input
                        id="name"
                        value={form.name}
                        onChange={(e) => setForm({ ...form, name: e.target.value })}
                        placeholder="My FHIR Server"
                      />
                    </div>

                    <div className="col-span-2">
                      <Label htmlFor="description">Description</Label>
                      <Input
                        id="description"
                        value={form.description}
                        onChange={(e) => setForm({ ...form, description: e.target.value })}
                        placeholder="Production FHIR server for patient data"
                      />
                    </div>

                    <div>
                      <Label htmlFor="source_type">Source Type</Label>
                      <Select
                        value={form.source_type}
                        onValueChange={(v) => setForm({ ...form, source_type: v as SourceType })}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {SOURCE_TYPE_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              <div className="flex items-center gap-2">
                                {opt.icon}
                                {opt.label}
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div>
                      <Label htmlFor="auth_method">Authentication</Label>
                      <Select
                        value={form.auth_method}
                        onValueChange={(v) => setForm({ ...form, auth_method: v as AuthMethod })}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {AUTH_METHOD_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              {opt.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {/* Connection Settings */}
                  <div className="border-t pt-4">
                    <h4 className="font-medium mb-3">Connection Settings</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="col-span-2">
                        <Label htmlFor="base_url">Base URL</Label>
                        <Input
                          id="base_url"
                          value={form.base_url}
                          onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                          placeholder="https://fhir.example.com/r4"
                        />
                      </div>

                      {form.auth_method === "basic" && (
                        <>
                          <div>
                            <Label htmlFor="username">Username</Label>
                            <Input
                              id="username"
                              value={form.username}
                              onChange={(e) => setForm({ ...form, username: e.target.value })}
                            />
                          </div>
                          <div>
                            <Label htmlFor="password">Password</Label>
                            <Input
                              id="password"
                              type="password"
                              value={form.password}
                              onChange={(e) => setForm({ ...form, password: e.target.value })}
                              placeholder={editingId ? "(unchanged)" : ""}
                            />
                          </div>
                        </>
                      )}

                      {(form.auth_method === "bearer_token" || form.auth_method === "api_key") && (
                        <div className="col-span-2">
                          <Label htmlFor="api_key">API Key / Token</Label>
                          <Input
                            id="api_key"
                            type="password"
                            value={form.api_key}
                            onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                            placeholder={editingId ? "(unchanged)" : ""}
                          />
                        </div>
                      )}

                      {(form.auth_method === "oauth2_client_credentials" || form.auth_method === "smart_backend") && (
                        <>
                          <div>
                            <Label htmlFor="client_id">Client ID</Label>
                            <Input
                              id="client_id"
                              value={form.client_id}
                              onChange={(e) => setForm({ ...form, client_id: e.target.value })}
                            />
                          </div>
                          <div>
                            <Label htmlFor="client_secret">Client Secret</Label>
                            <Input
                              id="client_secret"
                              type="password"
                              value={form.client_secret}
                              onChange={(e) => setForm({ ...form, client_secret: e.target.value })}
                              placeholder={editingId ? "(unchanged)" : ""}
                            />
                          </div>
                          <div className="col-span-2">
                            <Label htmlFor="token_url">Token URL</Label>
                            <Input
                              id="token_url"
                              value={form.token_url}
                              onChange={(e) => setForm({ ...form, token_url: e.target.value })}
                              placeholder="https://auth.example.com/oauth2/token"
                            />
                          </div>
                          <div className="col-span-2">
                            <Label htmlFor="scopes">Scopes (space-separated)</Label>
                            <Input
                              id="scopes"
                              value={form.scopes}
                              onChange={(e) => setForm({ ...form, scopes: e.target.value })}
                              placeholder="system/*.read patient/*.read"
                            />
                          </div>
                        </>
                      )}

                      <div>
                        <Label htmlFor="timeout">Timeout (seconds)</Label>
                        <Input
                          id="timeout"
                          type="number"
                          value={form.timeout_seconds}
                          onChange={(e) => setForm({ ...form, timeout_seconds: parseInt(e.target.value) || 30 })}
                        />
                      </div>

                      <div className="flex items-center gap-2 pt-6">
                        <Checkbox
                          id="verify_ssl"
                          checked={form.verify_ssl}
                          onCheckedChange={(c) => setForm({ ...form, verify_ssl: c === true })}
                        />
                        <Label htmlFor="verify_ssl">Verify SSL Certificate</Label>
                      </div>
                    </div>
                  </div>

                  {/* Default Settings */}
                  <div className="border-t pt-4">
                    <h4 className="font-medium mb-3">Default Pipeline Settings</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="batch_size">Batch Size</Label>
                        <Input
                          id="batch_size"
                          type="number"
                          value={form.default_batch_size}
                          onChange={(e) => setForm({ ...form, default_batch_size: parseInt(e.target.value) || 100 })}
                        />
                      </div>
                      <div>
                        <Label htmlFor="retry_count">Retry Count</Label>
                        <Input
                          id="retry_count"
                          type="number"
                          value={form.default_retry_count}
                          onChange={(e) => setForm({ ...form, default_retry_count: parseInt(e.target.value) || 3 })}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <DialogFooter>
                  <Button variant="outline" onClick={closeDialog}>
                    Cancel
                  </Button>
                  <Button onClick={saveSource} disabled={saving || !form.name}>
                    {saving ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      "Save"
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Configured Sources</CardTitle>
            <CardDescription>
              {sources.length} data source{sources.length !== 1 ? "s" : ""} configured
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : sources.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Database className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No data sources configured.</p>
                <p className="text-sm">Click &quot;Add Data Source&quot; to connect to external systems.</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Records</TableHead>
                    <TableHead>Last Connected</TableHead>
                    <TableHead className="w-[150px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sources.map((source) => {
                    const healthConfig = HEALTH_STATUS_CONFIG[source.health_status];
                    return (
                      <TableRow key={source.id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {getSourceIcon(source.source_type)}
                            <div>
                              <div className="font-medium">{source.name}</div>
                              {source.base_url && (
                                <div className="text-xs text-muted-foreground truncate max-w-[200px]">
                                  {source.base_url}
                                </div>
                              )}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {SOURCE_TYPE_OPTIONS.find((o) => o.value === source.source_type)?.label || source.source_type}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant={healthConfig.variant} className="gap-1">
                            {healthConfig.icon}
                            {healthConfig.label}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {source.total_records_imported.toLocaleString()}
                        </TableCell>
                        <TableCell>
                          {source.last_connected_at
                            ? new Date(source.last_connected_at).toLocaleDateString()
                            : "Never"}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => testConnection(source.id)}
                              disabled={testing === source.id}
                              title="Test Connection"
                            >
                              {testing === source.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Play className="h-4 w-4" />
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => openEditDialog(source)}
                              title="Edit"
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-destructive"
                              onClick={() => deleteSource(source.id)}
                              title="Delete"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </PermissionGate>
  );
}
