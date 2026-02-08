"use client";

import { useState } from "react";
import { useBulkScreening, useScreeningResults } from "@/hooks/api/useScreening";
import { useTrials } from "@/hooks/api/useTrials";
import { usePatients } from "@/hooks/api/usePatients";
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
import {
  Target,
  RefreshCw,
  Users,
  CheckCircle2,
  XCircle,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Search,
  Play,
  AlertTriangle,
} from "lucide-react";
import type { BulkScreeningResponse } from "@/lib/api";

// ---------------------------------------------------------------------------
// Status badge styling
// ---------------------------------------------------------------------------

const statusBadge: Record<string, { className: string; icon: React.ReactNode }> = {
  eligible: {
    className: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
    icon: <CheckCircle2 className="mr-1 h-3 w-3" />,
  },
  ineligible: {
    className: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
    icon: <XCircle className="mr-1 h-3 w-3" />,
  },
  unknown: {
    className: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
    icon: <HelpCircle className="mr-1 h-3 w-3" />,
  },
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function BulkScreenPage() {
  // Selection state
  const [selectedPatientIds, setSelectedPatientIds] = useState("");
  const [selectedTrialIds, setSelectedTrialIds] = useState("");
  const [allPatients, setAllPatients] = useState(false);
  const [allTrials, setAllTrials] = useState(false);

  // Results state
  const [lastRun, setLastRun] = useState<BulkScreeningResponse | null>(null);

  // History filters & pagination
  const [page, setPage] = useState(0);
  const [pageSize] = useState(25);
  const [statusFilter, setStatusFilter] = useState("");
  const [triggerFilter, setTriggerFilter] = useState("");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  // Data hooks
  const { data: patientsData } = usePatients({ page: 0, page_size: 10000 });
  const { data: trialsData } = useTrials({ offset: 0, limit: 1000 });
  const bulkScreenMutation = useBulkScreening();

  const { data: historyData, isLoading: historyLoading, refetch: refetchHistory } =
    useScreeningResults({
      status: statusFilter || undefined,
      triggered_by: triggerFilter || undefined,
      offset: page * pageSize,
      limit: pageSize,
    });

  const historyResults = historyData?.results || [];
  const historyTotal = historyData?.total || 0;
  const totalPages = Math.ceil(historyTotal / pageSize);

  // ---------------------------------------------------------------------------
  // Run screening
  // ---------------------------------------------------------------------------

  const handleRunScreening = () => {
    const patientIds = allPatients
      ? (patientsData?.patients || []).map((p: { id: string }) => p.id)
      : selectedPatientIds
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);

    const trialIds = allTrials
      ? (trialsData?.trials || []).map((t: { id: string }) => t.id)
      : selectedTrialIds
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);

    if (patientIds.length === 0 || trialIds.length === 0) return;

    bulkScreenMutation.mutate(
      { patient_ids: patientIds, trial_ids: trialIds },
      {
        onSuccess: (data) => {
          setLastRun(data);
          refetchHistory();
        },
      }
    );
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Bulk Screening</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Screen batches of patients against clinical trials
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetchHistory()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh History
        </Button>
      </div>

      {/* Action Section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Run Bulk Screening</CardTitle>
          <CardDescription>
            Select patients and trials, then run screening
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Patient selection */}
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <label className="text-sm font-medium w-32">Patients</label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={allPatients}
                  onChange={(e) => setAllPatients(e.target.checked)}
                  className="rounded border-input"
                />
                All patients ({patientsData?.patients?.length ?? 0})
              </label>
            </div>
            {!allPatients && (
              <Input
                placeholder="Comma-separated patient IDs..."
                value={selectedPatientIds}
                onChange={(e) => setSelectedPatientIds(e.target.value)}
              />
            )}
          </div>

          {/* Trial selection */}
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <label className="text-sm font-medium w-32">Trials</label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={allTrials}
                  onChange={(e) => setAllTrials(e.target.checked)}
                  className="rounded border-input"
                />
                All active trials ({trialsData?.trials?.length ?? 0})
              </label>
            </div>
            {!allTrials && (
              <Input
                placeholder="Comma-separated trial IDs..."
                value={selectedTrialIds}
                onChange={(e) => setSelectedTrialIds(e.target.value)}
              />
            )}
          </div>

          {/* Run button */}
          <Button
            onClick={handleRunScreening}
            disabled={bulkScreenMutation.isPending}
            className="w-full sm:w-auto"
          >
            {bulkScreenMutation.isPending ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Screening...
              </>
            ) : (
              <>
                <Play className="mr-2 h-4 w-4" />
                Run Bulk Screen
              </>
            )}
          </Button>

          {bulkScreenMutation.isError && (
            <div className="flex items-center gap-2 text-sm text-red-600">
              <AlertTriangle className="h-4 w-4" />
              {(bulkScreenMutation.error as Error)?.message || "Screening failed"}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Summary Cards (after a run completes) */}
      {lastRun && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">
                Total Pairs Screened
              </CardTitle>
              <Target className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {lastRun.summary.total_pairs_screened}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {lastRun.summary.total_patients} patients x{" "}
                {lastRun.summary.total_trials} trials
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Eligible</CardTitle>
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">
                {lastRun.summary.total_eligible}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">
                Pass Rate
              </CardTitle>
              <Users className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">
                {lastRun.summary.overall_pass_rate.toFixed(1)}%
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Duration</CardTitle>
              <RefreshCw className="h-4 w-4 text-purple-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-purple-600">
                {(lastRun.summary.screening_duration_ms / 1000).toFixed(1)}s
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* CDS disclaimer */}
      {lastRun?.requires_clinician_review && (
        <Card className="border-amber-300 bg-amber-50 dark:bg-amber-950/20">
          <CardContent className="pt-4">
            <p className="text-sm text-amber-800 dark:text-amber-300">
              <AlertTriangle className="inline mr-1.5 h-4 w-4" />
              {lastRun.cds_disclaimer}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Screening History Table */}
      <Card>
        <CardHeader>
          <CardTitle>Screening History</CardTitle>
          <CardDescription>
            Showing {historyResults.length} of {historyTotal} results
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="flex gap-4 mb-4">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(0);
              }}
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">All Statuses</option>
              <option value="eligible">Eligible</option>
              <option value="ineligible">Ineligible</option>
              <option value="unknown">Unknown</option>
            </select>
            <select
              value={triggerFilter}
              onChange={(e) => {
                setTriggerFilter(e.target.value);
                setPage(0);
              }}
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">All Triggers</option>
              <option value="webhook">Webhook</option>
              <option value="manual">Manual</option>
              <option value="bulk">Bulk</option>
            </select>
          </div>

          {historyLoading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-muted-foreground">Loading...</span>
            </div>
          ) : historyResults.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              <Search className="mx-auto h-8 w-8 mb-2" />
              No screening results found
            </div>
          ) : (
            <>
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-8" />
                      <TableHead>Patient ID</TableHead>
                      <TableHead>Trial</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Score</TableHead>
                      <TableHead>Inclusion</TableHead>
                      <TableHead>Exclusion</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Trigger</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {historyResults.map((row) => {
                      const badge = statusBadge[row.overall_status] || statusBadge.unknown;
                      const isExpanded = expandedRow === row.id;

                      return (
                        <>
                          <TableRow
                            key={row.id}
                            className="cursor-pointer hover:bg-muted/50"
                            onClick={() =>
                              setExpandedRow(isExpanded ? null : row.id)
                            }
                          >
                            <TableCell>
                              {isExpanded ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </TableCell>
                            <TableCell className="font-mono text-sm">
                              {row.patient_id}
                            </TableCell>
                            <TableCell>
                              <span className="font-medium">
                                {row.trial_name || row.trial_id}
                              </span>
                            </TableCell>
                            <TableCell>
                              <Badge className={badge.className}>
                                {badge.icon}
                                {row.overall_status}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right font-mono">
                              {row.match_score != null
                                ? `${(row.match_score * 100).toFixed(0)}%`
                                : "-"}
                            </TableCell>
                            <TableCell>
                              {row.inclusion_met != null && row.inclusion_total != null
                                ? `${row.inclusion_met}/${row.inclusion_total}`
                                : "-"}
                            </TableCell>
                            <TableCell>
                              {row.exclusion_triggered != null &&
                              row.exclusion_total != null
                                ? `${row.exclusion_triggered}/${row.exclusion_total}`
                                : "-"}
                            </TableCell>
                            <TableCell className="text-sm">
                              {new Date(row.screening_date).toLocaleDateString()}
                            </TableCell>
                            <TableCell>
                              <Badge variant="outline">{row.triggered_by}</Badge>
                            </TableCell>
                          </TableRow>

                          {/* Expanded criterion details */}
                          {isExpanded && (
                            <TableRow key={`${row.id}-detail`}>
                              <TableCell colSpan={9} className="bg-muted/30 p-4">
                                <div className="space-y-2">
                                  {row.notes && (
                                    <p className="text-sm">
                                      <strong>Notes:</strong> {row.notes}
                                    </p>
                                  )}
                                  {row.safety_blocked && (
                                    <p className="text-sm text-red-600 flex items-center gap-1">
                                      <AlertTriangle className="h-4 w-4" />
                                      Safety blocked
                                    </p>
                                  )}
                                  {row.criterion_results ? (
                                    <div>
                                      <h4 className="text-sm font-semibold mb-1">
                                        Criterion Results
                                      </h4>
                                      <pre className="text-xs bg-background rounded p-3 overflow-x-auto border max-h-64 overflow-y-auto">
                                        {JSON.stringify(
                                          row.criterion_results,
                                          null,
                                          2
                                        )}
                                      </pre>
                                    </div>
                                  ) : (
                                    <p className="text-sm text-muted-foreground">
                                      No detailed criterion data available
                                    </p>
                                  )}
                                </div>
                              </TableCell>
                            </TableRow>
                          )}
                        </>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="mt-4 flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    Page {page + 1} of {totalPages}
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page === 0}
                      onClick={() => setPage((p) => Math.max(0, p - 1))}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Prev
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page >= totalPages - 1}
                      onClick={() =>
                        setPage((p) => Math.min(totalPages - 1, p + 1))
                      }
                    >
                      Next
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
