"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  useTrial,
  useTrialDashboard,
  useTrialScreening,
  useTrialEnrollments,
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ArrowLeft,
  RefreshCw,
  Users,
  Target,
  Activity,
  ClipboardList,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Play,
  BarChart3,
} from "lucide-react";

const statusColors: Record<string, string> = {
  recruiting: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  active: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  completed: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300",
  suspended: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  closed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
};

const enrollmentStatusColors: Record<string, string> = {
  candidate: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300",
  screened: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  eligible: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  enrolled: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-300",
  active: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  completed: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300",
  withdrawn: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  screen_failed: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300",
};

const phaseLabels: Record<string, string> = {
  phase_1: "Phase I",
  phase_2: "Phase II",
  phase_3: "Phase III",
  phase_4: "Phase IV",
};

export default function TrialDetailPage() {
  const params = useParams();
  const trialId = params.id as string;
  const [activeTab, setActiveTab] = useState("overview");

  const { data: trial, isLoading: trialLoading } = useTrial(trialId);
  const { data: dashboard } = useTrialDashboard(trialId);
  const { data: enrollments } = useTrialEnrollments(trialId, { limit: 100 });
  const screening = useTrialScreening(trialId);

  if (trialLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading trial...</span>
      </div>
    );
  }

  if (!trial) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Trial not found.</p>
        <Link href="/trials">
          <Button variant="outline" className="mt-4">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Trials
          </Button>
        </Link>
      </div>
    );
  }

  const progressPercent = dashboard?.enrollment_progress ?? 0;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Link href="/trials">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-1 h-4 w-4" />
                Trials
              </Button>
            </Link>
          </div>
          <h1 className="text-2xl font-bold">{trial.name}</h1>
          <div className="flex items-center gap-3 mt-2">
            {trial.nct_number && (
              <Badge variant="outline" className="font-mono">
                {trial.nct_number}
              </Badge>
            )}
            <Badge className={statusColors[trial.status] || ""}>
              {trial.status}
            </Badge>
            <Badge variant="outline">
              {phaseLabels[trial.phase] || trial.phase}
            </Badge>
            <span className="text-sm text-muted-foreground">
              Sponsor: {trial.sponsor}
            </span>
          </div>
        </div>
        <Button
          onClick={() => screening.mutate()}
          disabled={screening.isPending}
        >
          {screening.isPending ? (
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Play className="mr-2 h-4 w-4" />
          )}
          Screen Patients
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Enrollment Target</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{trial.enrollment_target}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {trial.site_count} site{trial.site_count !== 1 ? "s" : ""}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Enrolled</CardTitle>
            <Users className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {trial.enrolled_count}
            </div>
            <div className="mt-2 h-2 w-full rounded-full bg-gray-200 dark:bg-gray-700">
              <div
                className="h-full rounded-full bg-blue-500 transition-all"
                style={{ width: `${Math.min(100, progressPercent)}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {progressPercent.toFixed(0)}% of target
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active</CardTitle>
            <Activity className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {dashboard?.total_active ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Candidates</CardTitle>
            <ClipboardList className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">
              {dashboard?.total_candidates ?? 0}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview" className="flex items-center gap-2">
            <ClipboardList className="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="eligibility" className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            Eligibility Criteria
          </TabsTrigger>
          <TabsTrigger value="candidates" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            Candidates
          </TabsTrigger>
          <TabsTrigger value="enrollment" className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Enrollment
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Trial Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {trial.description && (
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Description</label>
                  <p className="mt-1">{trial.description}</p>
                </div>
              )}
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Therapeutic Area</label>
                  <p className="mt-1 font-medium">{trial.therapeutic_area || "Not specified"}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Protocol ID</label>
                  <p className="mt-1 font-medium">{trial.protocol_id || "Not specified"}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Start Date</label>
                  <p className="mt-1 font-medium">{trial.start_date || "Not specified"}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">End Date</label>
                  <p className="mt-1 font-medium">{trial.end_date || "Not specified"}</p>
                </div>
              </div>
              {trial.indication_codes.length > 0 && (
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Indication Codes</label>
                  <div className="flex gap-2 mt-1 flex-wrap">
                    {trial.indication_codes.map((code) => (
                      <Badge key={code} variant="outline" className="font-mono">
                        {code}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Enrollment Pipeline Status */}
          {dashboard && (
            <Card>
              <CardHeader>
                <CardTitle>Enrollment Pipeline</CardTitle>
                <CardDescription>Status breakdown of all enrollments</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 md:grid-cols-4">
                  {[
                    { label: "Candidates", key: "candidate", count: dashboard.total_candidates },
                    { label: "Screened", key: "screened", count: dashboard.total_screened },
                    { label: "Eligible", key: "eligible", count: dashboard.total_eligible },
                    { label: "Enrolled", key: "enrolled", count: dashboard.total_enrolled },
                    { label: "Active", key: "active", count: dashboard.total_active },
                    { label: "Completed", key: "completed", count: dashboard.total_completed },
                    { label: "Withdrawn", key: "withdrawn", count: dashboard.total_withdrawn },
                    { label: "Screen Failed", key: "screen_failed", count: dashboard.total_screen_failed },
                  ].map(({ label, key, count }) => (
                    <div
                      key={key}
                      className="flex items-center justify-between rounded-lg border p-3"
                    >
                      <span className="text-sm">{label}</span>
                      <Badge className={enrollmentStatusColors[key] || ""}>
                        {count}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Eligibility Criteria Tab */}
        <TabsContent value="eligibility" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-500" />
                Inclusion Criteria
              </CardTitle>
              <CardDescription>
                Patients must meet all inclusion criteria
              </CardDescription>
            </CardHeader>
            <CardContent>
              {(trial.inclusion_criteria?.criteria ?? []).length === 0 ? (
                <p className="text-muted-foreground">No inclusion criteria defined</p>
              ) : (
                <div className="space-y-3">
                  {(trial.inclusion_criteria?.criteria ?? []).map((criterion, idx) => (
                    <div
                      key={idx}
                      className="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 p-3 dark:border-green-900 dark:bg-green-950"
                    >
                      <CheckCircle2 className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
                      <div className="text-sm">
                        <span className="font-medium capitalize">
                          {((criterion as Record<string, unknown>).criterion_type as string || (criterion as Record<string, unknown>).type as string || "criteria")}:
                        </span>{" "}
                        {formatCriterion(criterion as Record<string, unknown>)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <XCircle className="h-5 w-5 text-red-500" />
                Exclusion Criteria
              </CardTitle>
              <CardDescription>
                Patients are excluded if they meet any exclusion criterion
              </CardDescription>
            </CardHeader>
            <CardContent>
              {(trial.exclusion_criteria?.criteria ?? []).length === 0 ? (
                <p className="text-muted-foreground">No exclusion criteria defined</p>
              ) : (
                <div className="space-y-3">
                  {(trial.exclusion_criteria?.criteria ?? []).map((criterion, idx) => (
                    <div
                      key={idx}
                      className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950"
                    >
                      <XCircle className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
                      <div className="text-sm">
                        <span className="font-medium capitalize">
                          {((criterion as Record<string, unknown>).criterion_type as string || (criterion as Record<string, unknown>).type as string || "criteria")}:
                        </span>{" "}
                        {formatCriterion(criterion as Record<string, unknown>)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Candidates Tab */}
        <TabsContent value="candidates" className="space-y-4">
          {screening.data ? (
            <>
              <div className="grid gap-4 md:grid-cols-3">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Total Screened</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{screening.data.total_patients_screened}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Eligible</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-green-600">
                      {screening.data.eligible_count}
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Ineligible</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-red-600">
                      {screening.data.ineligible_count}
                    </div>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Eligible Candidates</CardTitle>
                  <CardDescription>
                    {screening.data.candidates.length} patients match eligibility criteria
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="rounded-lg border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Patient ID</TableHead>
                          <TableHead>Match Score</TableHead>
                          <TableHead>Criteria Met</TableHead>
                          <TableHead>Exclusions</TableHead>
                          <TableHead>Missing Data</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {screening.data.candidates.map((candidate) => (
                          <TableRow key={candidate.patient_id}>
                            <TableCell className="font-mono">
                              {candidate.patient_id}
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <div className="h-2 w-16 rounded-full bg-gray-200 dark:bg-gray-700">
                                  <div
                                    className="h-full rounded-full bg-green-500"
                                    style={{
                                      width: `${(candidate.match_score * 100).toFixed(0)}%`,
                                    }}
                                  />
                                </div>
                                <span className="text-sm font-medium">
                                  {(candidate.match_score * 100).toFixed(0)}%
                                </span>
                              </div>
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-1">
                                <CheckCircle2 className="h-4 w-4 text-green-500" />
                                <span className="text-sm">{candidate.inclusion_met.length}</span>
                              </div>
                            </TableCell>
                            <TableCell>
                              {candidate.exclusion_triggered.length > 0 ? (
                                <div className="flex items-center gap-1">
                                  <XCircle className="h-4 w-4 text-red-500" />
                                  <span className="text-sm">{candidate.exclusion_triggered.length}</span>
                                </div>
                              ) : (
                                <span className="text-sm text-muted-foreground">None</span>
                              )}
                            </TableCell>
                            <TableCell>
                              {candidate.missing_data.length > 0 ? (
                                <div className="flex items-center gap-1">
                                  <AlertCircle className="h-4 w-4 text-yellow-500" />
                                  <span className="text-sm">{candidate.missing_data.length}</span>
                                </div>
                              ) : (
                                <span className="text-sm text-muted-foreground">None</span>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>

              {/* Exclusion Breakdown */}
              {screening.data.exclusion_breakdown &&
                Object.keys(screening.data.exclusion_breakdown).length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Exclusion Breakdown</CardTitle>
                    <CardDescription>
                      Reasons patients were excluded
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {Object.entries(screening.data.exclusion_breakdown).map(
                        ([reason, count]) => (
                          <div
                            key={reason}
                            className="flex items-center justify-between rounded-lg border p-3"
                          >
                            <span className="text-sm">{reason}</span>
                            <Badge variant="outline">{count}</Badge>
                          </div>
                        )
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <Card>
              <CardContent className="py-12 text-center">
                <Users className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="text-lg font-medium mb-2">No screening results yet</h3>
                <p className="text-muted-foreground mb-4">
                  Click &quot;Screen Patients&quot; to find eligible candidates
                </p>
                <Button
                  onClick={() => screening.mutate()}
                  disabled={screening.isPending}
                >
                  {screening.isPending ? (
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="mr-2 h-4 w-4" />
                  )}
                  Screen Patients
                </Button>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Enrollment Tab */}
        <TabsContent value="enrollment" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Enrollments</CardTitle>
              <CardDescription>
                {enrollments?.total ?? 0} total enrollments for this trial
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!enrollments || enrollments.enrollments.length === 0 ? (
                <div className="py-8 text-center text-muted-foreground">
                  No enrollments yet
                </div>
              ) : (
                <div className="rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Patient ID</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Match Score</TableHead>
                        <TableHead>Criteria Met</TableHead>
                        <TableHead>Criteria Failed</TableHead>
                        <TableHead>Screened</TableHead>
                        <TableHead>Notes</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {enrollments.enrollments.map((enrollment) => (
                        <TableRow key={enrollment.patient_id}>
                          <TableCell className="font-mono text-sm">
                            {enrollment.patient_id}
                          </TableCell>
                          <TableCell>
                            <Badge
                              className={
                                enrollmentStatusColors[enrollment.enrollment_status] || ""
                              }
                            >
                              {enrollment.enrollment_status.replace("_", " ")}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {enrollment.match_score != null ? (
                              <span className="font-medium">
                                {(enrollment.match_score * 100).toFixed(0)}%
                              </span>
                            ) : (
                              "-"
                            )}
                          </TableCell>
                          <TableCell>
                            <span className="text-green-600 font-medium">
                              {(enrollment.criteria_met ?? []).length}
                            </span>
                          </TableCell>
                          <TableCell>
                            <span className={(enrollment.criteria_failed ?? []).length > 0 ? "text-red-600 font-medium" : "text-muted-foreground"}>
                              {(enrollment.criteria_failed ?? []).length}
                            </span>
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {enrollment.screening_date
                              ? new Date(enrollment.screening_date).toLocaleDateString()
                              : "-"}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground max-w-[200px] truncate">
                            {enrollment.notes || "-"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function formatCriterion(criterion: Record<string, unknown>): string {
  const type = (criterion.criterion_type || criterion.type) as string;
  const name = criterion.name as string | undefined;

  switch (type) {
    case "demographic": {
      const parts: string[] = [];
      if (name) parts.push(name);
      const ageRange = criterion.age_range as Record<string, number> | undefined;
      if (ageRange) {
        if (ageRange.min_age && ageRange.max_age) {
          parts.push(`Age ${ageRange.min_age}-${ageRange.max_age}`);
        } else if (ageRange.min_age) {
          parts.push(`Age >= ${ageRange.min_age}`);
        } else if (ageRange.max_age) {
          parts.push(`Age <= ${ageRange.max_age}`);
        }
      }
      const gender = criterion.gender as string[] | undefined;
      if (gender && gender.length > 0) {
        parts.push(`Gender: ${gender.join(", ")}`);
      }
      return parts.join(" - ") || "Demographics filter";
    }
    case "condition": {
      const parts: string[] = [];
      if (name) parts.push(name);
      const codes = criterion.codes as Array<Record<string, string>> | undefined;
      if (codes && codes.length > 0) {
        parts.push(codes.map((c) => `${c.display || c.code}`).join(", "));
      }
      return parts.join(": ") || "Condition criteria";
    }
    case "drug":
    case "drug_exposure": {
      const parts: string[] = [];
      if (name) parts.push(name);
      const codes = criterion.codes as Array<Record<string, string>> | undefined;
      if (codes && codes.length > 0) {
        parts.push(codes.map((c) => `${c.display || c.code}`).join(", "));
      }
      return parts.join(": ") || "Drug exposure criteria";
    }
    case "measurement": {
      const parts: string[] = [];
      if (name) parts.push(name);
      const codes = criterion.codes as Array<Record<string, string>> | undefined;
      const valueRange = criterion.value_range as Record<string, number> | undefined;
      if (codes && codes.length > 0) {
        parts.push(codes.map((c) => c.display || c.code).join(", "));
      }
      if (valueRange) {
        if (valueRange.min_value !== undefined && valueRange.max_value !== undefined) {
          parts.push(`${valueRange.min_value}-${valueRange.max_value}`);
        } else if (valueRange.min_value !== undefined) {
          parts.push(`>= ${valueRange.min_value}`);
        } else if (valueRange.max_value !== undefined) {
          parts.push(`<= ${valueRange.max_value}`);
        }
      }
      const unit = criterion.unit as string | undefined;
      if (unit) parts.push(unit);
      const codeSystem = criterion.code_system as string | undefined;
      if (codeSystem) parts.push(`(${codeSystem})`);
      return parts.join(" ") || "Measurement criteria";
    }
    case "procedure": {
      const parts: string[] = [];
      if (name) parts.push(name);
      const codes = criterion.codes as Array<Record<string, string>> | undefined;
      if (codes && codes.length > 0) {
        parts.push(codes.map((c) => `${c.display || c.code}`).join(", "));
      }
      return parts.join(": ") || "Procedure criteria";
    }
    default:
      return name || JSON.stringify(criterion);
  }
}
