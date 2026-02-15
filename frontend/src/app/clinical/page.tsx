"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
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
  AlertTriangle,
  AlertCircle,
  Info,
  TrendingUp,
  Calculator,
  FileWarning,
  Activity,
  Heart,
  Pill,
  ClipboardCheck,
  RefreshCw,
  ArrowRight,
  DollarSign,
  Target,
  Stethoscope,
  Brain,
  Network,
} from "lucide-react";
import {
  DegradedBanner,
  isDegraded,
  type DegradedState,
} from "@/components/DegradedBanner";
import { RefusalCard } from "@/components/RefusalCard";

// ---------------------------------------------------------------------------
// Types matching backend schema shapes
// ---------------------------------------------------------------------------

interface DrugAlertSummary {
  alert_type: string;
  severity: string;
  drug1: string;
  drug2: string | null;
  description: string;
}

interface DiagnosisSummary {
  name: string;
  probability: number;
  urgency: string;
  icd10_code: string | null;
}

interface RiskScoreSummary {
  calculator_name: string;
  risk_level: string;
  score_value: number | null;
  interpretation: string;
}

interface LabInterpretationSummary {
  lab_name: string;
  value: number;
  unit: string;
  interpretation: string;
  reference_range: string;
}

interface ActionItem {
  priority: string;
  title: string;
  description: string;
  category: string;
  patient_id: string | null;
  estimated_impact: string | null;
}

interface ProviderDashboardResponse {
  metadata: {
    generated_at: string;
    patient_id: string | null;
    time_window: string;
  };
  clinical_summary: {
    one_liner: string;
    active_problems_count: number;
    medication_count: number;
    critical_findings: string[];
  } | null;
  differential_diagnoses: DiagnosisSummary[];
  risk_scores: RiskScoreSummary[];
  drug_alerts: DrugAlertSummary[];
  abnormal_labs: LabInterpretationSummary[];
  stats: Record<string, unknown>;
  action_items: ActionItem[];
}

interface HCCOpportunitySummary {
  hcc_code: string;
  description: string;
  gap_type: string;
  confidence: string;
  estimated_revenue: number;
  recommended_icd10: string | null;
}

interface CDIQuerySummary {
  query_id: string;
  priority: string;
  question: string;
  gap_category: string;
  estimated_impact: number;
}

interface BillerDashboardResponse {
  metadata: {
    generated_at: string;
    patient_id: string | null;
    time_window: string;
  };
  hcc_opportunities: HCCOpportunitySummary[];
  cdi_queries: CDIQuerySummary[];
  revenue_summary: Record<string, unknown>;
  action_items: ActionItem[];
}

// ---------------------------------------------------------------------------
// UI-facing types for backward-compatible rendering
// ---------------------------------------------------------------------------

interface DrugAlert {
  id: string;
  drug1: string;
  drug2: string;
  severity: "contraindicated" | "major" | "moderate" | "minor";
  description: string;
  management: string;
}

interface HCCOpportunity {
  id: string;
  hccCode: string;
  description: string;
  rafValue: number;
  estimatedRevenue: number;
  confidence: "high" | "medium" | "low";
  evidence: string;
}

interface DocumentationIssue {
  id: string;
  type: "missing" | "incomplete" | "conflicting";
  description: string;
  affectedCode: string;
  priority: "high" | "medium" | "low";
}

interface QualityGap {
  id: string;
  measureId: string;
  measureName: string;
  category: string;
  missingElement: string;
  dueDate: string;
  priority: "critical" | "high" | "medium" | "low";
}

interface ClinicalCalculator {
  id: string;
  name: string;
  shortName: string;
  description: string;
  category: string;
}

// ---------------------------------------------------------------------------
// Mappers: backend response -> UI types
// ---------------------------------------------------------------------------

function mapDrugAlerts(alerts: DrugAlertSummary[]): DrugAlert[] {
  return alerts.map((a, idx) => ({
    id: String(idx + 1),
    drug1: a.drug1,
    drug2: a.drug2 ?? "Unknown",
    severity: normalizeSeverity(a.severity),
    description: a.description,
    management: a.alert_type === "contraindication"
      ? "Contraindicated combination"
      : "Review clinical appropriateness",
  }));
}

function normalizeSeverity(
  s: string
): "contraindicated" | "major" | "moderate" | "minor" {
  const lower = s.toLowerCase();
  if (lower === "contraindicated") return "contraindicated";
  if (lower === "major") return "major";
  if (lower === "moderate") return "moderate";
  return "minor";
}

