"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";
import {
  ArrowLeft,
  Edit,
  Copy,
  GitCompare,
  Download,
  Users,
  Database,
  Clock,
  Tag,
  CheckCircle,
  Archive,
  Activity,
  ChevronRight,
  FileJson,
  Code,
  History,
  BarChart3,
  Pill,
  Stethoscope,
  User,
  Calendar,
} from "lucide-react";

// Types
interface CodeEntry {
  code: string;
  display: string | null;
  system: string | null;
}

interface AgeRange {
  min_age: number | null;
  max_age: number | null;
}

interface DateRange {
  start_date: string | null;
  end_date: string | null;
}

interface NumericRange {
  min_value: number | null;
  max_value: number | null;
}

interface BaseCriterion {
  id: string;
  criterion_type: string;
  name: string | null;
  description: string | null;
  negated: boolean;
}

interface DemographicCriterion extends BaseCriterion {
  criterion_type: "demographic";
  age_range: AgeRange | null;
  genders: string[] | null;
  races: string[] | null;
  ethnicities: string[] | null;
}

interface ConditionCriterion extends BaseCriterion {
  criterion_type: "condition";
  codes: CodeEntry[];
  code_system: string;
  date_range: DateRange | null;
}

interface DrugCriterion extends BaseCriterion {
  criterion_type: "drug";
  codes: CodeEntry[];
  code_system: string;
  date_range: DateRange | null;
}

interface ProcedureCriterion extends BaseCriterion {
  criterion_type: "procedure";
  codes: CodeEntry[];
  code_system: string;
  date_range: DateRange | null;
}

interface MeasurementCriterion extends BaseCriterion {
  criterion_type: "measurement";
  codes: CodeEntry[];
  code_system: string;
  value_range: NumericRange | null;
  date_range: DateRange | null;
}

interface VisitCriterion extends BaseCriterion {
  criterion_type: "visit";
  visit_types: string[];
  date_range: DateRange | null;
}

type AnyCriterion =
  | DemographicCriterion
  | ConditionCriterion
  | DrugCriterion
  | ProcedureCriterion
  | MeasurementCriterion
  | VisitCriterion;

interface CohortDefinition {
  id: string;
  name: string;
  description: string | null;
  version: string;
  status: "draft" | "active" | "archived";
  criteria: AnyCriterion[];
  root_operator: "AND" | "OR" | "NOT";
  created_at: string;
  updated_at: string;
  created_by: string | null;
  tags: string[];
}

interface CohortCountResult {
  cohort_id: string;
  count: number;
  execution_time_ms: number;
  sql_query: string;
  cached: boolean;
}

interface DemographicBreakdown {
  total_patients: number;
  by_gender: Record<string, number>;
  by_race: Record<string, number>;
  by_ethnicity: Record<string, number>;
  by_age_group: Record<string, number>;
  mean_age: number | null;
  median_age: number | null;
}

interface CohortVersion {
  version: string;
  created_at: string;
  created_by: string | null;
  changes: string | null;
}

interface VersionListResponse {
  versions: CohortVersion[];
  cohort_id: string;
}

// API functions
const API_BASE = "/api/cohorts";

async function fetchCohort(id: string): Promise<CohortDefinition> {
  const response = await fetch(`${API_BASE}/${id}`);
  if (!response.ok) throw new Error("Failed to fetch cohort");
  return response.json();
}

async function fetchCohortCount(id: string): Promise<CohortCountResult> {
  const response = await fetch(`${API_BASE}/${id}/count`, { method: "POST" });
  if (!response.ok) throw new Error("Failed to fetch count");
  return response.json();
}

async function fetchDemographics(id: string): Promise<DemographicBreakdown> {
  const response = await fetch(`${API_BASE}/${id}/demographics`);
  if (!response.ok) throw new Error("Failed to fetch demographics");
  return response.json();
}

async function fetchVersions(id: string): Promise<VersionListResponse> {
  const response = await fetch(`${API_BASE}/${id}/versions`);
  if (!response.ok) throw new Error("Failed to fetch versions");
  return response.json();
}

// Status config
const STATUS_CONFIG: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  draft: {
    color: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
    icon: <Clock className="h-3 w-3" />,
    label: "Draft",
  },
  active: {
    color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    icon: <CheckCircle className="h-3 w-3" />,
    label: "Active",
  },
  archived: {
    color: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
    icon: <Archive className="h-3 w-3" />,
    label: "Archived",
  },
};

