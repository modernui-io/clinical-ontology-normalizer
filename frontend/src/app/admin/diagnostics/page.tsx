"use client";

import { useState, useCallback } from "react";
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
import {
  Server,
  Database,
  Activity,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Loader2,
  Settings,
  Workflow,
  Wifi,
  WifiOff,
  Clock,
  Play,
  CheckSquare,
  Square,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

interface ConnectionStatus {
  name: string;
  status: "healthy" | "unhealthy" | "not_configured";
  latency_ms: number | null;
  message: string | null;
}

interface ConnectionsResponse {
  checked_at: string;
  connections: ConnectionStatus[];
  overall: string;
}

interface ConfigCheck {
  key: string;
  status: "ok" | "missing" | "placeholder";
  hint: string | null;
}

interface ConfigResponse {
  checked_at: string;
  checks: ConfigCheck[];
  overall: string;
}

interface PipelineTestStep {
  step: string;
  status: "pass" | "fail" | "skip";
  duration_ms: number | null;
  message: string | null;
}

interface PipelineTestResponse {
  tested_at: string;
  steps: PipelineTestStep[];
  overall: string;
}

// =============================================================================
// Static checklist
// =============================================================================

interface ChecklistItem {
  label: string;
  description: string;
}

const INTEGRATION_CHECKLIST: ChecklistItem[] = [
  {
    label: "Data contract verified",
    description:
      "Input/output schemas match the documented API contract for your integration.",
  },
  {
    label: "Validation rules configured",
    description:
      "Custom validation rules are set up for your data domain and document types.",
  },
  {
    label: "Rollback procedure documented",
    description:
      "A documented process exists to revert changes if integration issues arise.",
  },
  {
    label: "Error handling tested",
    description:
      "Malformed inputs, timeouts, and upstream failures produce clear error messages.",
  },
  {
    label: "Audit logging confirmed",
    description:
      "All API calls from your integration are captured in the audit log with correct user context.",
  },
  {
    label: "Rate limits understood",
    description:
      "Your integration respects the configured rate limits and handles 429 responses gracefully.",
  },
];

// =============================================================================
// Helpers
// =============================================================================

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function statusIcon(s: string) {
  switch (s) {
    case "healthy":
    case "ok":
    case "pass":
      return <CheckCircle className="h-4 w-4 text-green-600" />;
    case "unhealthy":
    case "errors":
    case "fail":
      return <XCircle className="h-4 w-4 text-red-600" />;
    case "degraded":
    case "warnings":
    case "partial":
      return <AlertTriangle className="h-4 w-4 text-yellow-600" />;
    case "not_configured":
    case "missing":
    case "placeholder":
      return <AlertTriangle className="h-4 w-4 text-muted-foreground" />;
    default:
      return <Activity className="h-4 w-4 text-muted-foreground" />;
  }
}

function statusBadge(s: string) {
  const variant =
    s === "healthy" || s === "ok" || s === "pass"
      ? "default"
      : s === "unhealthy" || s === "errors" || s === "fail"
        ? "destructive"
        : "secondary";
  return <Badge variant={variant}>{s}</Badge>;
}

// =============================================================================
// Component
// =============================================================================

export default function DiagnosticsPage() {
  const [connections, setConnections] = useState<ConnectionsResponse | null>(
    null,
  );
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [pipeline, setPipeline] = useState<PipelineTestResponse | null>(null);
  const [loadingConn, setLoadingConn] = useState(false);
  const [loadingConfig, setLoadingConfig] = useState(false);
  const [loadingPipeline, setLoadingPipeline] = useState(false);
  const [checkedItems, setCheckedItems] = useState<Set<number>>(new Set());

  const fetchConnections = useCallback(async () => {
    setLoadingConn(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/diagnostics/connections`);
      if (res.ok) {
        setConnections(await res.json());
      }
    } catch {
      // network error — show nothing
    } finally {
      setLoadingConn(false);
    }
  }, []);

  const fetchConfig = useCallback(async () => {
    setLoadingConfig(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/diagnostics/config`);
      if (res.ok) {
        setConfig(await res.json());
      }
    } catch {
      // network error
    } finally {
      setLoadingConfig(false);
    }
  }, []);

  const runPipeline = useCallback(async () => {
    setLoadingPipeline(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/diagnostics/pipeline-test`);
      if (res.ok) {
        setPipeline(await res.json());
      }
    } catch {
      // network error
    } finally {
      setLoadingPipeline(false);
    }
  }, []);

  const toggleChecklist = (idx: number) => {
    setCheckedItems((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Server className="h-6 w-6" />
          Integration Diagnostics
        </h1>
        <p className="text-muted-foreground mt-1">
          Self-serve diagnostics for onboarding teams. Check connections,
          validate configuration, and run pipeline smoke tests.
        </p>
      </div>

      {/* Connection Status */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Wifi className="h-5 w-5" />
              Connection Status
            </CardTitle>
            <CardDescription>
              Connectivity to PostgreSQL, Redis, Neo4j, and Kafka
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchConnections}
            disabled={loadingConn}
          >
            {loadingConn ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-1" />
            )}
            Check
          </Button>
        </CardHeader>
        <CardContent>
          {connections ? (
            <>
              <div className="flex items-center gap-2 mb-3">
                {statusIcon(connections.overall)}
                <span className="text-sm font-medium">
                  Overall: {statusBadge(connections.overall)}
                </span>
                <span className="text-xs text-muted-foreground ml-auto">
                  {new Date(connections.checked_at).toLocaleString()}
                </span>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Service</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Latency</TableHead>
                    <TableHead>Message</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {connections.connections.map((c) => (
                    <TableRow key={c.name}>
                      <TableCell className="font-medium flex items-center gap-2">
                        <Database className="h-4 w-4 text-muted-foreground" />
                        {c.name}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          {statusIcon(c.status)}
                          {c.status}
                        </div>
                      </TableCell>
                      <TableCell>
                        {c.latency_ms != null ? `${c.latency_ms} ms` : "-"}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                        {c.message || "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          ) : (
            <p className="text-sm text-muted-foreground py-4 text-center">
              Click &quot;Check&quot; to test dependency connections.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Configuration Validation */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Configuration Validation
            </CardTitle>
            <CardDescription>
              Required environment variables and credential checks
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchConfig}
            disabled={loadingConfig}
          >
            {loadingConfig ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-1" />
            )}
            Validate
          </Button>
        </CardHeader>
        <CardContent>
          {config ? (
            <>
              <div className="flex items-center gap-2 mb-3">
                {statusIcon(config.overall)}
                <span className="text-sm font-medium">
                  Overall: {statusBadge(config.overall)}
                </span>
                <span className="text-xs text-muted-foreground ml-auto">
                  {new Date(config.checked_at).toLocaleString()}
                </span>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Config Key</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Details</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {config.checks.map((c) => (
                    <TableRow key={c.key}>
                      <TableCell className="font-mono text-sm">
                        {c.key}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          {statusIcon(c.status)}
                          {c.status}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {c.hint || "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          ) : (
            <p className="text-sm text-muted-foreground py-4 text-center">
              Click &quot;Validate&quot; to check environment configuration.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Pipeline Smoke Test */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Workflow className="h-5 w-5" />
              Pipeline Smoke Test
            </CardTitle>
            <CardDescription>
              Submit a test document and trace it through NLP, mapping, fact
              building, and graph construction
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={runPipeline}
            disabled={loadingPipeline}
          >
            {loadingPipeline ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1" />
            ) : (
              <Play className="h-4 w-4 mr-1" />
            )}
            Run Test
          </Button>
        </CardHeader>
        <CardContent>
          {pipeline ? (
            <>
              <div className="flex items-center gap-2 mb-3">
                {statusIcon(pipeline.overall)}
                <span className="text-sm font-medium">
                  Overall: {statusBadge(pipeline.overall)}
                </span>
                <span className="text-xs text-muted-foreground ml-auto">
                  {new Date(pipeline.tested_at).toLocaleString()}
                </span>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Step</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Message</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pipeline.steps.map((s) => (
                    <TableRow key={s.step}>
                      <TableCell className="font-medium">{s.step}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          {statusIcon(s.status)}
                          {s.status}
                        </div>
                      </TableCell>
                      <TableCell>
                        {s.duration_ms != null ? (
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {s.duration_ms} ms
                          </span>
                        ) : (
                          "-"
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                        {s.message || "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          ) : (
            <p className="text-sm text-muted-foreground py-4 text-center">
              Click &quot;Run Test&quot; to execute a pipeline smoke test.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Integration Checklist */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckSquare className="h-5 w-5" />
            Integration Checklist
          </CardTitle>
          <CardDescription>
            Track onboarding readiness for your integration
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {INTEGRATION_CHECKLIST.map((item, idx) => (
              <div
                key={idx}
                className="flex items-start gap-3 cursor-pointer group"
                onClick={() => toggleChecklist(idx)}
              >
                {checkedItems.has(idx) ? (
                  <CheckSquare className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
                ) : (
                  <Square className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0 group-hover:text-foreground" />
                )}
                <div>
                  <p
                    className={`text-sm font-medium ${checkedItems.has(idx) ? "line-through text-muted-foreground" : ""}`}
                  >
                    {item.label}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {item.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-3 border-t text-sm text-muted-foreground">
            {checkedItems.size} of {INTEGRATION_CHECKLIST.length} items
            completed
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