function mapHCCOpportunities(opps: HCCOpportunitySummary[]): HCCOpportunity[] {
  return opps.map((o, idx) => ({
    id: String(idx + 1),
    hccCode: o.hcc_code,
    description: o.description,
    rafValue: 0,
    estimatedRevenue: o.estimated_revenue,
    confidence: normalizeConfidence(o.confidence),
    evidence: o.gap_type + (o.recommended_icd10 ? ` (${o.recommended_icd10})` : ""),
  }));
}

function normalizeConfidence(c: string): "high" | "medium" | "low" {
  const lower = c.toLowerCase();
  if (lower === "high") return "high";
  if (lower === "medium") return "medium";
  return "low";
}

function mapCDIToDocIssues(queries: CDIQuerySummary[]): DocumentationIssue[] {
  return queries.map((q, idx) => {
    const rawPriority = normalizePriority(q.priority);
    // DocumentationIssue priority does not include "critical"; map to "high"
    const priority: DocumentationIssue["priority"] =
      rawPriority === "critical" ? "high" : rawPriority;
    return {
      id: String(idx + 1),
      type: "incomplete" as const,
      description: q.question,
      affectedCode: q.gap_category,
      priority,
    };
  });
}

function normalizePriority(
  p: string
): "critical" | "high" | "medium" | "low" {
  const lower = p.toLowerCase();
  if (lower === "critical") return "critical";
  if (lower === "high") return "high";
  if (lower === "medium") return "medium";
  return "low";
}

function mapActionItemsToQualityGaps(items: ActionItem[]): QualityGap[] {
  return items
    .filter((a) => a.category === "quality" || a.category === "hcc")
    .map((a, idx) => ({
      id: String(idx + 1),
      measureId: a.category.toUpperCase(),
      measureName: a.title,
      category: a.category,
      missingElement: a.description,
      dueDate: "",
      priority: normalizePriority(a.priority),
    }));
}

// ---------------------------------------------------------------------------
// Static calculator list (these are UI links, not backend-driven)
// ---------------------------------------------------------------------------

const clinicalCalculators: ClinicalCalculator[] = [
  {
    id: "egfr",
    name: "CKD-EPI eGFR (2021)",
    shortName: "eGFR",
    description: "Kidney function estimation",
    category: "Renal",
  },
  {
    id: "chadsvasc",
    name: "CHA2DS2-VASc Score",
    shortName: "CHADS-VASc",
    description: "AF stroke risk",
    category: "Cardiology",
  },
  {
    id: "meld",
    name: "MELD-Na Score",
    shortName: "MELD",
    description: "Liver disease severity",
    category: "Hepatology",
  },
  {
    id: "wells_dvt",
    name: "Wells Score for DVT",
    shortName: "Wells DVT",
    description: "DVT probability",
    category: "Hematology",
  },
  {
    id: "curb65",
    name: "CURB-65 Score",
    shortName: "CURB-65",
    description: "Pneumonia severity",
    category: "Pulmonology",
  },
  {
    id: "framingham",
    name: "Framingham 10-Year CVD Risk",
    shortName: "Framingham",
    description: "Cardiovascular risk",
    category: "Cardiology",
  },
];

// ---------------------------------------------------------------------------
// Severity / priority badge styling
// ---------------------------------------------------------------------------

const severityStyles: Record<string, string> = {
  contraindicated: "bg-red-600 text-white hover:bg-red-700",
  major: "bg-red-500 text-white hover:bg-red-600",
  moderate: "bg-amber-500 text-white hover:bg-amber-600",
  minor: "bg-blue-500 text-white hover:bg-blue-600",
};

const priorityStyles: Record<string, string> = {
  critical: "bg-red-600 text-white",
  high: "bg-red-500 text-white",
  medium: "bg-amber-500 text-white",
  low: "bg-blue-500 text-white",
};

const confidenceStyles: Record<string, string> = {
  high: "bg-green-500 text-white",
  medium: "bg-amber-500 text-white",
  low: "bg-gray-500 text-white",
};

