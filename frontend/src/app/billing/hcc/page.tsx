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
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Target,
  Search,
  Filter,
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  DollarSign,
  AlertCircle,
  CheckCircle,
  Clock,
  FileText,
  User,
  TrendingUp,
  Download,
} from "lucide-react";

// HCC Categories for filtering
const HCC_CATEGORIES = [
  { value: "all", label: "All Categories" },
  { value: "diabetes", label: "Diabetes" },
  { value: "cardiovascular", label: "Cardiovascular" },
  { value: "renal", label: "Renal" },
  { value: "respiratory", label: "Respiratory" },
  { value: "neurological", label: "Neurological" },
  { value: "psychiatric", label: "Psychiatric" },
  { value: "metabolic", label: "Metabolic" },
  { value: "vascular", label: "Vascular" },
  { value: "immune", label: "Immune" },
];

// Confidence levels for filtering
const CONFIDENCE_LEVELS = [
  { value: "all", label: "All Confidence" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

// Gap types
const GAP_TYPES = [
  { value: "all", label: "All Types" },
  { value: "not_coded", label: "Not Coded" },
  { value: "needs_specificity", label: "Needs Specificity" },
  { value: "needs_recapture", label: "Needs Recapture" },
  { value: "suspect", label: "Suspect" },
];

interface HCCOpportunity {
  id: string;
  patientId: string;
  patientName: string;
  hccCode: string;
  hccDescription: string;
  category: string;
  gapType: "not_coded" | "needs_specificity" | "needs_recapture" | "suspect";
  confidence: "high" | "medium" | "low";
  rafValue: number;
  estimatedRevenue: number;
  currentIcd10: string | null;
  recommendedIcd10: string;
  evidence: {
    source: string;
    text: string;
    date: string | null;
  }[];
  documentationNeeded: string[];
  coderNotes: string;
  lastUpdated: string;
}

// Mock data for HCC opportunities
const mockHCCOpportunities: HCCOpportunity[] = [
  {
    id: "1",
    patientId: "P001",
    patientName: "John Smith",
    hccCode: "HCC37",
    hccDescription: "Diabetes with Chronic Complications",
    category: "diabetes",
    gapType: "not_coded",
    confidence: "high",
    rafValue: 0.302,
    estimatedRevenue: 4354,
    currentIcd10: "E11.9",
    recommendedIcd10: "E11.22",
    evidence: [
      { source: "note", text: "...patient has diabetic nephropathy with CKD stage 3...", date: "2026-01-15" },
      { source: "lab", text: "HbA1c: 9.2% (threshold: >9.0%)", date: "2026-01-10" },
      { source: "lab", text: "eGFR: 42 mL/min (threshold: <60)", date: "2026-01-10" },
    ],
    documentationNeeded: [
      "Type of diabetes (1 or 2)",
      "Specific complication (nephropathy, retinopathy, neuropathy, etc.)",
      "Causal relationship between diabetes and complication",
    ],
    coderNotes: "Documentation supports Diabetes with Chronic Complications but not currently coded. Key terms found: diabetic nephropathy, ckd. Ensure documentation includes: Type of diabetes, Specific complication.",
    lastUpdated: "2026-01-19T10:30:00Z",
  },
  {
    id: "2",
    patientId: "P003",
    patientName: "Mary Johnson",
    hccCode: "HCC85",
    hccDescription: "Heart Failure",
    category: "cardiovascular",
    gapType: "not_coded",
    confidence: "high",
    rafValue: 0.323,
    estimatedRevenue: 4656,
    currentIcd10: null,
    recommendedIcd10: "I50.22",
    evidence: [
      { source: "note", text: "...chronic systolic heart failure with EF 35%...", date: "2026-01-12" },
      { source: "lab", text: "BNP: 450 pg/mL (threshold: >100)", date: "2026-01-08" },
      { source: "note", text: "...patient on lisinopril and carvedilol for HFrEF management...", date: "2026-01-12" },
    ],
    documentationNeeded: [
      "Type of heart failure (systolic/HFrEF, diastolic/HFpEF, combined)",
      "Acuity (acute, chronic, acute-on-chronic)",
      "Ejection fraction if known",
    ],
    coderNotes: "Documentation supports Heart Failure but not currently coded. Key terms found: heart failure, hfref, ef. Ensure documentation includes: Type of heart failure, Acuity.",
    lastUpdated: "2026-01-19T09:15:00Z",
  },
  {
    id: "3",
    patientId: "P004",
    patientName: "Robert Williams",
    hccCode: "HCC327",
    hccDescription: "Chronic Kidney Disease, Stage 4",
    category: "renal",
    gapType: "needs_specificity",
    confidence: "medium",
    rafValue: 0.237,
    estimatedRevenue: 3417,
    currentIcd10: "N18.9",
    recommendedIcd10: "N18.4",
    evidence: [
      { source: "lab", text: "eGFR: 22 mL/min (threshold: 15-29)", date: "2026-01-11" },
      { source: "note", text: "...CKD Stage 4 per nephrology consult...", date: "2026-01-05" },
    ],
    documentationNeeded: [
      "CKD Stage 4 explicitly documented",
      "Etiology if known (diabetic, hypertensive, etc.)",
    ],
    coderNotes: "Current code lacks specificity for HCC capture. Review for more specific code. Key terms found: ckd stage 4.",
    lastUpdated: "2026-01-18T14:20:00Z",
  },
  {
    id: "4",
    patientId: "P005",
    patientName: "Sarah Davis",
    hccCode: "HCC111",
    hccDescription: "Chronic Obstructive Pulmonary Disease",
    category: "respiratory",
    gapType: "needs_recapture",
    confidence: "high",
    rafValue: 0.335,
    estimatedRevenue: 4829,
    currentIcd10: null,
    recommendedIcd10: "J44.1",
    evidence: [
      { source: "note", text: "...COPD with recent exacerbation requiring prednisone burst...", date: "2026-01-14" },
      { source: "note", text: "...patient uses albuterol and Symbicort inhalers...", date: "2026-01-14" },
    ],
    documentationNeeded: [
      "COPD diagnosis with specificity (with exacerbation, etc.)",
      "Severity if known (GOLD stage)",
    ],
    coderNotes: "COPD was captured in prior year but needs recapture for this measurement year. Documentation clearly supports diagnosis.",
    lastUpdated: "2026-01-17T11:45:00Z",
  },
  {
    id: "5",
    patientId: "P006",
    patientName: "Michael Brown",
    hccCode: "HCC155",
    hccDescription: "Major Depression, Moderate or Severe",
    category: "psychiatric",
    gapType: "suspect",
    confidence: "medium",
    rafValue: 0.309,
    estimatedRevenue: 4454,
    currentIcd10: "F32.9",
    recommendedIcd10: "F33.1",
    evidence: [
      { source: "note", text: "...depression, currently on Zoloft 100mg...", date: "2026-01-13" },
      { source: "note", text: "...PHQ-9 score 18 indicating moderately severe depression...", date: "2026-01-13" },
    ],
    documentationNeeded: [
      "Severity (mild, moderate, severe)",
      "Single episode vs recurrent",
      "With or without psychotic features",
    ],
    coderNotes: "Lab values suggest this condition. Query provider for confirmation. PHQ-9 score supports moderate-severe depression.",
    lastUpdated: "2026-01-16T16:00:00Z",
  },
  {
    id: "6",
    patientId: "P007",
    patientName: "Jennifer Wilson",
    hccCode: "HCC48",
    hccDescription: "Morbid Obesity",
    category: "metabolic",
    gapType: "not_coded",
    confidence: "high",
    rafValue: 0.250,
    estimatedRevenue: 3604,
    currentIcd10: "E66.9",
    recommendedIcd10: "E66.01",
    evidence: [
      { source: "note", text: "...BMI 42.3 kg/m2...", date: "2026-01-09" },
      { source: "lab", text: "BMI: 42.3 kg/m2 (threshold: >=40)", date: "2026-01-09" },
    ],
    documentationNeeded: [
      "BMI >= 40 or BMI >= 35 with comorbidity",
      "Morbid obesity explicitly documented (not just BMI)",
    ],
    coderNotes: "Documentation supports Morbid Obesity but not currently coded. BMI of 42.3 meets threshold. Ensure morbid obesity is explicitly documented.",
    lastUpdated: "2026-01-15T08:30:00Z",
  },
  {
    id: "7",
    patientId: "P008",
    patientName: "David Martinez",
    hccCode: "HCC108",
    hccDescription: "Vascular Disease",
    category: "vascular",
    gapType: "not_coded",
    confidence: "medium",
    rafValue: 0.288,
    estimatedRevenue: 4152,
    currentIcd10: null,
    recommendedIcd10: "I70.201",
    evidence: [
      { source: "note", text: "...peripheral arterial disease with claudication...", date: "2026-01-11" },
      { source: "lab", text: "ABI: 0.7 (threshold: <0.9)", date: "2026-01-11" },
    ],
    documentationNeeded: [
      "PVD/PAD explicitly documented",
      "Severity/stage if known",
      "Affected vessels if known",
    ],
    coderNotes: "Documentation suggests PVD/PAD. ABI of 0.7 confirms diagnosis. Ensure PVD is explicitly documented in assessment.",
    lastUpdated: "2026-01-14T13:00:00Z",
  },
  {
    id: "8",
    patientId: "P009",
    patientName: "Lisa Anderson",
    hccCode: "HCC40",
    hccDescription: "Rheumatoid Arthritis and Inflammatory Connective Tissue Disease",
    category: "immune",
    gapType: "needs_recapture",
    confidence: "high",
    rafValue: 0.374,
    estimatedRevenue: 5392,
    currentIcd10: null,
    recommendedIcd10: "M05.00",
    evidence: [
      { source: "note", text: "...seropositive rheumatoid arthritis on methotrexate...", date: "2026-01-10" },
      { source: "lab", text: "RF: 85 IU/mL (threshold: >14)", date: "2025-12-20" },
    ],
    documentationNeeded: [
      "Specific type of inflammatory arthritis",
      "Seropositive vs seronegative for RA",
      "Organ involvement if present",
    ],
    coderNotes: "RA was captured in prior year but needs recapture. Documentation clearly supports seropositive RA.",
    lastUpdated: "2026-01-13T10:15:00Z",
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

const getConfidenceColor = (confidence: string): string => {
  switch (confidence) {
    case "high":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "medium":
      return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200";
    case "low":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

const getGapTypeColor = (gapType: string): string => {
  switch (gapType) {
    case "not_coded":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "needs_specificity":
      return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
    case "needs_recapture":
      return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200";
    case "suspect":
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

const getGapTypeLabel = (gapType: string): string => {
  switch (gapType) {
    case "not_coded":
      return "Not Coded";
    case "needs_specificity":
      return "Needs Specificity";
    case "needs_recapture":
      return "Needs Recapture";
    case "suspect":
      return "Suspect";
    default:
      return gapType;
  }
};

export default function HCCAnalysisPage() {
  const [opportunities] = useState<HCCOpportunity[]>(mockHCCOpportunities);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [selectedConfidence, setSelectedConfidence] = useState("all");
  const [selectedGapType, setSelectedGapType] = useState("all");
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [sortField, setSortField] = useState<"rafValue" | "estimatedRevenue">("estimatedRevenue");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");

  // Filter opportunities
  const filteredOpportunities = opportunities.filter((opp) => {
    const matchesSearch =
      searchQuery === "" ||
      opp.patientName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      opp.patientId.toLowerCase().includes(searchQuery.toLowerCase()) ||
      opp.hccCode.toLowerCase().includes(searchQuery.toLowerCase()) ||
      opp.hccDescription.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesCategory = selectedCategory === "all" || opp.category === selectedCategory;
    const matchesConfidence = selectedConfidence === "all" || opp.confidence === selectedConfidence;
    const matchesGapType = selectedGapType === "all" || opp.gapType === selectedGapType;

    return matchesSearch && matchesCategory && matchesConfidence && matchesGapType;
  });

  // Sort opportunities
  const sortedOpportunities = [...filteredOpportunities].sort((a, b) => {
    const multiplier = sortDirection === "asc" ? 1 : -1;
    return (a[sortField] - b[sortField]) * multiplier;
  });

  // Calculate summary stats
  const totalRAF = sortedOpportunities.reduce((sum, opp) => sum + opp.rafValue, 0);
  const totalRevenue = sortedOpportunities.reduce((sum, opp) => sum + opp.estimatedRevenue, 0);
  const highConfidenceRevenue = sortedOpportunities
    .filter((opp) => opp.confidence === "high")
    .reduce((sum, opp) => sum + opp.estimatedRevenue, 0);

  const toggleExpanded = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  const handleSort = (field: "rafValue" | "estimatedRevenue") => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/billing">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">HCC Gap Analysis</h1>
            <p className="text-muted-foreground">
              Identify missing HCC diagnoses and revenue opportunities
            </p>
          </div>
        </div>
        <Button>
          <Download className="mr-2 h-4 w-4" />
          Export Report
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="border-l-4 border-l-green-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Revenue Opportunity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{formatCurrency(totalRevenue)}</div>
            <p className="text-xs text-muted-foreground">
              {sortedOpportunities.length} gaps identified
            </p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-blue-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">High Confidence Revenue</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{formatCurrency(highConfidenceRevenue)}</div>
            <p className="text-xs text-muted-foreground">
              {sortedOpportunities.filter((o) => o.confidence === "high").length} high confidence gaps
            </p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-purple-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total RAF Opportunity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">{totalRAF.toFixed(3)}</div>
            <p className="text-xs text-muted-foreground">Potential RAF increase</p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-orange-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Patients Affected</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {new Set(sortedOpportunities.map((o) => o.patientId)).size}
            </div>
            <p className="text-xs text-muted-foreground">Unique patients with gaps</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-4">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search patient, HCC code..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>

            {/* Category Filter */}
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {HCC_CATEGORIES.map((cat) => (
                <option key={cat.value} value={cat.value}>
                  {cat.label}
                </option>
              ))}
            </select>

            {/* Confidence Filter */}
            <select
              value={selectedConfidence}
              onChange={(e) => setSelectedConfidence(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {CONFIDENCE_LEVELS.map((conf) => (
                <option key={conf.value} value={conf.value}>
                  {conf.label}
                </option>
              ))}
            </select>

            {/* Gap Type Filter */}
            <select
              value={selectedGapType}
              onChange={(e) => setSelectedGapType(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {GAP_TYPES.map((gap) => (
                <option key={gap.value} value={gap.value}>
                  {gap.label}
                </option>
              ))}
            </select>
          </div>
        </CardContent>
      </Card>

      {/* HCC Gaps Table */}
      <Card>
        <CardHeader>
          <CardTitle>HCC Gaps by Patient</CardTitle>
          <CardDescription>
            Click on a row to see detailed evidence and documentation requirements
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10"></TableHead>
                  <TableHead>Patient</TableHead>
                  <TableHead>HCC Code</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Gap Type</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => handleSort("rafValue")}
                  >
                    <div className="flex items-center gap-1">
                      RAF Value
                      {sortField === "rafValue" && (
                        sortDirection === "asc" ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />
                      )}
                    </div>
                  </TableHead>
                  <TableHead
                    className="cursor-pointer hover:bg-muted/50 text-right"
                    onClick={() => handleSort("estimatedRevenue")}
                  >
                    <div className="flex items-center justify-end gap-1">
                      Est. Revenue
                      {sortField === "estimatedRevenue" && (
                        sortDirection === "asc" ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />
                      )}
                    </div>
                  </TableHead>
                  <TableHead className="w-24">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedOpportunities.map((opp) => (
                  <>
                    <TableRow
                      key={opp.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => toggleExpanded(opp.id)}
                    >
                      <TableCell>
                        {expandedRows.has(opp.id) ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <User className="h-4 w-4 text-muted-foreground" />
                          <div>
                            <p className="font-medium">{opp.patientName}</p>
                            <p className="text-xs text-muted-foreground">{opp.patientId}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <Badge variant="outline" className="font-mono">
                            {opp.hccCode}
                          </Badge>
                          <p className="mt-1 text-xs text-muted-foreground max-w-48 truncate">
                            {opp.hccDescription}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell className="capitalize">{opp.category}</TableCell>
                      <TableCell>
                        <span className={`rounded px-2 py-1 text-xs font-medium ${getGapTypeColor(opp.gapType)}`}>
                          {getGapTypeLabel(opp.gapType)}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className={`rounded px-2 py-1 text-xs font-medium ${getConfidenceColor(opp.confidence)}`}>
                          {opp.confidence}
                        </span>
                      </TableCell>
                      <TableCell className="font-mono">{opp.rafValue.toFixed(3)}</TableCell>
                      <TableCell className="text-right">
                        <span className="font-bold text-green-600">{formatCurrency(opp.estimatedRevenue)}</span>
                      </TableCell>
                      <TableCell>
                        <Button size="sm" variant="outline" onClick={(e) => e.stopPropagation()}>
                          Review
                        </Button>
                      </TableCell>
                    </TableRow>
                    {expandedRows.has(opp.id) && (
                      <TableRow key={`${opp.id}-expanded`}>
                        <TableCell colSpan={9} className="bg-muted/30 p-4">
                          <div className="grid gap-4 md:grid-cols-3">
                            {/* Evidence */}
                            <div className="space-y-2">
                              <h4 className="font-semibold flex items-center gap-2">
                                <FileText className="h-4 w-4" />
                                Evidence
                              </h4>
                              <div className="space-y-2">
                                {opp.evidence.map((ev, idx) => (
                                  <div key={idx} className="rounded bg-background p-2 text-sm">
                                    <Badge variant="outline" className="mb-1">
                                      {ev.source}
                                    </Badge>
                                    {ev.date && (
                                      <span className="ml-2 text-xs text-muted-foreground">{ev.date}</span>
                                    )}
                                    <p className="mt-1 text-muted-foreground">{ev.text}</p>
                                  </div>
                                ))}
                              </div>
                            </div>

                            {/* Documentation Requirements */}
                            <div className="space-y-2">
                              <h4 className="font-semibold flex items-center gap-2">
                                <AlertCircle className="h-4 w-4" />
                                Documentation Requirements
                              </h4>
                              <ul className="space-y-1">
                                {opp.documentationNeeded.map((doc, idx) => (
                                  <li key={idx} className="flex items-start gap-2 text-sm">
                                    <Clock className="h-4 w-4 text-yellow-600 mt-0.5 shrink-0" />
                                    {doc}
                                  </li>
                                ))}
                              </ul>
                            </div>

                            {/* Code Information */}
                            <div className="space-y-2">
                              <h4 className="font-semibold flex items-center gap-2">
                                <Target className="h-4 w-4" />
                                Code Information
                              </h4>
                              <div className="space-y-2 text-sm">
                                {opp.currentIcd10 && (
                                  <div>
                                    <span className="text-muted-foreground">Current Code:</span>
                                    <code className="ml-2 rounded bg-red-100 px-2 py-0.5 dark:bg-red-900">
                                      {opp.currentIcd10}
                                    </code>
                                  </div>
                                )}
                                <div>
                                  <span className="text-muted-foreground">Recommended:</span>
                                  <code className="ml-2 rounded bg-green-100 px-2 py-0.5 dark:bg-green-900">
                                    {opp.recommendedIcd10}
                                  </code>
                                </div>
                                <div className="mt-4 rounded bg-background p-2">
                                  <p className="font-medium text-xs text-muted-foreground mb-1">Coder Notes:</p>
                                  <p className="text-sm">{opp.coderNotes}</p>
                                </div>
                              </div>
                            </div>
                          </div>
                          <div className="mt-4 flex gap-2 justify-end">
                            <Button variant="outline" size="sm">
                              Create CDI Query
                            </Button>
                            <Button variant="outline" size="sm">
                              View Patient Record
                            </Button>
                            <Button size="sm">
                              <CheckCircle className="mr-2 h-4 w-4" />
                              Capture HCC
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                ))}
              </TableBody>
            </Table>
          </div>

          {sortedOpportunities.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Target className="h-12 w-12 text-muted-foreground/50" />
              <h3 className="mt-4 text-lg font-semibold">No HCC gaps found</h3>
              <p className="text-sm text-muted-foreground">
                Try adjusting your filters or search criteria
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
