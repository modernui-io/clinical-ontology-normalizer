"use client";

import { useState, useEffect } from "react";
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
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DollarSign,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Clock,
  FileText,
  ArrowRight,
  RefreshCw,
  Target,
  AlertCircle,
  MessageSquare,
  Zap,
  BarChart3,
} from "lucide-react";

// Mock data for billing dashboard
interface RevenueOpportunity {
  id: string;
  category: string;
  description: string;
  estimatedAmount: number;
  confidence: "high" | "medium" | "low";
  status: "new" | "in_review" | "approved" | "implemented";
  patientId?: string;
  encounterId?: string;
}

interface HCCGap {
  id: string;
  hccCode: string;
  hccDescription: string;
  rafValue: number;
  estimatedRevenue: number;
  confidence: "high" | "medium" | "low";
  patientId: string;
  patientName: string;
  evidence: string[];
}

interface CodingSuggestion {
  id: string;
  type: "icd10" | "cpt";
  code: string;
  description: string;
  confidence: number;
  reason: string;
  impact: string;
  patientId?: string;
}

interface CDIQuery {
  id: string;
  queryId: string;
  question: string;
  status: "pending" | "sent" | "responded" | "resolved";
  priority: "stat" | "urgent" | "routine" | "deferred";
  estimatedImpact: number;
  createdAt: string;
  patientId: string;
  patientName: string;
}

interface BillingStats {
  totalRevenueOpportunity: number;
  hccGapCount: number;
  hccRevenuePotential: number;
  pendingQueries: number;
  codingSuggestions: number;
  monthlyRecovered: number;
  complianceScore: number;
}

// Mock data
const mockStats: BillingStats = {
  totalRevenueOpportunity: 487250,
  hccGapCount: 156,
  hccRevenuePotential: 312500,
  pendingQueries: 42,
  codingSuggestions: 89,
  monthlyRecovered: 125000,
  complianceScore: 92,
};

const mockRevenueOpportunities: RevenueOpportunity[] = [
  {
    id: "1",
    category: "HCC Gap",
    description: "Diabetes with chronic complications - documentation supports HCC37",
    estimatedAmount: 4320,
    confidence: "high",
    status: "new",
    patientId: "P001",
  },
  {
    id: "2",
    category: "E/M Upcoding",
    description: "Time documentation supports 99215 vs billed 99214",
    estimatedAmount: 68,
    confidence: "high",
    status: "in_review",
    encounterId: "E2001",
  },
  {
    id: "3",
    category: "Missed Service",
    description: "Tobacco cessation counseling documented but not billed (99406)",
    estimatedAmount: 25,
    confidence: "medium",
    status: "new",
    encounterId: "E2002",
  },
  {
    id: "4",
    category: "HCC Gap",
    description: "Heart failure - documentation supports HCC85",
    estimatedAmount: 4650,
    confidence: "high",
    status: "approved",
    patientId: "P003",
  },
  {
    id: "5",
    category: "Code Specificity",
    description: "CKD Stage 4 documented, coded as unspecified (N18.9 -> N18.4)",
    estimatedAmount: 3420,
    confidence: "medium",
    status: "new",
    patientId: "P004",
  },
];

const mockHCCGaps: HCCGap[] = [
  {
    id: "1",
    hccCode: "HCC37",
    hccDescription: "Diabetes with Chronic Complications",
    rafValue: 0.302,
    estimatedRevenue: 4354,
    confidence: "high",
    patientId: "P001",
    patientName: "John Smith",
    evidence: ["Diabetic nephropathy documented", "HbA1c 9.2% recorded"],
  },
  {
    id: "2",
    hccCode: "HCC85",
    hccDescription: "Heart Failure",
    rafValue: 0.323,
    estimatedRevenue: 4656,
    confidence: "high",
    patientId: "P003",
    patientName: "Mary Johnson",
    evidence: ["EF 35% on echo", "Chronic systolic HF noted"],
  },
  {
    id: "3",
    hccCode: "HCC327",
    hccDescription: "Chronic Kidney Disease, Stage 4",
    rafValue: 0.237,
    estimatedRevenue: 3417,
    confidence: "medium",
    patientId: "P004",
    patientName: "Robert Williams",
    evidence: ["eGFR 22 mL/min", "CKD Stage 4 in problem list"],
  },
];