// Criterion type config
const CRITERION_CONFIG: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  demographic: {
    icon: <User className="h-4 w-4" />,
    label: "Demographics",
    color: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  },
  condition: {
    icon: <Stethoscope className="h-4 w-4" />,
    label: "Condition",
    color: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  },
  drug: {
    icon: <Pill className="h-4 w-4" />,
    label: "Drug",
    color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  },
  procedure: {
    icon: <Activity className="h-4 w-4" />,
    label: "Procedure",
    color: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  },
  measurement: {
    icon: <BarChart3 className="h-4 w-4" />,
    label: "Measurement",
    color: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
  },
  visit: {
    icon: <Calendar className="h-4 w-4" />,
    label: "Visit",
    color: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200",
  },
};

function CriterionCard({ criterion, index }: { criterion: AnyCriterion; index: number }) {
  const config = CRITERION_CONFIG[criterion.criterion_type];

  const renderDetails = () => {
    switch (criterion.criterion_type) {
      case "demographic": {
        const demo = criterion as DemographicCriterion;
        return (
          <div className="space-y-1 text-sm">
            {demo.age_range && (demo.age_range.min_age || demo.age_range.max_age) && (
              <p>
                Age: {demo.age_range.min_age || "*"} - {demo.age_range.max_age || "*"}
              </p>
            )}
            {demo.genders && demo.genders.length > 0 && (
              <p>Gender: {demo.genders.join(", ")}</p>
            )}
            {demo.races && demo.races.length > 0 && (
              <p>Race: {demo.races.join(", ")}</p>
            )}
          </div>
        );
      }
      case "condition":
      case "drug":
      case "procedure": {
        const coded = criterion as ConditionCriterion | DrugCriterion | ProcedureCriterion;
        return (
          <div className="space-y-1 text-sm">
            <p className="font-medium">{coded.code_system}</p>
            <div className="flex flex-wrap gap-1">
              {coded.codes.slice(0, 5).map((code, i) => (
                <Badge key={i} variant="outline" className="text-xs">
                  {code.code}
                  {code.display && `: ${code.display.substring(0, 30)}...`}
                </Badge>
              ))}
              {coded.codes.length > 5 && (
                <Badge variant="outline" className="text-xs">
                  +{coded.codes.length - 5} more
                </Badge>
              )}
            </div>
            {coded.date_range && (coded.date_range.start_date || coded.date_range.end_date) && (
              <p className="text-muted-foreground">
                Date: {coded.date_range.start_date || "*"} to {coded.date_range.end_date || "*"}
              </p>
            )}
          </div>
        );
      }
      case "measurement": {
        const meas = criterion as MeasurementCriterion;
        return (
          <div className="space-y-1 text-sm">
            <p className="font-medium">{meas.code_system}</p>
            <div className="flex flex-wrap gap-1">
              {meas.codes.slice(0, 3).map((code, i) => (
                <Badge key={i} variant="outline" className="text-xs">
                  {code.code}
                </Badge>
              ))}
            </div>
            {meas.value_range && (
              <p>
                Value: {meas.value_range.min_value ?? "*"} - {meas.value_range.max_value ?? "*"}
              </p>
            )}
          </div>
        );
      }
      case "visit": {
        const visit = criterion as VisitCriterion;
        return (
          <div className="space-y-1 text-sm">
            {visit.visit_types.length > 0 && (
              <p>Types: {visit.visit_types.join(", ")}</p>
            )}
            {visit.date_range && (visit.date_range.start_date || visit.date_range.end_date) && (
              <p className="text-muted-foreground">
                Date: {visit.date_range.start_date || "*"} to {visit.date_range.end_date || "*"}
              </p>
            )}
          </div>
        );
      }
      default:
        return null;
    }
  };

  return (
    <Card className={criterion.negated ? "border-red-300 dark:border-red-800" : ""}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Badge className={config.color}>
              {config.icon}
              <span className="ml-1">{config.label}</span>
            </Badge>
            <span className="text-sm text-muted-foreground">#{index + 1}</span>
          </div>
          {criterion.negated && (
            <Badge variant="destructive">NOT</Badge>
          )}
        </div>
        {criterion.name && (
          <CardTitle className="text-base">{criterion.name}</CardTitle>
        )}
      </CardHeader>
      <CardContent>{renderDetails()}</CardContent>
    </Card>
  );
}

