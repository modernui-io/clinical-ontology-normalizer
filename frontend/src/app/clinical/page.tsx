"use client";

import { useState } from "react";
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

// Types for CDS data
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

// Mock data for demonstration
const mockDrugAlerts: DrugAlert[] = [
  {
    id: "1",
    drug1: "Warfarin",
    drug2: "Aspirin",
    severity: "major",
    description: "Additive anticoagulant/antiplatelet effects",
    management: "Monitor INR closely; avoid unless specifically indicated",
  },
  {
    id: "2",
    drug1: "Simvastatin",
    drug2: "Clarithromycin",
    severity: "contraindicated",
    description: "Strong CYP3A4 inhibition increases simvastatin levels 10-fold",
    management: "Contraindicated; suspend simvastatin during clarithromycin course",
  },
  {
    id: "3",
    drug1: "Metformin",
    drug2: "Lisinopril",
    severity: "moderate",
    description: "ACE inhibitors may enhance hypoglycemic effect",
    management: "Monitor blood glucose; may need to reduce metformin dose",
  },
  {
    id: "4",
    drug1: "Gabapentin",
    drug2: "Morphine",
    severity: "moderate",
    description: "Additive CNS depression",
    management: "Start with lower doses; monitor for respiratory depression",
  },
];

const mockHCCOpportunities: HCCOpportunity[] = [
  {
    id: "1",
    hccCode: "HCC85",
    description: "Heart Failure",
    rafValue: 0.323,
    estimatedRevenue: 4651,
    confidence: "high",
    evidence: "Documentation mentions 'CHF', 'reduced EF 35%', BNP elevated",
  },
  {
    id: "2",
    hccCode: "HCC37",
    description: "Diabetes with Chronic Complications",
    rafValue: 0.302,
    estimatedRevenue: 4349,
    confidence: "high",
    evidence: "Diabetic nephropathy documented, UACR >300 mg/g",
  },
  {
    id: "3",
    hccCode: "HCC111",
    description: "COPD",
    rafValue: 0.335,
    estimatedRevenue: 4824,
    confidence: "medium",
    evidence: "History of emphysema mentioned, FEV1/FVC ratio <0.7",
  },
  {
    id: "4",
    hccCode: "HCC155",
    description: "Major Depression, Moderate/Severe",
    rafValue: 0.309,
    estimatedRevenue: 4450,
    confidence: "low",
    evidence: "Depression noted but severity not specified",
  },
];

const mockDocumentationIssues: DocumentationIssue[] = [
  {
    id: "1",
    type: "incomplete",
    description: "Diabetes type not specified (Type 1 vs Type 2)",
    affectedCode: "E11.9",
    priority: "high",
  },
  {
    id: "2",
    type: "missing",
    description: "Heart failure type missing (HFrEF vs HFpEF)",
    affectedCode: "I50.9",
    priority: "high",
  },
  {
    id: "3",
    type: "conflicting",
    description: "CKD stage documented as both 3 and 4 in different notes",
    affectedCode: "N18.3/N18.4",
    priority: "medium",
  },
  {
    id: "4",
    type: "incomplete",
    description: "BMI 42 documented but morbid obesity not coded",
    affectedCode: "E66.01",
    priority: "medium",
  },
];

const mockQualityGaps: QualityGap[] = [
  {
    id: "1",
    measureId: "HEDIS-CDC-HBA1C",
    measureName: "Diabetes: HbA1c Control (<8%)",
    category: "Diabetes",
    missingElement: "HbA1c test overdue by 45 days",
    dueDate: "2024-11-15",
    priority: "critical",
  },
  {
    id: "2",
    measureId: "HEDIS-CDC-EYE",
    measureName: "Diabetes: Eye Exam",
    category: "Diabetes",
    missingElement: "Annual dilated eye exam not documented",
    dueDate: "2024-12-31",
    priority: "high",
  },
  {
    id: "3",
    measureId: "HEDIS-BCS",
    measureName: "Breast Cancer Screening",
    category: "Preventive",
    missingElement: "Mammogram due (last: 2022-06-15)",
    dueDate: "2024-06-15",
    priority: "high",
  },
  {
    id: "4",
    measureId: "HEDIS-CBP",
    measureName: "Controlling High Blood Pressure",
    category: "Cardiovascular",
    missingElement: "Last BP reading 145/92 (target: <140/90)",
    dueDate: "2024-12-31",
    priority: "medium",
  },
];

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

