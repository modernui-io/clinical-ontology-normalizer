"use client";

import { useState } from "react";
import Link from "next/link";
import { useDualEnrollmentCandidates, useTrials } from "@/hooks/api";
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
import {
  GitBranch,
  RefreshCw,
  Users,
  DollarSign,
  ChevronDown,
  ChevronRight,
  Search,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Shield,
} from "lucide-react";
import type {
  DualEnrollmentCandidate,
  AdditionalTrialMatch,
} from "@/lib/api";

const ENROLLMENT_VALUE_PER_PATIENT = 42000;

export default function DualEnrollmentPage() {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [selectedTrialIds, setSelectedTrialIds] = useState<string[]>([]);
  const [minScore, setMinScore] = useState(0.5);

  const { data: trialsData } = useTrials({ limit: 100 });
  const mutation = useDualEnrollmentCandidates();

  const trials = trialsData?.trials || [];
  const candidates = mutation.data?.candidates || [];
  const summary = mutation.data?.summary;
  const totalValue = candidates.reduce(
    (sum, c) => sum + c.total_additional_matches * ENROLLMENT_VALUE_PER_PATIENT,
    0
  );

  const handleFindCandidates = () => {
    mutation.mutate({
      trial_id: selectedTrialIds.length === 1 ? selectedTrialIds[0] : undefined,
      min_match_score: minScore,
    });
  };

  const toggleRow = (patientId: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(patientId)) {
        next.delete(patientId);
      } else {
        next.add(patientId);
      }
      return next;
    });
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dual Enrollment Detection</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Find patients eligible for additional clinical trials
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">
                Patients Checked
              </CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {summary.total_enrolled_patients_checked}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                across {summary.trials_checked} trials
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">
                Dual-Eligible Patients
              </CardTitle>
              <GitBranch className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">
                {summary.total_patients_with_additional_matches}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                could enroll in additional trials
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">
                Additional Matches
              </CardTitle>
              <Search className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">
                {summary.total_additional_matches}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                total cross-trial opportunities
              </p>
            </CardContent>
          </Card>
          <Card className="border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">
                Potential Value
              </CardTitle>
              <DollarSign className="h-4 w-4 text-green-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-700 dark:text-green-400">
                ${totalValue.toLocaleString()}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                at ${ENROLLMENT_VALUE_PER_PATIENT.toLocaleString()} per
                enrollment
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters and Action */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label className="block text-sm font-medium mb-1.5">
                Filter by Trial (optional)
              </label>
              <select
                value={selectedTrialIds[0] || ""}
                onChange={(e) =>
                  setSelectedTrialIds(
                    e.target.value ? [e.target.value] : []
                  )
                }
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">All Recruiting Trials</option>
                {trials
                  .filter((t) => t.status === "recruiting")
                  .map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
              </select>
            </div>
            <div className="w-40">
              <label className="block text-sm font-medium mb-1.5">
                Min Match Score
              </label>
              <select
                value={minScore}
                onChange={(e) => setMinScore(Number(e.target.value))}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value={0}>0% (all)</option>
                <option value={0.25}>25%</option>
                <option value={0.5}>50%</option>
                <option value={0.75}>75%</option>
                <option value={0.9}>90%</option>
              </select>
            </div>
            <Button
              onClick={handleFindCandidates}
              disabled={mutation.isPending}
            >
              {mutation.isPending ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  Scanning...
                </>
              ) : (
                <>
                  <Search className="mr-2 h-4 w-4" />
                  Find Candidates
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* CDS Disclaimer */}
      {mutation.data?.requires_clinician_review && (
        <Card className="border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950">
          <CardContent className="pt-4 pb-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
              <p className="text-sm text-amber-800 dark:text-amber-200">
                {mutation.data.cds_disclaimer}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results Table */}
      <Card>
        <CardHeader>
          <CardTitle>Dual Enrollment Candidates</CardTitle>
          <CardDescription>
            {mutation.data
              ? `${candidates.length} patients with cross-trial eligibility`
              : "Click Find Candidates to scan for dual enrollment opportunities"}
            {summary
              ? ` (screened in ${summary.screening_duration_ms.toFixed(0)}ms)`
              : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {mutation.isPending ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-muted-foreground">
                Scanning enrolled patients for cross-trial eligibility...
              </span>
            </div>
          ) : mutation.isError ? (
            <div className="py-12 text-center text-red-600">
              Error: {mutation.error?.message || "Failed to find candidates"}
            </div>
          ) : candidates.length === 0 && mutation.data ? (
            <div className="py-12 text-center text-muted-foreground">
              No dual enrollment candidates found with current filters
            </div>
          ) : candidates.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              Use the filters above and click Find Candidates to begin
            </div>
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8" />
                    <TableHead>Patient ID</TableHead>
                    <TableHead>Current Trial(s)</TableHead>
                    <TableHead>Additional Eligible Trials</TableHead>
                    <TableHead className="text-right">
                      Best Match Score
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {candidates.map((candidate) => (
                    <CandidateRow
                      key={candidate.patient_id}
                      candidate={candidate}
                      isExpanded={expandedRows.has(candidate.patient_id)}
                      onToggle={() => toggleRow(candidate.patient_id)}
                    />
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

function CandidateRow({
  candidate,
  isExpanded,
  onToggle,
}: {
  candidate: DualEnrollmentCandidate;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const bestScore = Math.max(
    ...candidate.additional_matches.map((m) => m.match_score)
  );

  return (
    <>
      <TableRow
        className="cursor-pointer hover:bg-muted/50"
        onClick={onToggle}
      >
        <TableCell>
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </TableCell>
        <TableCell>
          <Link
            href={`/patients/${candidate.patient_id}`}
            className="font-medium text-blue-600 hover:underline dark:text-blue-400"
            onClick={(e) => e.stopPropagation()}
          >
            {candidate.patient_id.slice(0, 8)}...
          </Link>
        </TableCell>
        <TableCell>
          <div className="flex flex-wrap gap-1">
            {candidate.current_enrollments.map((e) => (
              <Badge key={e.trial_id} variant="secondary" className="text-xs">
                {e.trial_name}
              </Badge>
            ))}
          </div>
        </TableCell>
        <TableCell>
          <div className="flex flex-wrap gap-1">
            {candidate.additional_matches.map((m) => (
              <Badge
                key={m.trial_id}
                className={
                  m.safety_blocked
                    ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300"
                    : m.eligible
                      ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
                      : "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300"
                }
              >
                {m.trial_name}
                <span className="ml-1 opacity-70">
                  {Math.round(m.match_score * 100)}%
                </span>
              </Badge>
            ))}
          </div>
        </TableCell>
        <TableCell className="text-right">
          <span className="font-semibold">
            {Math.round(bestScore * 100)}%
          </span>
        </TableCell>
      </TableRow>

      {/* Expanded Detail */}
      {isExpanded && (
        <TableRow>
          <TableCell colSpan={5} className="bg-muted/30 p-0">
            <div className="p-4 space-y-3">
              {candidate.additional_matches.map((match) => (
                <MatchDetail key={match.trial_id} match={match} />
              ))}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

function MatchDetail({ match }: { match: AdditionalTrialMatch }) {
  return (
    <div className="rounded-lg border bg-background p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="font-medium">{match.trial_name}</span>
          {match.nct_number && (
            <span className="text-xs text-muted-foreground font-mono">
              {match.nct_number}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {match.safety_blocked && (
            <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300">
              <Shield className="mr-1 h-3 w-3" />
              Safety Blocked
            </Badge>
          )}
          <Badge
            className={
              match.eligible
                ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
                : "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300"
            }
          >
            {Math.round(match.match_score * 100)}% match
          </Badge>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {/* Inclusion criteria met */}
        {match.key_criteria_met.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">
              Key Criteria Met
            </p>
            <ul className="space-y-1">
              {match.key_criteria_met.map((criterion, i) => (
                <li key={i} className="flex items-start gap-1.5 text-sm">
                  <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0 mt-0.5" />
                  {criterion}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Exclusion criteria triggered */}
        {match.exclusion_triggered.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">
              Exclusion Criteria Triggered
            </p>
            <ul className="space-y-1">
              {match.exclusion_triggered.map((criterion, i) => (
                <li key={i} className="flex items-start gap-1.5 text-sm">
                  <XCircle className="h-3.5 w-3.5 text-red-500 shrink-0 mt-0.5" />
                  {criterion}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Empty state */}
        {match.key_criteria_met.length === 0 &&
          match.exclusion_triggered.length === 0 && (
            <p className="text-sm text-muted-foreground col-span-2">
              No detailed criteria breakdown available
            </p>
          )}
      </div>
    </div>
  );
}
