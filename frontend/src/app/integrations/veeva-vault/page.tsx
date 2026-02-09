"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  useVeevaConnectionTest,
  useVeevaStudies,
  useVeevaStudyImport,
  useVeevaScreeningPush,
  useVeevaEnrollmentSync,
  useVeevaStatus,
  useTrials,
} from "@/hooks/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Database,
  RefreshCw,
  CheckCircle,
  XCircle,
  Upload,
  Download,
  ArrowRightLeft,
  Plug,
  Eye,
  EyeOff,
  Clock,
  AlertCircle,
  ExternalLink,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import type {
  VeevaStudyImportResponse,
  VeevaScreeningPushResult,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Connection Tab
// ---------------------------------------------------------------------------

function ConnectionTab() {
  const [vaultUrl, setVaultUrl] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const { data: status, isLoading: statusLoading } = useVeevaStatus();
  const connectionTest = useVeevaConnectionTest();

  const handleTestConnection = () => {
    if (!vaultUrl || !username || !password) {
      toast.error("Please fill in all required fields");
      return;
    }
    connectionTest.mutate(
      { vault_url: vaultUrl, username, password },
      {
        onSuccess: (result) => {
          if (result.connected) {
            toast.success(
              `Connected to Vault (${result.latency_ms}ms) - ${result.studies_count} studies found`
            );
          } else {
            toast.error(`Connection failed: ${result.error}`);
          }
        },
        onError: (err) => {
          toast.error(`Connection test failed: ${(err as Error).message}`);
        },
      }
    );
  };

  return (
    <div className="space-y-6">
      {/* Status Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plug className="h-5 w-5" />
            Connection Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          {statusLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Checking status...
            </div>
          ) : (
            <div className="flex items-center gap-3">
              {status?.connected ? (
                <>
                  <div className="h-3 w-3 rounded-full bg-green-500" />
                  <span className="font-medium text-green-700">Connected</span>
                  {status.vault_url && (
                    <span className="text-sm text-muted-foreground">
                      to {status.vault_url}
                    </span>
                  )}
                </>
              ) : status?.configured ? (
                <>
                  <div className="h-3 w-3 rounded-full bg-yellow-500" />
                  <span className="font-medium text-yellow-700">
                    Configured (not verified)
                  </span>
                </>
              ) : (
                <>
                  <div className="h-3 w-3 rounded-full bg-red-500" />
                  <span className="font-medium text-red-700">
                    Not Connected
                  </span>
                </>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Configuration Form */}
      <Card>
        <CardHeader>
          <CardTitle>Vault Configuration</CardTitle>
          <CardDescription>
            Enter your Veeva Vault CDMS credentials to establish a connection
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="vault-url">Vault URL</Label>
            <Input
              id="vault-url"
              placeholder="https://yourorg.veevavault.com"
              value={vaultUrl}
              onChange={(e) => setVaultUrl(e.target.value)}
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="vault-username">Username</Label>
              <Input
                id="vault-username"
                placeholder="vault_api_user"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="vault-password">Password</Label>
              <div className="relative">
                <Input
                  id="vault-password"
                  type={showPassword ? "text" : "password"}
                  placeholder="********"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-0 top-0 h-full px-3"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </div>

          <div className="flex gap-3 pt-2">
            <Button
              onClick={handleTestConnection}
              disabled={connectionTest.isPending}
            >
              {connectionTest.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Plug className="mr-2 h-4 w-4" />
              )}
              Test Connection
            </Button>
            <Button variant="outline" disabled>
              Save Configuration
            </Button>
          </div>

          {/* Test Results */}
          {connectionTest.data && (
            <div
              className={`mt-4 rounded-lg border p-4 ${
                connectionTest.data.connected
                  ? "border-green-200 bg-green-50"
                  : "border-red-200 bg-red-50"
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                {connectionTest.data.connected ? (
                  <CheckCircle className="h-5 w-5 text-green-600" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-600" />
                )}
                <span className="font-medium">
                  {connectionTest.data.connected
                    ? "Connection Successful"
                    : "Connection Failed"}
                </span>
              </div>
              {connectionTest.data.connected ? (
                <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
                  <div>
                    <span className="text-muted-foreground">Latency:</span>{" "}
                    <span className="font-medium">
                      {connectionTest.data.latency_ms}ms
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Version:</span>{" "}
                    <span className="font-medium">
                      {connectionTest.data.vault_version ?? "N/A"}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Studies:</span>{" "}
                    <span className="font-medium">
                      {connectionTest.data.studies_count}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Session:</span>{" "}
                    <span className="font-medium">
                      {connectionTest.data.session_valid ? "Valid" : "Invalid"}
                    </span>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-red-700">
                  {connectionTest.data.error}
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Study Import Tab
// ---------------------------------------------------------------------------

function StudyImportTab() {
  const {
    data: studiesData,
    isLoading,
    refetch,
  } = useVeevaStudies({ enabled: true });
  const importMutation = useVeevaStudyImport();
  const [importResult, setImportResult] =
    useState<VeevaStudyImportResponse | null>(null);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [selectedStudy, setSelectedStudy] = useState<string | null>(null);

  const studies = studiesData?.studies ?? [];

  const handleImport = (studyName: string) => {
    setSelectedStudy(studyName);
    importMutation.mutate(studyName, {
      onSuccess: (result) => {
        setImportResult(result);
        setShowImportDialog(true);
        if (result.success) {
          toast.success(`Study "${result.study_name}" imported successfully`);
        } else {
          toast.error(`Import failed: ${result.error}`);
        }
      },
      onError: (err) => {
        toast.error(`Import failed: ${(err as Error).message}`);
      },
    });
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Download className="h-5 w-5" />
              Available Vault Studies
            </CardTitle>
            <CardDescription>
              Studies available in your Veeva Vault instance for import
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : studies.length === 0 ? (
            <div className="py-8 text-center">
              <Database className="mx-auto h-10 w-10 text-muted-foreground mb-2" />
              <p className="text-muted-foreground">
                No studies found. Check your Vault connection.
              </p>
            </div>
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Study Name</TableHead>
                    <TableHead>Title</TableHead>
                    <TableHead>Phase</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Subjects</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {studies.map((study) => (
                    <TableRow key={study.study_name}>
                      <TableCell className="font-mono text-sm">
                        {study.study_name}
                      </TableCell>
                      <TableCell className="font-medium">
                        {study.title}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{study.phase}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            study.status === "Active"
                              ? "default"
                              : "secondary"
                          }
                        >
                          {study.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        {study.subject_count}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          onClick={() => handleImport(study.study_name)}
                          disabled={
                            importMutation.isPending &&
                            selectedStudy === study.study_name
                          }
                        >
                          {importMutation.isPending &&
                          selectedStudy === study.study_name ? (
                            <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                          ) : (
                            <Download className="mr-2 h-3 w-3" />
                          )}
                          Import
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Import Result Dialog */}
      <Dialog open={showImportDialog} onOpenChange={setShowImportDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {importResult?.success ? "Import Successful" : "Import Failed"}
            </DialogTitle>
            <DialogDescription>
              {importResult?.success
                ? `Study "${importResult.study_name}" has been imported.`
                : importResult?.error ?? "An error occurred during import."}
            </DialogDescription>
          </DialogHeader>
          {importResult?.success && (
            <div className="space-y-4">
              <div className="rounded-lg border p-3">
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-muted-foreground">Study:</span>{" "}
                    <span className="font-medium">
                      {importResult.study_name}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">
                      Criteria Found:
                    </span>{" "}
                    <span className="font-medium">
                      {importResult.criteria_found}
                    </span>
                  </div>
                </div>
              </div>
              {importResult.mapping_preview.length > 0 && (
                <div>
                  <p className="text-sm font-medium mb-2">Mapping Preview</p>
                  <div className="rounded-lg border max-h-40 overflow-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Vault Field</TableHead>
                          <TableHead>Mapped To</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {importResult.mapping_preview.map((m, i) => (
                          <TableRow key={i}>
                            <TableCell className="font-mono text-xs">
                              {m.vault_field}
                            </TableCell>
                            <TableCell className="text-xs">
                              {m.mapped_to}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            {importResult?.success && importResult.trial_id && (
              <Button asChild variant="outline">
                <Link href={`/trials/${importResult.trial_id}`}>
                  <ExternalLink className="mr-2 h-4 w-4" />
                  View Trial
                </Link>
              </Button>
            )}
            <Button onClick={() => setShowImportDialog(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Screening Export Tab
// ---------------------------------------------------------------------------

function ScreeningExportTab() {
  const { data: trialsData, isLoading: trialsLoading } = useTrials();
  const [selectedTrialId, setSelectedTrialId] = useState<string>("");
  const pushMutation = useVeevaScreeningPush();
  const [pushResults, setPushResults] = useState<VeevaScreeningPushResult[]>([]);

  const trials = trialsData?.trials ?? [];

  const handlePush = () => {
    if (!selectedTrialId) {
      toast.error("Please select a trial");
      return;
    }
    pushMutation.mutate(
      { trial_id: selectedTrialId },
      {
        onSuccess: (result) => {
          setPushResults(result.results);
          toast.success(
            `Pushed ${result.pushed} of ${result.total} results to Vault`
          );
        },
        onError: (err) => {
          toast.error(`Push failed: ${(err as Error).message}`);
        },
      }
    );
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Push Screening Results to Vault
          </CardTitle>
          <CardDescription>
            Select a trial and push screening results to Veeva Vault CDMS
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-end gap-4">
            <div className="flex-1 space-y-2">
              <Label>Select Trial</Label>
              {trialsLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading trials...
                </div>
              ) : (
                <Select
                  value={selectedTrialId}
                  onValueChange={setSelectedTrialId}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a trial..." />
                  </SelectTrigger>
                  <SelectContent>
                    {trials.map((trial) => (
                      <SelectItem key={trial.id} value={trial.id}>
                        {trial.name ?? trial.nct_number ?? trial.id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
            <Button
              onClick={handlePush}
              disabled={!selectedTrialId || pushMutation.isPending}
            >
              {pushMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Upload className="mr-2 h-4 w-4" />
              )}
              Push to Vault
            </Button>
          </div>

          {/* Push summary */}
          {pushMutation.data && (
            <div className="grid gap-4 md:grid-cols-4">
              <div className="rounded-lg border p-3 text-center">
                <p className="text-2xl font-bold">
                  {pushMutation.data.total}
                </p>
                <p className="text-xs text-muted-foreground">Total</p>
              </div>
              <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-center">
                <p className="text-2xl font-bold text-green-700">
                  {pushMutation.data.pushed}
                </p>
                <p className="text-xs text-muted-foreground">Pushed</p>
              </div>
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-center">
                <p className="text-2xl font-bold text-red-700">
                  {pushMutation.data.failed}
                </p>
                <p className="text-xs text-muted-foreground">Failed</p>
              </div>
              <div className="rounded-lg border p-3 text-center">
                <p className="text-2xl font-bold text-muted-foreground">
                  {pushMutation.data.skipped}
                </p>
                <p className="text-xs text-muted-foreground">Skipped</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Results Table */}
      {pushResults.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Push Results</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border max-h-96 overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Patient ID</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Vault Subject ID</TableHead>
                    <TableHead>Error</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pushResults.map((result, i) => (
                    <TableRow key={`${result.patient_id}-${i}`}>
                      <TableCell className="font-mono text-sm">
                        {result.patient_id}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            result.status === "pushed"
                              ? "default"
                              : result.status === "failed"
                                ? "destructive"
                                : "secondary"
                          }
                        >
                          {result.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {result.vault_subject_id ?? "-"}
                      </TableCell>
                      <TableCell className="text-sm text-red-600">
                        {result.error ?? "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Enrollment Sync Tab
// ---------------------------------------------------------------------------

function EnrollmentSyncTab() {
  const {
    data: status,
    isLoading: statusLoading,
    refetch: refetchStatus,
  } = useVeevaStatus();
  const syncMutation = useVeevaEnrollmentSync();
  const [autoRefresh, setAutoRefresh] = useState(false);

  // Auto-refresh status every 30s when toggled on
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      refetchStatus();
    }, 30_000);
    return () => clearInterval(interval);
  }, [autoRefresh, refetchStatus]);

  const handleSync = () => {
    syncMutation.mutate(undefined, {
      onSuccess: (result) => {
        toast.success(
          `Synced ${result.synced} enrollments (${result.pending} pending)`
        );
        refetchStatus();
      },
      onError: (err) => {
        toast.error(`Sync failed: ${(err as Error).message}`);
      },
    });
  };

  const events = syncMutation.data?.events ?? [];

  return (
    <div className="space-y-6">
      {/* Status Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Last Sync</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">
              {statusLoading
                ? "..."
                : status?.last_sync_at
                  ? new Date(status.last_sync_at).toLocaleString()
                  : "Never"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Synced</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {statusLoading ? "..." : status?.synced_count ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Pending</CardTitle>
            <Clock className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">
              {statusLoading ? "..." : status?.pending_count ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Failed</CardTitle>
            <AlertCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {statusLoading ? "..." : status?.failed_count ?? 0}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Sync Controls */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ArrowRightLeft className="h-5 w-5" />
              Enrollment Sync
            </CardTitle>
            <CardDescription>
              Synchronize enrollment status between your system and Veeva Vault
            </CardDescription>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Switch
                id="auto-refresh"
                checked={autoRefresh}
                onCheckedChange={setAutoRefresh}
              />
              <Label htmlFor="auto-refresh" className="text-sm">
                Auto-refresh
              </Label>
            </div>
            <Button onClick={handleSync} disabled={syncMutation.isPending}>
              {syncMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <ArrowRightLeft className="mr-2 h-4 w-4" />
              )}
              Sync Now
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {events.length === 0 ? (
            <p className="py-8 text-center text-muted-foreground">
              No recent sync events. Click &quot;Sync Now&quot; to synchronize.
            </p>
          ) : (
            <div className="rounded-lg border max-h-96 overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Patient ID</TableHead>
                    <TableHead>Vault Subject ID</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Previous Status</TableHead>
                    <TableHead>Synced At</TableHead>
                    <TableHead>Error</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {events.map((event, i) => (
                    <TableRow key={`${event.patient_id}-${i}`}>
                      <TableCell className="font-mono text-sm">
                        {event.patient_id}
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {event.vault_subject_id}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            event.status === "enrolled"
                              ? "default"
                              : event.status === "screen_failed"
                                ? "destructive"
                                : "secondary"
                          }
                        >
                          {event.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {event.previous_status ?? "-"}
                      </TableCell>
                      <TableCell className="text-sm">
                        {new Date(event.synced_at).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-sm text-red-600">
                        {event.error ?? "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function VeevaVaultPage() {
  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Veeva Vault CDMS Integration</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Connect to Veeva Vault CDMS to import studies, push screening
          results, and synchronize enrollment status
        </p>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="connection" className="space-y-6">
        <TabsList>
          <TabsTrigger value="connection">
            <Plug className="mr-2 h-4 w-4" />
            Connection
          </TabsTrigger>
          <TabsTrigger value="study-import">
            <Download className="mr-2 h-4 w-4" />
            Study Import
          </TabsTrigger>
          <TabsTrigger value="screening-export">
            <Upload className="mr-2 h-4 w-4" />
            Screening Export
          </TabsTrigger>
          <TabsTrigger value="enrollment-sync">
            <ArrowRightLeft className="mr-2 h-4 w-4" />
            Enrollment Sync
          </TabsTrigger>
        </TabsList>

        <TabsContent value="connection">
          <ConnectionTab />
        </TabsContent>
        <TabsContent value="study-import">
          <StudyImportTab />
        </TabsContent>
        <TabsContent value="screening-export">
          <ScreeningExportTab />
        </TabsContent>
        <TabsContent value="enrollment-sync">
          <EnrollmentSyncTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