const mockCodingSuggestions: CodingSuggestion[] = [
  {
    id: "1",
    type: "icd10",
    code: "E11.22",
    description: "Type 2 diabetes with diabetic CKD",
    confidence: 0.92,
    reason: "Documentation shows diabetic nephropathy with CKD",
    impact: "HCC capture: $4,320 annual",
    patientId: "P001",
  },
  {
    id: "2",
    type: "cpt",
    code: "99215",
    description: "Office visit, established patient, high MDM",
    confidence: 0.88,
    reason: "45 minutes documented with high complexity MDM",
    impact: "RVU increase: 0.88",
    patientId: "P002",
  },
  {
    id: "3",
    type: "icd10",
    code: "I50.22",
    description: "Chronic systolic heart failure",
    confidence: 0.95,
    reason: "Echo shows EF 35%, chronic HFrEF documented",
    impact: "HCC capture: $4,650 annual",
    patientId: "P003",
  },
];

const mockCDIQueries: CDIQuery[] = [
  {
    id: "1",
    queryId: "CDI-2026-001234",
    question: "Please specify the type of diabetes mellitus (Type 1 or Type 2)",
    status: "pending",
    priority: "urgent",
    estimatedImpact: 4320,
    createdAt: "2026-01-19T10:30:00Z",
    patientId: "P001",
    patientName: "John Smith",
  },
  {
    id: "2",
    queryId: "CDI-2026-001235",
    question: "Is the heart failure acute, chronic, or acute-on-chronic?",
    status: "sent",
    priority: "routine",
    estimatedImpact: 1200,
    createdAt: "2026-01-18T14:15:00Z",
    patientId: "P003",
    patientName: "Mary Johnson",
  },
  {
    id: "3",
    queryId: "CDI-2026-001236",
    question: "Please document the stage of chronic kidney disease",
    status: "responded",
    priority: "routine",
    estimatedImpact: 3420,
    createdAt: "2026-01-17T09:00:00Z",
    patientId: "P004",
    patientName: "Robert Williams",
  },
];

// Helper functions
const formatCurrency = (amount: number): string => {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
};

const getConfidenceBadgeVariant = (confidence: string): "default" | "secondary" | "outline" => {
  switch (confidence) {
    case "high":
      return "default";
    case "medium":
      return "secondary";
    default:
      return "outline";
  }
};

const getStatusColor = (status: string): string => {
  switch (status) {
    case "new":
      return "text-blue-600 bg-blue-50 dark:bg-blue-950";
    case "in_review":
      return "text-yellow-600 bg-yellow-50 dark:bg-yellow-950";
    case "approved":
      return "text-green-600 bg-green-50 dark:bg-green-950";
    case "implemented":
      return "text-purple-600 bg-purple-50 dark:bg-purple-950";
    case "pending":
      return "text-orange-600 bg-orange-50 dark:bg-orange-950";
    case "sent":
      return "text-blue-600 bg-blue-50 dark:bg-blue-950";
    case "responded":
      return "text-green-600 bg-green-50 dark:bg-green-950";
    case "resolved":
      return "text-gray-600 bg-gray-50 dark:bg-gray-950";
    default:
      return "text-gray-600 bg-gray-50 dark:bg-gray-950";
  }
};

const getPriorityColor = (priority: string): string => {
  switch (priority) {
    case "stat":
      return "text-red-600 bg-red-50 dark:bg-red-950";
    case "urgent":
      return "text-orange-600 bg-orange-50 dark:bg-orange-950";
    case "routine":
      return "text-blue-600 bg-blue-50 dark:bg-blue-950";
    case "deferred":
      return "text-gray-600 bg-gray-50 dark:bg-gray-950";
    default:
      return "text-gray-600 bg-gray-50 dark:bg-gray-950";
  }
};