const issueTypeStyles: Record<string, string> = {
  missing: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  incomplete:
    "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  conflicting:
    "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ClinicalDashboardPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [degradedState, setDegradedState] = useState<DegradedState | null>(null);

  // Data derived from API responses
  const [drugAlerts, setDrugAlerts] = useState<DrugAlert[]>([]);
  const [hccOpportunities, setHCCOpportunities] = useState<HCCOpportunity[]>(
    []
  );
  const [documentationIssues, setDocumentationIssues] = useState<
    DocumentationIssue[]
  >([]);
  const [qualityGaps, setQualityGaps] = useState<QualityGap[]>([]);
  const [providerStats, setProviderStats] = useState<Record<string, unknown>>(
    {}
  );

  // -----------------------------------------------------------------------
  // Fetch data from backend dashboard endpoints
  // -----------------------------------------------------------------------

  const refreshData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setDegradedState(null);

    try {
      const [providerRes, billerRes] = await Promise.all([
        fetch("/api/dashboard/provider"),
        fetch("/api/dashboard/biller"),
      ]);

      if (!providerRes.ok) {
        throw new Error(
          `Provider dashboard returned ${providerRes.status}: ${providerRes.statusText}`
        );
      }
      if (!billerRes.ok) {
        throw new Error(
          `Biller dashboard returned ${billerRes.status}: ${billerRes.statusText}`
        );
      }

      const provider: ProviderDashboardResponse = await providerRes.json();
      const biller: BillerDashboardResponse = await billerRes.json();

      // Check for degraded indicators in the response
      // The backend may include these fields on dashboard responses
      const providerAny = provider as unknown as Record<string, unknown>;
      const billerAny = biller as unknown as Record<string, unknown>;
      const combined: DegradedState = {
        declined: (providerAny.declined as boolean) || (billerAny.declined as boolean),
        decline_reason: (providerAny.decline_reason as string) || (billerAny.decline_reason as string) || null,
        escalation_path: (providerAny.escalation_path as string) || (billerAny.escalation_path as string) || null,
        confidence: providerAny.confidence as number | undefined,
        dependency_state: (providerAny.dependency_state as Record<string, boolean>) || (billerAny.dependency_state as Record<string, boolean>),
        provenance_complete: providerAny.provenance_complete as boolean | undefined,
        action_gate: (providerAny.action_gate as DegradedState["action_gate"]) || null,
      };
      if (isDegraded(combined)) {
        setDegradedState(combined);
      }

      // Map backend shapes to UI types
      setDrugAlerts(mapDrugAlerts(provider.drug_alerts));
      setHCCOpportunities(mapHCCOpportunities(biller.hcc_opportunities));
      setDocumentationIssues(mapCDIToDocIssues(biller.cdi_queries));
      setProviderStats(provider.stats);

      // Combine action items from both dashboards into quality gaps
      const allActions = [
        ...provider.action_items,
        ...biller.action_items,
      ];
      setQualityGaps(mapActionItemsToQualityGaps(allActions));
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load dashboard data";
      setError(message);
      console.error("Clinical dashboard fetch error:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshData();
  }, [refreshData]);

  // -----------------------------------------------------------------------
  // Computed summary stats
  // -----------------------------------------------------------------------

  const totalAlerts = drugAlerts.length;
  const criticalAlerts = drugAlerts.filter(
    (a) => a.severity === "contraindicated" || a.severity === "major"
  ).length;
  const totalRAFOpportunity = hccOpportunities.reduce(
    (sum, o) => sum + o.rafValue,
    0
  );
  const totalRevenueOpportunity = hccOpportunities.reduce(
    (sum, o) => sum + o.estimatedRevenue,
    0
  );
  const criticalGaps = qualityGaps.filter(
    (g) => g.priority === "critical"
  ).length;

  // Available calculators count from provider stats
  const availableCalculators =
    (
      providerStats as {
        summary?: { available_calculators?: number };
      }
    )?.summary?.available_calculators ?? clinicalCalculators.length;

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Clinical Decision Support
          </h1>
          <p className="text-muted-foreground">
            Real-time clinical alerts, HCC opportunities, and quality measure
            gaps
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={refreshData}
            disabled={isLoading}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          <Link href="/clinical/differential">
            <Button size="sm" variant="outline">
              <Brain className="mr-2 h-4 w-4" />
              Differential Dx
            </Button>
          </Link>
          <Link href="/clinical/safety">
            <Button size="sm" variant="outline">
              <Pill className="mr-2 h-4 w-4" />
              Drug Safety
            </Button>
          </Link>
          <Link href="/clinical/hcc">
            <Button size="sm" variant="outline">
              <TrendingUp className="mr-2 h-4 w-4" />
              HCC Analysis
            </Button>
          </Link>
          <Link href="/clinical/icd10">
            <Button size="sm" variant="outline">
              <Activity className="mr-2 h-4 w-4" />
              ICD-10
            </Button>
          </Link>
          <Link href="/clinical/cpt">
            <Button size="sm" variant="outline">
              <Stethoscope className="mr-2 h-4 w-4" />
              CPT
            </Button>
          </Link>
          <Link href="/clinical/crossref">
            <Button size="sm" variant="outline">
              <Network className="mr-2 h-4 w-4" />
              Cross-Ref
            </Button>
          </Link>
          <Link href="/clinical/med-reconciliation">
            <Button size="sm" variant="outline">
              <Pill className="mr-2 h-4 w-4" />
              Med Recon
            </Button>
          </Link>
          <Link href="/clinical/cdi-queries">
            <Button size="sm" variant="outline">
              <ClipboardCheck className="mr-2 h-4 w-4" />
              CDI Queries
            </Button>
          </Link>
          <Link href="/clinical/value-sets">
            <Button size="sm" variant="outline">
              <Activity className="mr-2 h-4 w-4" />
              Value Sets
            </Button>
          </Link>
          <Link href="/clinical/tools">
            <Button size="sm">
              <Calculator className="mr-2 h-4 w-4" />
              Calculators
            </Button>
          </Link>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <Card className="border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-red-800 dark:text-red-200">
                Failed to load dashboard data
              </p>
              <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={refreshData}
              disabled={isLoading}
            >
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* P1-004: Refusal card for declined, degraded banner for other issues */}
      {degradedState?.declined ? (
        <RefusalCard state={degradedState} />
      ) : degradedState ? (
        <DegradedBanner state={degradedState} />
      ) : null}

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Drug Alerts</CardTitle>
            <Pill className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? "..." : totalAlerts}
            </div>
            <p className="text-xs text-muted-foreground">
              {isLoading ? (
                "Loading..."
              ) : (
                <>
                  <span className="text-red-600 dark:text-red-400 font-medium">
                    {criticalAlerts} critical
                  </span>{" "}
                  interactions detected
                </>
              )}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              RAF Opportunity
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? "..." : `+${totalRAFOpportunity.toFixed(3)}`}
            </div>
            <p className="text-xs text-muted-foreground">
              {isLoading
                ? "Loading..."
                : `${hccOpportunities.length} HCC gaps identified`}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Revenue Opportunity
            </CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {isLoading
                ? "..."
                : `$${totalRevenueOpportunity.toLocaleString()}`}
            </div>
            <p className="text-xs text-muted-foreground">
              {isLoading ? "Loading..." : "Potential annual revenue"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Quality Gaps</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? "..." : qualityGaps.length}
            </div>
            <p className="text-xs text-muted-foreground">
              {isLoading ? (
                "Loading..."
              ) : (
                <>
                  <span className="text-red-600 dark:text-red-400 font-medium">
                    {criticalGaps} critical
                  </span>{" "}
                  gaps to close
                </>
              )}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Drug Interaction Alerts Panel */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-amber-500" />
                  Drug Interaction Alerts
                </CardTitle>
                <CardDescription>
                  Active medication interactions requiring attention
                </CardDescription>
              </div>
              <Link href="/clinical/interactions">
                <Button variant="ghost" size="sm">
                  View All
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">
                  Loading alerts...
                </span>
              </div>
            ) : drugAlerts.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">
                No drug interaction alerts found.
              </p>
            ) : (
              <div className="space-y-3">
                {drugAlerts.map((alert) => (
                  <div
                    key={alert.id}
                    className="flex items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/50"
                  >
                    {alert.severity === "contraindicated" ? (
                      <AlertCircle className="h-5 w-5 text-red-600 mt-0.5 shrink-0" />
                    ) : alert.severity === "major" ? (
                      <AlertTriangle className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />
                    ) : (
                      <Info className="h-5 w-5 text-amber-500 mt-0.5 shrink-0" />
                    )}
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium">
                          {alert.drug1} + {alert.drug2}
                        </span>
                        <Badge className={severityStyles[alert.severity] ?? ""}>
                          {alert.severity}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {alert.description}
                      </p>
                      <p className="text-xs text-blue-600 dark:text-blue-400">
                        {alert.management}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* HCC Gap Opportunities Panel */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-green-500" />
                  HCC Gap Opportunities
                </CardTitle>
                <CardDescription>
                  Revenue recovery opportunities from documentation
                </CardDescription>
              </div>
              <Badge variant="outline" className="text-green-600">
                {isLoading
                  ? "..."
                  : `$${totalRevenueOpportunity.toLocaleString()} potential`}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">
                  Loading opportunities...
                </span>
              </div>
            ) : hccOpportunities.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">
                No HCC gap opportunities found. Provide clinical text to analyze
                for revenue opportunities.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>HCC</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>RAF</TableHead>
                    <TableHead>Est. Revenue</TableHead>
                    <TableHead>Confidence</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {hccOpportunities.map((opp) => (
                    <TableRow key={opp.id}>
                      <TableCell className="font-medium">
                        {opp.hccCode}
                      </TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium text-sm">
                            {opp.description}
                          </div>
                          <div className="text-xs text-muted-foreground truncate max-w-[200px]">
                            {opp.evidence}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>+{opp.rafValue.toFixed(3)}</TableCell>
                      <TableCell className="text-green-600 dark:text-green-400 font-medium">
                        ${opp.estimatedRevenue.toLocaleString()}
                      </TableCell>
                      <TableCell>
                        <Badge
                          className={
                            confidenceStyles[opp.confidence] ?? ""
                          }
                        >
                          {opp.confidence}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Documentation Issues Panel */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <FileWarning className="h-5 w-5 text-amber-500" />
                  Documentation Issues
                </CardTitle>
                <CardDescription>
                  Missing or incomplete documentation affecting coding
                </CardDescription>
              </div>
              <Badge variant="outline">
                {isLoading ? "..." : `${documentationIssues.length} issues`}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">
                  Loading issues...
                </span>
              </div>
            ) : documentationIssues.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">
                No documentation issues found.
              </p>
            ) : (
              <div className="space-y-3">
                {documentationIssues.map((issue) => (
                  <div
                    key={issue.id}
                    className="flex items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex-1 space-y-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge className={issueTypeStyles[issue.type] ?? ""}>
                          {issue.type}
                        </Badge>
                        <Badge
                          className={priorityStyles[issue.priority] ?? ""}
                        >
                          {issue.priority}
                        </Badge>
                        <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                          {issue.affectedCode}
                        </code>
                      </div>
                      <p className="text-sm">{issue.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Quality Measure Gaps Panel */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <ClipboardCheck className="h-5 w-5 text-blue-500" />
                  Quality Measure Gaps
                </CardTitle>
                <CardDescription>
                  HEDIS/CQM gaps requiring intervention
                </CardDescription>
              </div>
              <Badge variant="outline" className="text-red-600">
                {isLoading ? "..." : `${criticalGaps} critical`}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">
                  Loading quality gaps...
                </span>
              </div>
            ) : qualityGaps.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">
                No quality measure gaps found.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Measure</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Gap</TableHead>
                    <TableHead>Due</TableHead>
                    <TableHead>Priority</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {qualityGaps.map((gap) => (
                    <TableRow key={gap.id}>
                      <TableCell>
                        <div>
                          <div className="font-medium text-sm">
                            {gap.measureName}
                          </div>
                          <code className="text-xs text-muted-foreground">
                            {gap.measureId}
                          </code>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">{gap.category}</Badge>
                      </TableCell>
                      <TableCell className="max-w-[200px]">
                        <span className="text-sm">{gap.missingElement}</span>
                      </TableCell>
                      <TableCell className="text-sm">
                        {gap.dueDate || "--"}
                      </TableCell>
                      <TableCell>
                        <Badge
                          className={priorityStyles[gap.priority] ?? ""}
                        >
                          {gap.priority}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Clinical Calculators Quick Access */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Calculator className="h-5 w-5 text-purple-500" />
                Clinical Calculators
              </CardTitle>
              <CardDescription>
                Quick access to validated clinical risk calculators
                {availableCalculators > 0 &&
                  ` (${availableCalculators} available)`}
              </CardDescription>
            </div>
            <Link href="/clinical/tools">
              <Button variant="outline" size="sm">
                View All Calculators
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            {clinicalCalculators.map((calc) => (
              <Link key={calc.id} href={`/clinical/tools?calc=${calc.id}`}>
                <div className="flex flex-col items-center justify-center gap-2 rounded-lg border p-4 transition-colors hover:bg-muted/50 hover:border-primary/50 cursor-pointer h-full">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-purple-100 dark:bg-purple-900">
                    {calc.category === "Cardiology" ? (
                      <Heart className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                    ) : calc.category === "Renal" ? (
                      <Activity className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                    ) : (
                      <Stethoscope className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                    )}
                  </div>
                  <div className="text-center">
                    <p className="font-medium text-sm">{calc.shortName}</p>
                    <p className="text-xs text-muted-foreground">
                      {calc.description}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
