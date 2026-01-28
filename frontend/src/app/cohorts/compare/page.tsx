"use client";

import { useState, useMemo, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import {
  ArrowLeft,
  ArrowRight,
  GitCompare,
  Users,
  Loader2,
  BarChart3,
  Pill,
  Stethoscope,
  RefreshCw,
  ChevronRight,
} from "lucide-react";

// Types
interface CohortSummary {
  id: string;
  name: string;
  description: string | null;
  version: string;
  status: string;
  criteria_count: number;
  patient_count: number | null;
}

interface CohortListResponse {
  cohorts: CohortSummary[];
  total: number;
}

interface ConditionPrevalence {
  condition_code: string;
  condition_name: string | null;
  patient_count: number;
  prevalence_percent: number;
}

interface DrugUtilization {
  drug_code: string;
  drug_name: string | null;
  patient_count: number;
  utilization_percent: number;
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

interface CohortComparisonResult {
  cohort_a_id: string;
  cohort_b_id: string;
  cohort_a_count: number;
  cohort_b_count: number;
  overlap_count: number;
  cohort_a_only_count: number;
  cohort_b_only_count: number;
  demographics_a: DemographicBreakdown | null;
  demographics_b: DemographicBreakdown | null;
  top_conditions_a: ConditionPrevalence[];
  top_conditions_b: ConditionPrevalence[];
  top_drugs_a: DrugUtilization[];
  top_drugs_b: DrugUtilization[];
}

// API functions
const API_BASE = "/api/cohorts";

async function fetchCohorts(): Promise<CohortListResponse> {
  const response = await fetch(`${API_BASE}?limit=100`);
  if (!response.ok) throw new Error("Failed to fetch cohorts");
  return response.json();
}

async function compareCohorts(
  cohortAId: string,
  cohortBId: string
): Promise<CohortComparisonResult> {
  const response = await fetch(`${API_BASE}/${cohortAId}/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cohort_b_id: cohortBId }),
  });
  if (!response.ok) throw new Error("Failed to compare cohorts");
  return response.json();
}

// Bar chart component for comparisons
function ComparisonBar({
  label,
  valueA,
  valueB,
  maxValue,
  colorA = "bg-blue-500",
  colorB = "bg-green-500",
}: {
  label: string;
  valueA: number;
  valueB: number;
  maxValue: number;
  colorA?: string;
  colorB?: string;
}) {
  const percentA = maxValue > 0 ? (valueA / maxValue) * 100 : 0;
  const percentB = maxValue > 0 ? (valueB / maxValue) * 100 : 0;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">
          {valueA.toLocaleString()} vs {valueB.toLocaleString()}
        </span>
      </div>
      <div className="flex gap-1 h-4">
        <div className="flex-1 bg-muted rounded-l overflow-hidden">
          <div
            className={`h-full ${colorA} transition-all`}
            style={{ width: `${percentA}%`, marginLeft: "auto" }}
          />
        </div>
        <div className="flex-1 bg-muted rounded-r overflow-hidden">
          <div
            className={`h-full ${colorB} transition-all`}
            style={{ width: `${percentB}%` }}
          />
        </div>
      </div>
    </div>
  );
}

// Venn diagram component
function VennDiagram({
  countA,
  countB,
  overlap,
  labelA,
  labelB,
}: {
  countA: number;
  countB: number;
  overlap: number;
  labelA: string;
  labelB: string;
}) {
  const total = countA + countB - overlap;
  const aOnlyPercent = total > 0 ? ((countA - overlap) / total) * 100 : 0;
  const bOnlyPercent = total > 0 ? ((countB - overlap) / total) * 100 : 0;
  const overlapPercent = total > 0 ? (overlap / total) * 100 : 0;

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-80 h-48">
        {/* Cohort A Circle */}
        <div
          className="absolute top-4 left-4 w-40 h-40 rounded-full bg-blue-100 dark:bg-blue-900/30 border-2 border-blue-500 flex items-center justify-center"
          style={{ opacity: 0.7 }}
        >
          <div className="text-center -ml-8">
            <div className="text-2xl font-bold text-blue-600">
              {(countA - overlap).toLocaleString()}
            </div>
            <div className="text-xs text-blue-600">Only A</div>
          </div>
        </div>

        {/* Cohort B Circle */}
        <div
          className="absolute top-4 right-4 w-40 h-40 rounded-full bg-green-100 dark:bg-green-900/30 border-2 border-green-500 flex items-center justify-center"
          style={{ opacity: 0.7 }}
        >
          <div className="text-center ml-8">
            <div className="text-2xl font-bold text-green-600">
              {(countB - overlap).toLocaleString()}
            </div>
            <div className="text-xs text-green-600">Only B</div>
          </div>
        </div>

        {/* Overlap */}
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
          <div className="text-center">
            <div className="text-xl font-bold text-purple-600">{overlap.toLocaleString()}</div>
            <div className="text-xs text-purple-600">Overlap</div>
          </div>
        </div>
      </div>

      <div className="flex gap-8 mt-4">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-blue-500" />
          <span className="text-sm">{labelA}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-green-500" />
          <span className="text-sm">{labelB}</span>
        </div>
      </div>
    </div>
  );
}

function CohortCompareContent() {
  const searchParams = useSearchParams();
  const initialCohortA = searchParams.get("a") || "";

  // State
  const [cohortAId, setCohortAId] = useState(initialCohortA);
  const [cohortBId, setCohortBId] = useState("");

  // Fetch cohorts for selection
  const { data: cohortsData, isLoading: cohortsLoading } = useQuery({
    queryKey: ["cohorts-list"],
    queryFn: fetchCohorts,
  });

  const cohorts = useMemo(() => cohortsData?.cohorts || [], [cohortsData]);

  // Compare mutation
  const compareMutation = useMutation({
    mutationFn: () => compareCohorts(cohortAId, cohortBId),
    onError: () => {
      toast.error("Failed to compare cohorts");
    },
  });

  // Selected cohort details
  const cohortA = useMemo(
    () => cohorts.find((c) => c.id === cohortAId),
    [cohorts, cohortAId]
  );
  const cohortB = useMemo(
    () => cohorts.find((c) => c.id === cohortBId),
    [cohorts, cohortBId]
  );

  const comparison = compareMutation.data;

  // Calculate max values for comparisons
  const maxGenderValue = useMemo(() => {
    if (!comparison?.demographics_a || !comparison?.demographics_b) return 0;
    return Math.max(
      ...Object.values(comparison.demographics_a.by_gender),
      ...Object.values(comparison.demographics_b.by_gender)
    );
  }, [comparison]);

  const maxAgeValue = useMemo(() => {
    if (!comparison?.demographics_a || !comparison?.demographics_b) return 0;
    return Math.max(
      ...Object.values(comparison.demographics_a.by_age_group),
      ...Object.values(comparison.demographics_b.by_age_group)
    );
  }, [comparison]);

  const handleCompare = () => {
    if (!cohortAId || !cohortBId) {
      toast.error("Please select two cohorts to compare");
      return;
    }
    if (cohortAId === cohortBId) {
      toast.error("Please select two different cohorts");
      return;
    }
    compareMutation.mutate();
  };

  const handleSwapCohorts = () => {
    const temp = cohortAId;
    setCohortAId(cohortBId);
    setCohortBId(temp);
    compareMutation.reset();
  };

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
          <Link href="/cohorts" className="hover:text-foreground">
            Cohorts
          </Link>
          <ChevronRight className="h-4 w-4" />
          <span>Compare</span>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <GitCompare className="h-6 w-6" />
              Compare Cohorts
            </h1>
            <p className="text-muted-foreground">
              Compare demographics, conditions, and medications between two cohorts
            </p>
          </div>
          <Link href="/cohorts">
            <Button variant="outline">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Cohorts
            </Button>
          </Link>
        </div>
      </div>

      {/* Cohort Selection */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Select Cohorts to Compare</CardTitle>
          <CardDescription>
            Choose two cohorts to see a detailed comparison
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-4">
            {/* Cohort A */}
            <div className="flex-1">
              <label className="text-sm font-medium text-blue-600">Cohort A</label>
              <Select value={cohortAId} onValueChange={setCohortAId}>
                <SelectTrigger className="mt-1 border-blue-200">
                  <SelectValue placeholder="Select first cohort" />
                </SelectTrigger>
                <SelectContent>
                  {cohorts.map((cohort) => (
                    <SelectItem key={cohort.id} value={cohort.id}>
                      <div className="flex items-center justify-between w-full">
                        <span>{cohort.name}</span>
                        <Badge variant="outline" className="ml-2">
                          {cohort.patient_count?.toLocaleString() || "?"} patients
                        </Badge>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {cohortA && (
                <p className="text-xs text-muted-foreground mt-1">
                  {cohortA.description || `${cohortA.criteria_count} criteria`}
                </p>
              )}
            </div>

            {/* Swap Button */}
            <Button
              variant="ghost"
              size="icon"
              onClick={handleSwapCohorts}
              disabled={!cohortAId || !cohortBId}
            >
              <ArrowRight className="h-4 w-4" />
            </Button>

            {/* Cohort B */}
            <div className="flex-1">
              <label className="text-sm font-medium text-green-600">Cohort B</label>
              <Select value={cohortBId} onValueChange={setCohortBId}>
                <SelectTrigger className="mt-1 border-green-200">
                  <SelectValue placeholder="Select second cohort" />
                </SelectTrigger>
                <SelectContent>
                  {cohorts.map((cohort) => (
                    <SelectItem key={cohort.id} value={cohort.id}>
                      <div className="flex items-center justify-between w-full">
                        <span>{cohort.name}</span>
                        <Badge variant="outline" className="ml-2">
                          {cohort.patient_count?.toLocaleString() || "?"} patients
                        </Badge>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {cohortB && (
                <p className="text-xs text-muted-foreground mt-1">
                  {cohortB.description || `${cohortB.criteria_count} criteria`}
                </p>
              )}
            </div>

            {/* Compare Button */}
            <Button
              onClick={handleCompare}
              disabled={!cohortAId || !cohortBId || compareMutation.isPending}
            >
              {compareMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <GitCompare className="mr-2 h-4 w-4" />
              )}
              Compare
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Comparison Results */}
      {comparison && (
        <div className="space-y-6">
          {/* Overview Cards */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card className="border-blue-200">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-blue-600">
                  Cohort A Total
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {comparison.cohort_a_count.toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground">{cohortA?.name}</p>
              </CardContent>
            </Card>

            <Card className="border-green-200">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-green-600">
                  Cohort B Total
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {comparison.cohort_b_count.toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground">{cohortB?.name}</p>
              </CardContent>
            </Card>

            <Card className="border-purple-200">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-purple-600">
                  Overlap
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {comparison.overlap_count.toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground">
                  {(
                    (comparison.overlap_count /
                      Math.min(comparison.cohort_a_count, comparison.cohort_b_count)) *
                    100
                  ).toFixed(1)}
                  % of smaller cohort
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Unique Patients</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {(
                    comparison.cohort_a_count +
                    comparison.cohort_b_count -
                    comparison.overlap_count
                  ).toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground">Combined unique</p>
              </CardContent>
            </Card>
          </div>

          {/* Venn Diagram */}
          <Card>
            <CardHeader>
              <CardTitle>Population Overlap</CardTitle>
              <CardDescription>
                Visual representation of patient overlap between cohorts
              </CardDescription>
            </CardHeader>
            <CardContent className="flex justify-center py-6">
              <VennDiagram
                countA={comparison.cohort_a_count}
                countB={comparison.cohort_b_count}
                overlap={comparison.overlap_count}
                labelA={cohortA?.name || "Cohort A"}
                labelB={cohortB?.name || "Cohort B"}
              />
            </CardContent>
          </Card>

          {/* Demographics Comparison */}
          {comparison.demographics_a && comparison.demographics_b && (
            <div className="grid gap-6 md:grid-cols-2">
              {/* Gender */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Users className="h-5 w-5" />
                    Gender Distribution
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {Object.keys(comparison.demographics_a.by_gender).map((gender) => (
                    <ComparisonBar
                      key={gender}
                      label={gender}
                      valueA={comparison.demographics_a!.by_gender[gender] || 0}
                      valueB={comparison.demographics_b!.by_gender[gender] || 0}
                      maxValue={maxGenderValue}
                    />
                  ))}
                  <div className="flex justify-center gap-8 pt-2 border-t">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded bg-blue-500" />
                      <span className="text-sm">{cohortA?.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded bg-green-500" />
                      <span className="text-sm">{cohortB?.name}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Age Distribution */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <BarChart3 className="h-5 w-5" />
                    Age Distribution
                  </CardTitle>
                  <CardDescription>
                    Mean: {comparison.demographics_a.mean_age?.toFixed(1)} vs{" "}
                    {comparison.demographics_b.mean_age?.toFixed(1)} years
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {Object.keys(comparison.demographics_a.by_age_group).map((group) => (
                    <ComparisonBar
                      key={group}
                      label={group}
                      valueA={comparison.demographics_a!.by_age_group[group] || 0}
                      valueB={comparison.demographics_b!.by_age_group[group] || 0}
                      maxValue={maxAgeValue}
                    />
                  ))}
                </CardContent>
              </Card>
            </div>
          )}

          {/* Conditions Comparison */}
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Stethoscope className="h-5 w-5 text-blue-600" />
                  Top Conditions - {cohortA?.name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {comparison.top_conditions_a.map((condition) => (
                    <div key={condition.condition_code}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="font-medium">
                          {condition.condition_name || condition.condition_code}
                        </span>
                        <span className="text-muted-foreground">
                          {condition.prevalence_percent.toFixed(1)}%
                        </span>
                      </div>
                      <Progress value={condition.prevalence_percent} className="h-2" />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Stethoscope className="h-5 w-5 text-green-600" />
                  Top Conditions - {cohortB?.name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {comparison.top_conditions_b.map((condition) => (
                    <div key={condition.condition_code}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="font-medium">
                          {condition.condition_name || condition.condition_code}
                        </span>
                        <span className="text-muted-foreground">
                          {condition.prevalence_percent.toFixed(1)}%
                        </span>
                      </div>
                      <Progress value={condition.prevalence_percent} className="h-2" />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Medications Comparison */}
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Pill className="h-5 w-5 text-blue-600" />
                  Top Medications - {cohortA?.name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {comparison.top_drugs_a.map((drug) => (
                    <div key={drug.drug_code}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="font-medium">
                          {drug.drug_name || drug.drug_code}
                        </span>
                        <span className="text-muted-foreground">
                          {drug.utilization_percent.toFixed(1)}%
                        </span>
                      </div>
                      <Progress value={drug.utilization_percent} className="h-2" />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Pill className="h-5 w-5 text-green-600" />
                  Top Medications - {cohortB?.name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {comparison.top_drugs_b.map((drug) => (
                    <div key={drug.drug_code}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="font-medium">
                          {drug.drug_name || drug.drug_code}
                        </span>
                        <span className="text-muted-foreground">
                          {drug.utilization_percent.toFixed(1)}%
                        </span>
                      </div>
                      <Progress value={drug.utilization_percent} className="h-2" />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Loading State */}
      {cohortsLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      )}

      {/* Empty State */}
      {!comparison && !compareMutation.isPending && (
        <Card>
          <CardContent className="py-12 text-center">
            <GitCompare className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium">Select two cohorts to compare</h3>
            <p className="text-muted-foreground mt-1">
              Choose cohorts from the dropdowns above and click Compare
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function CohortComparePage() {
  return (
    <Suspense fallback={<div className="p-8 text-center">Loading...</div>}>
      <CohortCompareContent />
    </Suspense>
  );
}