export default function BillingDashboardPage() {
  const [stats, setStats] = useState<BillingStats>(mockStats);
  const [revenueOpportunities] = useState<RevenueOpportunity[]>(mockRevenueOpportunities);
  const [hccGaps] = useState<HCCGap[]>(mockHCCGaps);
  const [codingSuggestions] = useState<CodingSuggestion[]>(mockCodingSuggestions);
  const [cdiQueries] = useState<CDIQuery[]>(mockCDIQueries);
  const [isLoading, setIsLoading] = useState(false);

  const refreshData = async () => {
    setIsLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setStats(mockStats);
    setIsLoading(false);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Billing & Revenue Dashboard</h1>
          <p className="text-muted-foreground">
            Revenue opportunities, HCC gaps, and coding optimization
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={refreshData}
          disabled={isLoading}
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Key Metrics Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Total Revenue Opportunity */}
        <Card className="border-l-4 border-l-green-500">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Revenue Opportunity</CardTitle>
            <DollarSign className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {formatCurrency(stats.totalRevenueOpportunity)}
            </div>
            <p className="text-xs text-muted-foreground">
              Across all identified opportunities
            </p>
          </CardContent>
        </Card>

        {/* HCC Revenue Potential */}
        <Card className="border-l-4 border-l-blue-500">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">HCC Revenue Potential</CardTitle>
            <Target className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {formatCurrency(stats.hccRevenuePotential)}
            </div>
            <p className="text-xs text-muted-foreground">
              <span className="text-blue-600">{stats.hccGapCount}</span> HCC gaps identified
            </p>
          </CardContent>
        </Card>

        {/* Pending CDI Queries */}
        <Card className="border-l-4 border-l-yellow-500">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Pending Queries</CardTitle>
            <MessageSquare className="h-4 w-4 text-yellow-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">{stats.pendingQueries}</div>
            <p className="text-xs text-muted-foreground">
              <span className="text-yellow-600">{stats.codingSuggestions}</span> coding suggestions
            </p>
          </CardContent>
        </Card>

        {/* Compliance Score */}
        <Card className="border-l-4 border-l-purple-500">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Compliance Score</CardTitle>
            <CheckCircle className="h-4 w-4 text-purple-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">{stats.complianceScore}%</div>
            <Progress value={stats.complianceScore} className="mt-2 h-2" />
          </CardContent>
        </Card>
      </div>

      {/* Revenue Trend Placeholder */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Revenue Recovery Trend
          </CardTitle>
          <CardDescription>Monthly recovered revenue from coding optimization</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-48 items-center justify-center rounded-lg border-2 border-dashed bg-muted/30">
            <div className="text-center">
              <TrendingUp className="mx-auto h-12 w-12 text-muted-foreground/50" />
              <p className="mt-2 text-sm text-muted-foreground">
                Revenue trend chart will display here
              </p>
              <p className="text-xs text-muted-foreground">
                Monthly recovered: {formatCurrency(stats.monthlyRecovered)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content Tabs */}
      <Tabs defaultValue="opportunities" className="space-y-4">
        <TabsList>
          <TabsTrigger value="opportunities" className="gap-2">
            <Zap className="h-4 w-4" />
            Opportunities
          </TabsTrigger>
          <TabsTrigger value="hcc" className="gap-2">
            <Target className="h-4 w-4" />
            HCC Gaps
          </TabsTrigger>
          <TabsTrigger value="coding" className="gap-2">
            <FileText className="h-4 w-4" />
            Coding
          </TabsTrigger>
          <TabsTrigger value="queries" className="gap-2">
            <MessageSquare className="h-4 w-4" />
            CDI Queries
          </TabsTrigger>
        </TabsList>

        {/* Revenue Opportunities Tab */}
        <TabsContent value="opportunities" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Revenue Opportunities</CardTitle>
                  <CardDescription>
                    Identified billing and coding opportunities with estimated impact
                  </CardDescription>
                </div>
                <Link href="/billing/opportunities">
                  <Button variant="outline" size="sm">
                    View All
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {revenueOpportunities.map((opportunity) => (
                  <div
                    key={opportunity.id}
                    className="flex items-start justify-between gap-4 rounded-lg border p-4 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{opportunity.category}</Badge>
                        <Badge variant={getConfidenceBadgeVariant(opportunity.confidence)}>
                          {opportunity.confidence} confidence
                        </Badge>
                        <span className={`rounded px-2 py-0.5 text-xs font-medium ${getStatusColor(opportunity.status)}`}>
                          {opportunity.status.replace("_", " ")}
                        </span>
                      </div>
                      <p className="text-sm">{opportunity.description}</p>
                      {(opportunity.patientId || opportunity.encounterId) && (
                        <p className="text-xs text-muted-foreground">
                          {opportunity.patientId && `Patient: ${opportunity.patientId}`}
                          {opportunity.encounterId && ` | Encounter: ${opportunity.encounterId}`}
                        </p>
                      )}
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold text-green-600">
                        {formatCurrency(opportunity.estimatedAmount)}
                      </p>
                      <p className="text-xs text-muted-foreground">estimated</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* HCC Gaps Tab */}
        <TabsContent value="hcc" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>HCC Gap Analysis</CardTitle>
                  <CardDescription>
                    Missing HCC diagnoses with RAF values and evidence
                  </CardDescription>
                </div>
                <Link href="/billing/hcc">
                  <Button variant="outline" size="sm">
                    View Full Analysis
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {hccGaps.map((gap) => (
                  <div
                    key={gap.id}
                    className="flex items-start justify-between gap-4 rounded-lg border p-4 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex-1 space-y-2">
                      <div className="flex items-center gap-2">
                        <Badge className="bg-blue-600">{gap.hccCode}</Badge>
                        <span className="font-medium">{gap.hccDescription}</span>
                        <Badge variant={getConfidenceBadgeVariant(gap.confidence)}>
                          {gap.confidence}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        Patient: {gap.patientName} ({gap.patientId})
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {gap.evidence.map((ev, idx) => (
                          <span
                            key={idx}
                            className="rounded bg-muted px-2 py-0.5 text-xs"
                          >
                            {ev}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold text-green-600">
                        {formatCurrency(gap.estimatedRevenue)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        RAF: {gap.rafValue.toFixed(3)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Coding Suggestions Tab */}
        <TabsContent value="coding" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Coding Suggestions</CardTitle>
                  <CardDescription>
                    ICD-10 and CPT code recommendations with confidence scores
                  </CardDescription>
                </div>
                <Link href="/billing/coding">
                  <Button variant="outline" size="sm">
                    View All Suggestions
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {codingSuggestions.map((suggestion) => (
                  <div
                    key={suggestion.id}
                    className="flex items-start justify-between gap-4 rounded-lg border p-4 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex-1 space-y-2">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={suggestion.type === "icd10" ? "default" : "secondary"}
                        >
                          {suggestion.type.toUpperCase()}
                        </Badge>
                        <code className="rounded bg-muted px-2 py-0.5 text-sm font-mono">
                          {suggestion.code}
                        </code>
                        <span className="font-medium">{suggestion.description}</span>
                      </div>
                      <p className="text-sm text-muted-foreground">{suggestion.reason}</p>
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">Confidence:</span>
                          <Progress
                            value={suggestion.confidence * 100}
                            className="h-2 w-20"
                          />
                          <span className="text-xs font-medium">
                            {Math.round(suggestion.confidence * 100)}%
                          </span>
                        </div>
                        <span className="text-xs text-green-600">{suggestion.impact}</span>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline">
                        Review
                      </Button>
                      <Button size="sm">Accept</Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* CDI Queries Tab */}
        <TabsContent value="queries" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>CDI Query Tracker</CardTitle>
                  <CardDescription>
                    Clinical Documentation Improvement queries and responses
                  </CardDescription>
                </div>
                <Link href="/billing/queries">
                  <Button variant="outline" size="sm">
                    Manage Queries
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {cdiQueries.map((query) => (
                  <div
                    key={query.id}
                    className="flex items-start justify-between gap-4 rounded-lg border p-4 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex-1 space-y-2">
                      <div className="flex items-center gap-2">
                        <code className="rounded bg-muted px-2 py-0.5 text-xs font-mono">
                          {query.queryId}
                        </code>
                        <span className={`rounded px-2 py-0.5 text-xs font-medium ${getPriorityColor(query.priority)}`}>
                          {query.priority}
                        </span>
                        <span className={`rounded px-2 py-0.5 text-xs font-medium ${getStatusColor(query.status)}`}>
                          {query.status}
                        </span>
                      </div>
                      <p className="text-sm">{query.question}</p>
                      <p className="text-xs text-muted-foreground">
                        Patient: {query.patientName} ({query.patientId}) | Created:{" "}
                        {new Date(query.createdAt).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold text-green-600">
                        {formatCurrency(query.estimatedImpact)}
                      </p>
                      <p className="text-xs text-muted-foreground">potential impact</p>
                      {query.status === "pending" && (
                        <Button size="sm" className="mt-2">
                          Send Query
                        </Button>
                      )}
                      {query.status === "responded" && (
                        <Button size="sm" variant="outline" className="mt-2">
                          Review Response
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>Common billing and coding tasks</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Link href="/billing/suggestions" className="block">
              <Button variant="outline" className="w-full justify-start">
                <Zap className="mr-2 h-4 w-4" />
                AI Code Suggestions
              </Button>
            </Link>
            <Link href="/billing/hcc" className="block">
              <Button variant="outline" className="w-full justify-start">
                <Target className="mr-2 h-4 w-4" />
                HCC Gap Analysis
              </Button>
            </Link>
            <Link href="/billing/worksheet" className="block">
              <Button variant="outline" className="w-full justify-start">
                <FileText className="mr-2 h-4 w-4" />
                Coding Worksheet
              </Button>
            </Link>
            <Link href="/billing/coding" className="block">
              <Button variant="outline" className="w-full justify-start">
                <CheckCircle className="mr-2 h-4 w-4" />
                Review Suggestions
              </Button>
            </Link>
            <Link href="/billing/queries" className="block">
              <Button variant="outline" className="w-full justify-start">
                <MessageSquare className="mr-2 h-4 w-4" />
                CDI Queries
              </Button>
            </Link>
            <Link href="/billing/reports" className="block">
              <Button variant="outline" className="w-full justify-start">
                <BarChart3 className="mr-2 h-4 w-4" />
                Generate Reports
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
