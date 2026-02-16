"use client";

/**
 * OpenEHR Operations — Dry-Run Import, Reconciliation, Batch Rollback
 *
 * Operator UI for the three P0-019 backend capabilities. Falls back to
 * client-side demo mode when the API is unavailable.
 */

import { useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertCircle,
  CheckCircle,
  Loader2,
  Play,
  RotateCcw,
  Trash2,
  XCircle,
  FileJson,
  ArrowLeftRight,
} from "lucide-react";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Shared helpers (same pattern as ../page.tsx)
// ---------------------------------------------------------------------------

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem("auth_tokens");
    if (stored) {
      const tokens = JSON.parse(stored);
      return tokens.access_token || null;
    }
  } catch {
    // Ignore
  }
  return null;
}

function getAuthHeaders(token: string | null): HeadersInit {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

// ---------------------------------------------------------------------------
// Types (mirrors backend schemas)
// ---------------------------------------------------------------------------

interface DryRunResult {
  success: boolean;
  patient_id: string | null;
  conditions: number;
  medications: number;
  measurements: number;
  procedures: number;
  allergies: number;
  nodes: number;
  edges: number;
  skipped: number;
  error: string | null;
}

interface ReconciliationResult {
  patient_id: string;
  match: boolean;
  import_fingerprint: string;
  export_reimport_fingerprint: string;
  import_row_counts: Record<string, number>;
  reimport_row_counts: Record<string, number>;
  mismatches: string[];
}

interface RollbackResult {
  patient_id: string;
  success: boolean;
  facts_deleted: number;
  nodes_deleted: number;
  edges_deleted: number;
  error: string | null;
}

// ---------------------------------------------------------------------------
// Demo data (used when API is unavailable)
// ---------------------------------------------------------------------------

const DEMO_COMPOSITION = JSON.stringify(
  {
    _type: "COMPOSITION",
    archetype_node_id: "openEHR-EHR-COMPOSITION.encounter.v1",
    name: { _type: "DV_TEXT", value: "Clinical Encounter" },
    language: {
      _type: "CODE_PHRASE",
      terminology_id: { value: "ISO_639-1" },
      code_string: "en",
    },
    territory: {
      _type: "CODE_PHRASE",
      terminology_id: { value: "ISO_3166-1" },
      code_string: "US",
    },
    category: {
      _type: "DV_CODED_TEXT",
      value: "event",
      defining_code: {
        terminology_id: { value: "openehr" },
        code_string: "433",
      },
    },
    composer: { _type: "PARTY_IDENTIFIED", name: "Dr. Smith" },
    context: {
      _type: "EVENT_CONTEXT",
      start_time: { _type: "DV_DATE_TIME", value: "2025-01-15T09:30:00Z" },
      setting: {
        _type: "DV_CODED_TEXT",
        value: "primary medical care",
        defining_code: {
          terminology_id: { value: "openehr" },
          code_string: "228",
        },
      },
    },
    content: [
      {
        _type: "EVALUATION",
        archetype_node_id: "openEHR-EHR-EVALUATION.problem_diagnosis.v1",
        name: { _type: "DV_TEXT", value: "Problem/Diagnosis" },
        data: {
          _type: "ITEM_TREE",
          items: [
            {
              _type: "ELEMENT",
              name: { _type: "DV_TEXT", value: "Problem/Diagnosis name" },
              value: {
                _type: "DV_CODED_TEXT",
                value: "Type 2 diabetes mellitus",
                defining_code: {
                  terminology_id: { value: "SNOMED-CT" },
                  code_string: "44054006",
                },
              },
            },
          ],
        },
      },
      {
        _type: "INSTRUCTION",
        archetype_node_id: "openEHR-EHR-INSTRUCTION.medication_order.v3",
        name: { _type: "DV_TEXT", value: "Medication order" },
        activities: [
          {
            _type: "ACTIVITY",
            description: {
              _type: "ITEM_TREE",
              items: [
                {
                  _type: "ELEMENT",
                  name: { _type: "DV_TEXT", value: "Medication item" },
                  value: {
                    _type: "DV_CODED_TEXT",
                    value: "Metformin 500 MG Oral Tablet",
                    defining_code: {
                      terminology_id: { value: "RxNorm" },
                      code_string: "861004",
                    },
                  },
                },
              ],
            },
          },
        ],
      },
    ],
  },
  null,
  2,
);

function demoDryRunResult(patientId: string): DryRunResult {
  return {
    success: true,
    patient_id: patientId,
    conditions: 1,
    medications: 1,
    measurements: 0,
    procedures: 0,
    allergies: 0,
    nodes: 4,
    edges: 3,
    skipped: 0,
    error: null,
  };
}

function demoReconciliationResult(patientId: string): ReconciliationResult {
  return {
    patient_id: patientId,
    match: true,
    import_fingerprint: "a3f8c2e1d9b7..sha256",
    export_reimport_fingerprint: "a3f8c2e1d9b7..sha256",
    import_row_counts: {
      conditions: 3,
      medications: 2,
      measurements: 1,
      procedures: 0,
      allergies: 1,
    },
    reimport_row_counts: {
      conditions: 3,
      medications: 2,
      measurements: 1,
      procedures: 0,
      allergies: 1,
    },
    mismatches: [],
  };
}

function demoRollbackResult(patientId: string): RollbackResult {
  return {
    patient_id: patientId,
    success: true,
    facts_deleted: 7,
    nodes_deleted: 4,
    edges_deleted: 3,
    error: null,
  };
}

// ---------------------------------------------------------------------------
// Stat card helper
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  variant = "default",
}: {
  label: string;
  value: number;
  variant?: "default" | "destructive";
}) {
  return (
    <Card
      className={
        variant === "destructive" ? "border-red-200 dark:border-red-900" : ""
      }
    >
      <CardContent className="p-4 text-center">
        <p className="text-2xl font-bold tabular-nums">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function OpenEHROpsPage() {
  // Shared
  const [demoMode, setDemoMode] = useState(false);

  // Tab 1 — Dry Run
  const [dryPatientId, setDryPatientId] = useState("patient-demo-001");
  const [compositionJson, setCompositionJson] = useState("");
  const [dryLoading, setDryLoading] = useState(false);
  const [dryResult, setDryResult] = useState<DryRunResult | null>(null);

  // Tab 2 — Reconciliation
  const [reconPatientId, setReconPatientId] = useState("patient-demo-001");
  const [reconLoading, setReconLoading] = useState(false);
  const [reconResult, setReconResult] = useState<ReconciliationResult | null>(
    null,
  );

  // Tab 3 — Rollback
  const [rollPatientId, setRollPatientId] = useState("patient-demo-001");
  const [rollBatchStart, setRollBatchStart] = useState("");
  const [rollBatchEnd, setRollBatchEnd] = useState("");
  const [rollLoading, setRollLoading] = useState(false);
  const [rollResult, setRollResult] = useState<RollbackResult | null>(null);
  const [rollConfirmOpen, setRollConfirmOpen] = useState(false);

  // ------- Dry Run handler -------
  const handleDryRun = async () => {
    if (!dryPatientId.trim()) {
      toast.error("Patient ID is required");
      return;
    }
    let composition: Record<string, unknown>;
    try {
      composition = JSON.parse(compositionJson || "{}");
    } catch {
      toast.error("Invalid JSON in composition field");
      return;
    }

    setDryLoading(true);
    setDryResult(null);
    setDemoMode(false);

    try {
      const token = getStoredToken();
      const res = await fetch(`${API_BASE_URL}/api/v1/openehr/dry-run`, {
        method: "POST",
        headers: getAuthHeaders(token),
        body: JSON.stringify({
          patient_id: dryPatientId.trim(),
          composition,
        }),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const data: DryRunResult = await res.json();
      setDryResult(data);
      if (data.success) {
        toast.success("Dry run completed successfully");
      } else {
        toast.error(data.error || "Dry run failed");
      }
    } catch {
      setDemoMode(true);
      const demo = demoDryRunResult(dryPatientId.trim());
      setDryResult(demo);
      toast.info("Using client-side demo mode (API unavailable)");
    } finally {
      setDryLoading(false);
    }
  };

  // ------- Reconciliation handler -------
  const handleReconciliation = async () => {
    if (!reconPatientId.trim()) {
      toast.error("Patient ID is required");
      return;
    }

    setReconLoading(true);
    setReconResult(null);
    setDemoMode(false);

    try {
      const token = getStoredToken();
      const res = await fetch(
        `${API_BASE_URL}/api/v1/openehr/reconcile/${encodeURIComponent(reconPatientId.trim())}`,
        {
          method: "POST",
          headers: getAuthHeaders(token),
        },
      );
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const data: ReconciliationResult = await res.json();
      setReconResult(data);
      if (data.match) {
        toast.success("Round-trip reconciliation passed");
      } else {
        toast.warning("Mismatches detected");
      }
    } catch {
      setDemoMode(true);
      const demo = demoReconciliationResult(reconPatientId.trim());
      setReconResult(demo);
      toast.info("Using client-side demo mode (API unavailable)");
    } finally {
      setReconLoading(false);
    }
  };

  // ------- Rollback handler -------
  const handleRollback = async () => {
    setRollConfirmOpen(false);

    if (!rollPatientId.trim()) {
      toast.error("Patient ID is required");
      return;
    }
    if (!rollBatchStart || !rollBatchEnd) {
      toast.error("Batch start and end times are required");
      return;
    }

    setRollLoading(true);
    setRollResult(null);
    setDemoMode(false);

    try {
      const token = getStoredToken();
      const res = await fetch(`${API_BASE_URL}/api/v1/openehr/rollback`, {
        method: "POST",
        headers: getAuthHeaders(token),
        body: JSON.stringify({
          patient_id: rollPatientId.trim(),
          batch_start: new Date(rollBatchStart).toISOString(),
          batch_end: new Date(rollBatchEnd).toISOString(),
        }),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const data: RollbackResult = await res.json();
      setRollResult(data);
      if (data.success) {
        toast.success("Batch rollback completed");
      } else {
        toast.error(data.error || "Rollback failed");
      }
    } catch {
      setDemoMode(true);
      const demo = demoRollbackResult(rollPatientId.trim());
      setRollResult(demo);
      toast.info("Using client-side demo mode (API unavailable)");
    } finally {
      setRollLoading(false);
    }
  };

  return (
    <div className="container mx-auto max-w-5xl space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          OpenEHR Operations
        </h1>
        <p className="mt-1 text-muted-foreground">
          Dry-run imports, round-trip reconciliation, and batch rollback for
          OpenEHR data pipelines.
        </p>
      </div>

      {/* Demo mode banner */}
      {demoMode && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>
            <strong>Client-side demo mode</strong> — API is unavailable.
            Showing simulated results.
          </span>
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="dry-run" className="space-y-4">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="dry-run" className="gap-2">
            <Play className="h-4 w-4" />
            Dry Run
          </TabsTrigger>
          <TabsTrigger value="reconciliation" className="gap-2">
            <ArrowLeftRight className="h-4 w-4" />
            Reconciliation
          </TabsTrigger>
          <TabsTrigger value="rollback" className="gap-2">
            <RotateCcw className="h-4 w-4" />
            Rollback
          </TabsTrigger>
        </TabsList>

        {/* ================================================================
            TAB 1 — Dry Run Import
            ================================================================ */}
        <TabsContent value="dry-run" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Dry Run Import</CardTitle>
              <CardDescription>
                Simulate an OpenEHR COMPOSITION import without persisting data.
                Validates parsing, mapping, and graph construction.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="dry-patient-id">Patient ID</Label>
                <Input
                  id="dry-patient-id"
                  placeholder="patient-demo-001"
                  value={dryPatientId}
                  onChange={(e) => setDryPatientId(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="dry-composition">COMPOSITION JSON</Label>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCompositionJson(DEMO_COMPOSITION)}
                  >
                    <FileJson className="mr-2 h-3.5 w-3.5" />
                    Load Demo
                  </Button>
                </div>
                <textarea
                  id="dry-composition"
                  className="h-64 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  placeholder='{"_type": "COMPOSITION", ...}'
                  value={compositionJson}
                  onChange={(e) => setCompositionJson(e.target.value)}
                />
              </div>

              <Button onClick={handleDryRun} disabled={dryLoading}>
                {dryLoading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Play className="mr-2 h-4 w-4" />
                )}
                Dry Run
              </Button>
            </CardContent>
          </Card>

          {/* Dry Run Results */}
          {dryResult && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {dryResult.success ? (
                    <CheckCircle className="h-5 w-5 text-green-600" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-600" />
                  )}
                  {dryResult.success ? "Dry Run Passed" : "Dry Run Failed"}
                </CardTitle>
                {dryResult.error && (
                  <p className="text-sm text-red-600">{dryResult.error}</p>
                )}
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
                  <StatCard label="Conditions" value={dryResult.conditions} />
                  <StatCard
                    label="Medications"
                    value={dryResult.medications}
                  />
                  <StatCard
                    label="Measurements"
                    value={dryResult.measurements}
                  />
                  <StatCard label="Procedures" value={dryResult.procedures} />
                  <StatCard label="Allergies" value={dryResult.allergies} />
                  <StatCard label="KG Nodes" value={dryResult.nodes} />
                  <StatCard label="KG Edges" value={dryResult.edges} />
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ================================================================
            TAB 2 — Reconciliation
            ================================================================ */}
        <TabsContent value="reconciliation" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Round-Trip Reconciliation</CardTitle>
              <CardDescription>
                Import, export, and re-import a patient&apos;s data to verify
                round-trip fidelity. Compares fingerprints and row counts.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="recon-patient-id">Patient ID</Label>
                <Input
                  id="recon-patient-id"
                  placeholder="patient-demo-001"
                  value={reconPatientId}
                  onChange={(e) => setReconPatientId(e.target.value)}
                />
              </div>

              <Button onClick={handleReconciliation} disabled={reconLoading}>
                {reconLoading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <ArrowLeftRight className="mr-2 h-4 w-4" />
                )}
                Run Reconciliation
              </Button>
            </CardContent>
          </Card>

          {/* Reconciliation Results */}
          {reconResult && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {reconResult.match ? (
                    <CheckCircle className="h-5 w-5 text-green-600" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-600" />
                  )}
                  {reconResult.match
                    ? "Round-Trip Match"
                    : "Mismatches Detected"}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Fingerprint comparison */}
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">
                      Import Fingerprint
                    </p>
                    <div
                      className={`rounded-md border-2 p-3 font-mono text-xs break-all ${
                        reconResult.match
                          ? "border-green-300 bg-green-50 dark:border-green-800 dark:bg-green-950"
                          : "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950"
                      }`}
                    >
                      {reconResult.import_fingerprint}
                    </div>
                  </div>
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">
                      Export → Re-Import Fingerprint
                    </p>
                    <div
                      className={`rounded-md border-2 p-3 font-mono text-xs break-all ${
                        reconResult.match
                          ? "border-green-300 bg-green-50 dark:border-green-800 dark:bg-green-950"
                          : "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950"
                      }`}
                    >
                      {reconResult.export_reimport_fingerprint}
                    </div>
                  </div>
                </div>

                {/* Row count comparison table */}
                <div>
                  <p className="mb-2 text-sm font-medium">
                    Row Count Comparison
                  </p>
                  <div className="overflow-x-auto rounded-md border">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-muted/50">
                          <th className="px-4 py-2 text-left font-medium">
                            Domain
                          </th>
                          <th className="px-4 py-2 text-right font-medium">
                            Import
                          </th>
                          <th className="px-4 py-2 text-right font-medium">
                            Re-Import
                          </th>
                          <th className="px-4 py-2 text-center font-medium">
                            Match
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.keys(reconResult.import_row_counts).map(
                          (domain) => {
                            const imp =
                              reconResult.import_row_counts[domain] ?? 0;
                            const reimp =
                              reconResult.reimport_row_counts[domain] ?? 0;
                            const matches = imp === reimp;
                            return (
                              <tr key={domain} className="border-b last:border-0">
                                <td className="px-4 py-2 capitalize">
                                  {domain}
                                </td>
                                <td className="px-4 py-2 text-right tabular-nums">
                                  {imp}
                                </td>
                                <td className="px-4 py-2 text-right tabular-nums">
                                  {reimp}
                                </td>
                                <td className="px-4 py-2 text-center">
                                  {matches ? (
                                    <CheckCircle className="mx-auto h-4 w-4 text-green-600" />
                                  ) : (
                                    <XCircle className="mx-auto h-4 w-4 text-red-600" />
                                  )}
                                </td>
                              </tr>
                            );
                          },
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Mismatches list */}
                {reconResult.mismatches.length > 0 && (
                  <div>
                    <p className="mb-2 text-sm font-medium text-red-600">
                      Mismatches ({reconResult.mismatches.length})
                    </p>
                    <ul className="space-y-1">
                      {reconResult.mismatches.map((m, i) => (
                        <li
                          key={i}
                          className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
                        >
                          <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                          {m}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ================================================================
            TAB 3 — Batch Rollback
            ================================================================ */}
        <TabsContent value="rollback" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Batch Rollback</CardTitle>
              <CardDescription>
                Roll back all OpenEHR-imported facts, KG nodes, and KG edges
                for a patient within a time window.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Warning banner */}
              <div className="flex items-center gap-2 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-700 dark:bg-red-950 dark:text-red-200">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>
                  <strong>Destructive action</strong> — This permanently
                  deletes clinical facts and knowledge graph data. This cannot
                  be undone.
                </span>
              </div>

              <div className="space-y-2">
                <Label htmlFor="roll-patient-id">Patient ID</Label>
                <Input
                  id="roll-patient-id"
                  placeholder="patient-demo-001"
                  value={rollPatientId}
                  onChange={(e) => setRollPatientId(e.target.value)}
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="roll-batch-start">Batch Start</Label>
                  <Input
                    id="roll-batch-start"
                    type="datetime-local"
                    value={rollBatchStart}
                    onChange={(e) => setRollBatchStart(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="roll-batch-end">Batch End</Label>
                  <Input
                    id="roll-batch-end"
                    type="datetime-local"
                    value={rollBatchEnd}
                    onChange={(e) => setRollBatchEnd(e.target.value)}
                  />
                </div>
              </div>

              <Button
                variant="destructive"
                onClick={() => setRollConfirmOpen(true)}
                disabled={rollLoading}
              >
                {rollLoading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="mr-2 h-4 w-4" />
                )}
                Rollback Batch
              </Button>
            </CardContent>
          </Card>

          {/* Rollback confirmation dialog */}
          <Dialog open={rollConfirmOpen} onOpenChange={setRollConfirmOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Confirm Batch Rollback</DialogTitle>
                <DialogDescription>
                  This will permanently delete all OpenEHR-imported data for
                  the specified patient and time range. This action cannot be
                  undone.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-2 rounded-md border bg-muted/50 p-3 text-sm">
                <p>
                  <strong>Patient:</strong> {rollPatientId || "—"}
                </p>
                <p>
                  <strong>From:</strong>{" "}
                  {rollBatchStart
                    ? new Date(rollBatchStart).toLocaleString()
                    : "—"}
                </p>
                <p>
                  <strong>To:</strong>{" "}
                  {rollBatchEnd
                    ? new Date(rollBatchEnd).toLocaleString()
                    : "—"}
                </p>
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setRollConfirmOpen(false)}
                >
                  Cancel
                </Button>
                <Button variant="destructive" onClick={handleRollback}>
                  <Trash2 className="mr-2 h-4 w-4" />
                  Confirm Rollback
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* Rollback Results */}
          {rollResult && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {rollResult.success ? (
                    <CheckCircle className="h-5 w-5 text-green-600" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-600" />
                  )}
                  {rollResult.success
                    ? "Rollback Complete"
                    : "Rollback Failed"}
                  {rollResult.success && (
                    <Badge variant="outline" className="ml-2 text-xs">
                      {rollResult.patient_id}
                    </Badge>
                  )}
                </CardTitle>
                {rollResult.error && (
                  <p className="text-sm text-red-600">{rollResult.error}</p>
                )}
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-3">
                  <StatCard
                    label="Facts Deleted"
                    value={rollResult.facts_deleted}
                    variant="destructive"
                  />
                  <StatCard
                    label="Nodes Deleted"
                    value={rollResult.nodes_deleted}
                    variant="destructive"
                  />
                  <StatCard
                    label="Edges Deleted"
                    value={rollResult.edges_deleted}
                    variant="destructive"
                  />
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