export default function CohortDetailPage() {
  const params = useParams();
  const cohortId = params.id as string;
  const [activeTab, setActiveTab] = useState("definition");

  // Fetch cohort data
  const { data: cohort, isLoading: cohortLoading, error: cohortError } = useQuery({
    queryKey: ["cohort", cohortId],
    queryFn: () => fetchCohort(cohortId),
  });

  // Fetch count
  const { data: countResult } = useQuery({
    queryKey: ["cohort-count", cohortId],
    queryFn: () => fetchCohortCount(cohortId),
    enabled: !!cohort,
  });

  // Fetch demographics (only when tab is active)
  const { data: demographics, isLoading: demographicsLoading } = useQuery({
    queryKey: ["cohort-demographics", cohortId],
    queryFn: () => fetchDemographics(cohortId),
    enabled: activeTab === "demographics",
  });

  // Fetch versions (only when tab is active)
  const { data: versionsData, isLoading: versionsLoading } = useQuery({
    queryKey: ["cohort-versions", cohortId],
    queryFn: () => fetchVersions(cohortId),
    enabled: activeTab === "history",
  });

  // Calculate max demographic value for progress bars
  const maxGender = useMemo(() => {
    if (!demographics) return 0;
    return Math.max(...Object.values(demographics.by_gender));
  }, [demographics]);

  const maxRace = useMemo(() => {
    if (!demographics) return 0;
    return Math.max(...Object.values(demographics.by_race));
  }, [demographics]);

  const maxAge = useMemo(() => {
    if (!demographics) return 0;
    return Math.max(...Object.values(demographics.by_age_group));
  }, [demographics]);

  if (cohortLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
      </div>
    );
  }

  if (cohortError || !cohort) {
    return (
      <div className="p-6">
        <div className="rounded-lg bg-red-50 p-4 text-red-800 dark:bg-red-900/20 dark:text-red-200">
          Failed to load cohort. It may not exist or the backend is unavailable.
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
          <Link href="/cohorts" className="hover:text-foreground">
            Cohorts
          </Link>
          <ChevronRight className="h-4 w-4" />
          <span>{cohort.name}</span>
        </div>

        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight">{cohort.name}</h1>
              <Badge className={STATUS_CONFIG[cohort.status]?.color}>
                {STATUS_CONFIG[cohort.status]?.icon}
                <span className="ml-1">{STATUS_CONFIG[cohort.status]?.label}</span>
              </Badge>
              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                v{cohort.version}
              </code>
            </div>
            {cohort.description && (
              <p className="text-muted-foreground mt-1">{cohort.description}</p>
            )}
            {cohort.tags.length > 0 && (
              <div className="flex gap-1 mt-2">
                {cohort.tags.map((tag) => (
                  <Badge key={tag} variant="outline">
                    <Tag className="h-3 w-3 mr-1" />
                    {tag}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          <div className="flex gap-2">
            <Link href="/cohorts">
              <Button variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
            </Link>
            <Link href={`/cohorts/builder?edit=${cohort.id}`}>
              <Button variant="outline">
                <Edit className="mr-2 h-4 w-4" />
                Edit
              </Button>
            </Link>
            <Link href={`/cohorts/compare?a=${cohort.id}`}>
              <Button variant="outline">
                <GitCompare className="mr-2 h-4 w-4" />
                Compare
              </Button>
            </Link>
            <Button variant="outline" onClick={() => toast.success("Cohort cloned!")}>
              <Copy className="mr-2 h-4 w-4" />
              Clone
            </Button>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4 mb-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Patient Count</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {countResult?.count.toLocaleString() || "..."}
            </div>
            {countResult && (
              <p className="text-xs text-muted-foreground mt-1">
                Query time: {countResult.execution_time_ms.toFixed(1)}ms
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Criteria Count</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{cohort.criteria.length}</div>
            <p className="text-xs text-muted-foreground mt-1">
              Combined with {cohort.root_operator}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Created</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">
              {new Date(cohort.created_at).toLocaleDateString()}
            </div>
            {cohort.created_by && (
              <p className="text-xs text-muted-foreground mt-1">
                by {cohort.created_by}
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Last Updated</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">
              {new Date(cohort.updated_at).toLocaleDateString()}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {new Date(cohort.updated_at).toLocaleTimeString()}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="definition" className="flex items-center gap-2">
            <Database className="h-4 w-4" />
            Definition
          </TabsTrigger>
          <TabsTrigger value="demographics" className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Demographics
          </TabsTrigger>
          <TabsTrigger value="sql" className="flex items-center gap-2">
            <Code className="h-4 w-4" />
            SQL Query
          </TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-2">
            <History className="h-4 w-4" />
            Version History
          </TabsTrigger>
        </TabsList>

        {/* Definition Tab */}
        <TabsContent value="definition">
          <Card>
            <CardHeader>
              <CardTitle>Cohort Criteria</CardTitle>
              <CardDescription>
                All criteria combined with <Badge variant="outline">{cohort.root_operator}</Badge>
              </CardDescription>
            </CardHeader>
            <CardContent>
              {cohort.criteria.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No criteria defined. This cohort will match all patients.
                </div>
              ) : (
                <div className="space-y-4">
                  {cohort.criteria.map((criterion, index) => (
                    <div key={criterion.id} className="flex items-start gap-4">
                      {index > 0 && (
                        <div className="flex-shrink-0 w-12 text-center">
                          <Badge variant="secondary">{cohort.root_operator}</Badge>
                        </div>
                      )}
                      <div className="flex-grow">
                        <CriterionCard criterion={criterion} index={index} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Demographics Tab */}
        <TabsContent value="demographics">
          {demographicsLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
            </div>
          ) : demographics ? (
            <div className="grid gap-6 md:grid-cols-2">
              {/* Gender Distribution */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Gender Distribution</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {Object.entries(demographics.by_gender).map(([gender, count]) => (
                      <div key={gender}>
                        <div className="flex justify-between text-sm mb-1">
                          <span>{gender}</span>
                          <span className="font-medium">{count.toLocaleString()}</span>
                        </div>
                        <Progress value={(count / maxGender) * 100} />
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Race Distribution */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Race Distribution</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {Object.entries(demographics.by_race).map(([race, count]) => (
                      <div key={race}>
                        <div className="flex justify-between text-sm mb-1">
                          <span>{race}</span>
                          <span className="font-medium">{count.toLocaleString()}</span>
                        </div>
                        <Progress value={(count / maxRace) * 100} />
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Age Distribution */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Age Distribution</CardTitle>
                  <CardDescription>
                    Mean: {demographics.mean_age?.toFixed(1)} | Median: {demographics.median_age?.toFixed(1)}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {Object.entries(demographics.by_age_group).map(([group, count]) => (
                      <div key={group}>
                        <div className="flex justify-between text-sm mb-1">
                          <span>{group}</span>
                          <span className="font-medium">{count.toLocaleString()}</span>
                        </div>
                        <Progress value={(count / maxAge) * 100} />
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Summary Stats */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Summary Statistics</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex justify-between items-center py-2 border-b">
                      <span className="text-muted-foreground">Total Patients</span>
                      <span className="font-bold text-xl">
                        {demographics.total_patients.toLocaleString()}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-2 border-b">
                      <span className="text-muted-foreground">Mean Age</span>
                      <span className="font-medium">
                        {demographics.mean_age?.toFixed(1) ?? "N/A"} years
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-2">
                      <span className="text-muted-foreground">Median Age</span>
                      <span className="font-medium">
                        {demographics.median_age?.toFixed(1) ?? "N/A"} years
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              Unable to load demographics data.
            </div>
          )}
        </TabsContent>

        {/* SQL Tab */}
        <TabsContent value="sql">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Generated SQL Query</CardTitle>
                  <CardDescription>
                    OMOP CDM compatible SQL for counting patients
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  onClick={() => {
                    navigator.clipboard.writeText(countResult?.sql_query || "");
                    toast.success("SQL copied to clipboard");
                  }}
                >
                  <Download className="mr-2 h-4 w-4" />
                  Copy SQL
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <pre className="bg-muted p-4 rounded-lg overflow-x-auto text-sm">
                <code>{countResult?.sql_query || "Loading..."}</code>
              </pre>
            </CardContent>
          </Card>
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history">
          <Card>
            <CardHeader>
              <CardTitle>Version History</CardTitle>
              <CardDescription>
                Track changes to this cohort definition over time
              </CardDescription>
            </CardHeader>
            <CardContent>
              {versionsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
                </div>
              ) : versionsData && versionsData.versions.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Version</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Author</TableHead>
                      <TableHead>Changes</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {versionsData.versions.map((version) => (
                      <TableRow key={version.version}>
                        <TableCell>
                          <code className="text-sm bg-muted px-1.5 py-0.5 rounded">
                            v{version.version}
                          </code>
                        </TableCell>
                        <TableCell>
                          {new Date(version.created_at).toLocaleString()}
                        </TableCell>
                        <TableCell>{version.created_by || "System"}</TableCell>
                        <TableCell>{version.changes || "-"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No version history available.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Export Actions */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-lg">Export Options</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4">
            <Button
              variant="outline"
              onClick={() => window.open(`${API_BASE}/${cohort.id}/export?format=json`, "_blank")}
            >
              <FileJson className="mr-2 h-4 w-4" />
              Export as JSON
            </Button>
            <Button
              variant="outline"
              onClick={() => window.open(`${API_BASE}/${cohort.id}/export?format=sql`, "_blank")}
            >
              <Code className="mr-2 h-4 w-4" />
              Export as SQL
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