// Severity badge styling
const severityStyles = {
  contraindicated: "bg-red-600 text-white hover:bg-red-700",
  major: "bg-red-500 text-white hover:bg-red-600",
  moderate: "bg-amber-500 text-white hover:bg-amber-600",
  minor: "bg-blue-500 text-white hover:bg-blue-600",
};

const priorityStyles = {
  critical: "bg-red-600 text-white",
  high: "bg-red-500 text-white",
  medium: "bg-amber-500 text-white",
  low: "bg-blue-500 text-white",
};

const confidenceStyles = {
  high: "bg-green-500 text-white",
  medium: "bg-amber-500 text-white",
  low: "bg-gray-500 text-white",
};

const issueTypeStyles = {
  missing: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  incomplete: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  conflicting: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
};

export default function ClinicalDashboardPage() {
  const [isLoading, setIsLoading] = useState(false);

  const refreshData = async () => {
    setIsLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsLoading(false);
  };

  // Calculate summary stats
  const totalAlerts = mockDrugAlerts.length;
  const criticalAlerts = mockDrugAlerts.filter(
    (a) => a.severity === "contraindicated" || a.severity === "major"
  ).length;
  const totalRAFOpportunity = mockHCCOpportunities.reduce(
    (sum, o) => sum + o.rafValue,
    0
  );
  const totalRevenueOpportunity = mockHCCOpportunities.reduce(
    (sum, o) => sum + o.estimatedRevenue,
    0
  );
  const criticalGaps = mockQualityGaps.filter(
    (g) => g.priority === "critical"
  ).length;

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Clinical Decision Support
          </h1>
          <p className="text-muted-foreground">
            Real-time clinical alerts, HCC opportunities, and quality measure gaps
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
          <Link href="/clinical/tools">
            <Button size="sm">
              <Calculator className="mr-2 h-4 w-4" />
              Calculators
            </Button>
          </Link>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Drug Alerts</CardTitle>
            <Pill className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalAlerts}</div>
            <p className="text-xs text-muted-foreground">
              <span className="text-red-600 dark:text-red-400 font-medium">
                {criticalAlerts} critical
              </span>{" "}
              interactions detected
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">RAF Opportunity</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              +{totalRAFOpportunity.toFixed(3)}
            </div>
            <p className="text-xs text-muted-foreground">
              {mockHCCOpportunities.length} HCC gaps identified
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
              ${totalRevenueOpportunity.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              Potential annual revenue
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Quality Gaps</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{mockQualityGaps.length}</div>
            <p className="text-xs text-muted-foreground">
              <span className="text-red-600 dark:text-red-400 font-medium">
                {criticalGaps} critical
              </span>{" "}
              gaps to close
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
            <div className="space-y-3">
              {mockDrugAlerts.map((alert) => (
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
                      <Badge className={severityStyles[alert.severity]}>
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
                ${totalRevenueOpportunity.toLocaleString()} potential
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
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
                {mockHCCOpportunities.map((opp) => (
                  <TableRow key={opp.id}>
                    <TableCell className="font-medium">{opp.hccCode}</TableCell>
                    <TableCell>
                      <div>
                        <div className="font-medium text-sm">{opp.description}</div>
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
                      <Badge className={confidenceStyles[opp.confidence]}>
                        {opp.confidence}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
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
                {mockDocumentationIssues.length} issues
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {mockDocumentationIssues.map((issue) => (
                <div
                  key={issue.id}
                  className="flex items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/50"
                >
                  <div className="flex-1 space-y-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge className={issueTypeStyles[issue.type]}>
                        {issue.type}
                      </Badge>
                      <Badge className={priorityStyles[issue.priority]}>
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
                {criticalGaps} critical
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
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
                {mockQualityGaps.map((gap) => (
                  <TableRow key={gap.id}>
                    <TableCell>
                      <div>
                        <div className="font-medium text-sm">{gap.measureName}</div>
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
                    <TableCell className="text-sm">{gap.dueDate}</TableCell>
                    <TableCell>
                      <Badge className={priorityStyles[gap.priority]}>
                        {gap.priority}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
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
