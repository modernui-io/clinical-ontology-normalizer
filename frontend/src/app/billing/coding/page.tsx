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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  FileText,
  Search,
  ArrowLeft,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  DollarSign,
  Code,
  Stethoscope,
  ChevronDown,
  ChevronUp,
  ThumbsUp,
  ThumbsDown,
  BookOpen,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";

// Mock data interfaces
interface CERCitation {
  claim: string;
  evidence: string[];
  reasoning: string;
  strength: "HIGH" | "MEDIUM" | "LOW";
}

interface DocumentationRequirement {
  element: string;
  present: boolean | null;
  notes: string;
}

interface CodingSuggestion {
  id: string;
  type: "icd10" | "cpt";
  code: string;
  description: string;
  category: string;
  confidence: number;
  status: "pending" | "accepted" | "rejected" | "modified";

  // Patient/encounter info
  patientId: string;
  patientName: string;
  encounterId: string;
  encounterDate: string;

  // CER citation
  cerCitation: CERCitation;

  // For ICD-10
  currentCode?: string;
  hccImpact?: {
    hccCode: string;
    rafValue: number;
    estimatedRevenue: number;
  };

  // For CPT
  workRvu?: number;
  typicalTime?: number;

  // Documentation
  documentationChecklist: DocumentationRequirement[];

  // Alternatives
  alternativeCodes: {
    code: string;
    description: string;
    reason: string;
  }[];

  // Notes
  codingNotes: string[];

  createdAt: string;
}

// Mock data
const mockCodingSuggestions: CodingSuggestion[] = [
  {
    id: "1",
    type: "icd10",
    code: "E11.22",
    description: "Type 2 diabetes mellitus with diabetic chronic kidney disease",
    category: "Endocrine, nutritional and metabolic diseases",
    confidence: 0.92,
    status: "pending",
    patientId: "P001",
    patientName: "John Smith",
    encounterId: "E2001",
    encounterDate: "2026-01-15",
    cerCitation: {
      claim: "E11.22 is appropriate based on documented diabetic nephropathy with CKD",
      evidence: [
        "Problem list includes 'Type 2 diabetes mellitus'",
        "Nephrology note states 'diabetic nephropathy'",
        "Lab: eGFR 42 mL/min consistent with CKD Stage 3",
        "Urinalysis shows proteinuria (A/C ratio 85 mg/g)",
      ],
      reasoning: "Documentation clearly establishes causal relationship between diabetes and chronic kidney disease. Per ICD-10-CM Guidelines I.A.13, when diabetes is documented with associated conditions, the combination code should be assigned. E11.22 captures both the diabetes type and the chronic kidney disease complication.",
      strength: "HIGH",
    },
    currentCode: "E11.9",
    hccImpact: {
      hccCode: "HCC37",
      rafValue: 0.302,
      estimatedRevenue: 4354,
    },
    documentationChecklist: [
      { element: "Type of diabetes specified", present: true, notes: "Type 2 documented in problem list" },
      { element: "Chronic complication documented", present: true, notes: "Diabetic nephropathy noted" },
      { element: "Causal relationship stated", present: true, notes: "'Diabetic nephropathy' implies causation" },
      { element: "CKD stage documented", present: true, notes: "Stage 3 per nephrology" },
    ],
    alternativeCodes: [
      { code: "E11.65", description: "Type 2 DM with hyperglycemia", reason: "If hyperglycemia is present" },
      { code: "E11.21", description: "Type 2 DM with diabetic nephropathy", reason: "Without CKD staging" },
    ],
    codingNotes: [
      "Combination code captures both conditions - do not code separately",
      "Use additional code for CKD stage (N18.3) if not captured in E11.22",
      "Consider HCC capture for risk adjustment",
    ],
    createdAt: "2026-01-19T10:30:00Z",
  },
  {
    id: "2",
    type: "cpt",
    code: "99215",
    description: "Office/outpatient visit, established patient, high MDM or 40-54 min",
    category: "Evaluation and Management",
    confidence: 0.88,
    status: "pending",
    patientId: "P002",
    patientName: "Jane Doe",
    encounterId: "E2002",
    encounterDate: "2026-01-16",
    cerCitation: {
      claim: "99215 is supported by documented time and high complexity MDM",
      evidence: [
        "Total time documented: 47 minutes",
        "4 chronic conditions actively managed",
        "Prescription drug management with careful monitoring (insulin adjustment)",
        "Discussion of risks and benefits of treatment options",
      ],
      reasoning: "Documentation supports high complexity MDM based on: (1) Multiple chronic conditions with mild exacerbation, (2) Prescription drug management requiring intensive monitoring. Time of 47 minutes alone meets 99215 threshold of 40-54 minutes. Either time or MDM supports this level.",
      strength: "HIGH",
    },
    workRvu: 2.80,
    typicalTime: 47,
    documentationChecklist: [
      { element: "Chief complaint documented", present: true, notes: "Multiple follow-up concerns" },
      { element: "Total time documented", present: true, notes: "47 minutes specified" },
      { element: "MDM complexity documented", present: true, notes: "High complexity MDM elements met" },
      { element: "Chronic conditions documented", present: true, notes: "4 conditions in assessment" },
    ],
    alternativeCodes: [
      { code: "99214", description: "Established patient, moderate MDM", reason: "If time was 30-39 min" },
      { code: "99417", description: "Prolonged service", reason: "If time exceeded 54 minutes (add-on code)" },
    ],
    codingNotes: [
      "For E/M coding, document either time OR MDM complexity (whichever supports higher level)",
      "Time-based coding requires documentation of total time spent on encounter date",
      "RVU increase from 99214 to 99215: 0.88 additional work RVU",
    ],
    createdAt: "2026-01-19T11:15:00Z",
  },
  {
    id: "3",
    type: "icd10",
    code: "I50.22",
    description: "Chronic systolic (congestive) heart failure",
    category: "Diseases of the circulatory system",
    confidence: 0.95,
    status: "pending",
    patientId: "P003",
    patientName: "Mary Johnson",
    encounterId: "E2003",
    encounterDate: "2026-01-12",
    cerCitation: {
      claim: "I50.22 accurately captures the documented chronic systolic heart failure",
      evidence: [
        "Echo report: EF 35%",
        "Note states 'chronic systolic heart failure'",
        "Patient on guideline-directed medical therapy (lisinopril, carvedilol, spironolactone)",
        "BNP elevated at 450 pg/mL",
      ],
      reasoning: "Documentation explicitly states 'chronic systolic heart failure' with supporting evidence of reduced EF (35%) and elevated BNP. Per ICD-10-CM Guidelines I.C.9.a, heart failure codes should specify type (systolic, diastolic, combined) and acuity (acute, chronic, acute-on-chronic).",
      strength: "HIGH",
    },
    hccImpact: {
      hccCode: "HCC85",
      rafValue: 0.323,
      estimatedRevenue: 4656,
    },
    documentationChecklist: [
      { element: "Heart failure type specified", present: true, notes: "Systolic explicitly stated" },
      { element: "Acuity documented", present: true, notes: "Chronic specified" },
      { element: "EF documented", present: true, notes: "35% per echo" },
      { element: "Treatment documented", present: true, notes: "GDMT in medication list" },
    ],
    alternativeCodes: [
      { code: "I50.21", description: "Acute systolic heart failure", reason: "If acute decompensation" },
      { code: "I50.23", description: "Acute on chronic systolic HF", reason: "If exacerbation of chronic" },
    ],
    codingNotes: [
      "HFrEF (reduced ejection fraction) is coded as systolic heart failure",
      "EF <= 40% supports systolic heart failure diagnosis",
      "HCC85 capture provides significant risk adjustment value",
    ],
    createdAt: "2026-01-19T09:45:00Z",
  },
  {
    id: "4",
    type: "cpt",
    code: "99406",
    description: "Smoking and tobacco use cessation counseling visit; 3-10 min",
    category: "Medicine",
    confidence: 0.85,
    status: "pending",
    patientId: "P002",
    patientName: "Jane Doe",
    encounterId: "E2002",
    encounterDate: "2026-01-16",
    cerCitation: {
      claim: "99406 is appropriate for documented tobacco cessation counseling",
      evidence: [
        "Note states 'tobacco cessation counseling provided'",
        "Duration noted: 8 minutes",
        "Discussion of NRT options documented",
        "Patient declined Chantix due to prior side effects",
      ],
      reasoning: "Documentation supports tobacco cessation counseling of 3-10 minutes duration. 99406 is separately billable from E/M services when documented appropriately. Counseling must include advice to quit and strategies for cessation.",
      strength: "MEDIUM",
    },
    workRvu: 0.24,
    typicalTime: 7,
    documentationChecklist: [
      { element: "Tobacco use status documented", present: true, notes: "Active smoker, 1 ppd" },
      { element: "Counseling duration", present: true, notes: "8 minutes" },
      { element: "Cessation strategies discussed", present: true, notes: "NRT options reviewed" },
      { element: "Patient response documented", present: true, notes: "Considering NRT patch" },
    ],
    alternativeCodes: [
      { code: "99407", description: "Tobacco cessation >10 min", reason: "If counseling exceeded 10 minutes" },
    ],
    codingNotes: [
      "Can be billed in addition to E/M code on same date",
      "Requires documentation of specific counseling provided",
      "Often missed billing opportunity - check for counseling documentation",
    ],
    createdAt: "2026-01-19T11:20:00Z",
  },
  {
    id: "5",
    type: "icd10",
    code: "N18.4",
    description: "Chronic kidney disease, stage 4 (severe)",
    category: "Diseases of the genitourinary system",
    confidence: 0.90,
    status: "pending",
    patientId: "P004",
    patientName: "Robert Williams",
    encounterId: "E2004",
    encounterDate: "2026-01-11",
    cerCitation: {
      claim: "N18.4 provides required specificity for documented CKD Stage 4",
      evidence: [
        "eGFR: 22 mL/min (Stage 4 = 15-29)",
        "Nephrology consult states 'CKD Stage 4'",
        "Problem list includes CKD with unspecified code (N18.9)",
      ],
      reasoning: "Current code N18.9 (CKD, unspecified) lacks specificity. Lab values (eGFR 22) and nephrology documentation explicitly support Stage 4. Per ICD-10-CM Guidelines, the most specific code should be assigned. N18.4 is required for accurate HCC capture.",
      strength: "HIGH",
    },
    currentCode: "N18.9",
    hccImpact: {
      hccCode: "HCC327",
      rafValue: 0.237,
      estimatedRevenue: 3417,
    },
    documentationChecklist: [
      { element: "CKD stage documented", present: true, notes: "Stage 4 per nephrology" },
      { element: "eGFR supports staging", present: true, notes: "22 mL/min = Stage 4" },
      { element: "Etiology if known", present: null, notes: "Consider documenting cause" },
    ],
    alternativeCodes: [
      { code: "N18.5", description: "CKD Stage 5", reason: "If eGFR drops below 15" },
      { code: "N18.3", description: "CKD Stage 3", reason: "If eGFR 30-59 (not applicable here)" },
    ],
    codingNotes: [
      "Code specificity is required for accurate HCC capture",
      "CKD Stage 4 (N18.4) maps to HCC327 for risk adjustment",
      "Consider coding etiology (diabetic, hypertensive) if documented",
    ],
    createdAt: "2026-01-18T14:30:00Z",
  },
];

// Stats calculation
const calculateStats = (suggestions: CodingSuggestion[]) => {
  const icd10 = suggestions.filter((s) => s.type === "icd10");
  const cpt = suggestions.filter((s) => s.type === "cpt");
  const pending = suggestions.filter((s) => s.status === "pending");
  const accepted = suggestions.filter((s) => s.status === "accepted");

  const hccRevenue = icd10.reduce((sum, s) => sum + (s.hccImpact?.estimatedRevenue || 0), 0);
  const totalRvu = cpt.reduce((sum, s) => sum + (s.workRvu || 0), 0);
  const avgConfidence = suggestions.reduce((sum, s) => sum + s.confidence, 0) / suggestions.length;

  return {
    total: suggestions.length,
    icd10Count: icd10.length,
    cptCount: cpt.length,
    pendingCount: pending.length,
    acceptedCount: accepted.length,
    hccRevenue,
    totalRvu,
    avgConfidence,
  };
};

// Helper functions
const formatCurrency = (amount: number): string => {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
};

const getConfidenceColor = (confidence: number): string => {
  if (confidence >= 0.9) return "text-green-600";
  if (confidence >= 0.7) return "text-yellow-600";
  return "text-red-600";
};

const getConfidenceBg = (confidence: number): string => {
  if (confidence >= 0.9) return "bg-green-100 dark:bg-green-900";
  if (confidence >= 0.7) return "bg-yellow-100 dark:bg-yellow-900";
  return "bg-red-100 dark:bg-red-900";
};

const getStrengthColor = (strength: string): string => {
  switch (strength) {
    case "HIGH":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "MEDIUM":
      return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200";
    case "LOW":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case "accepted":
      return <CheckCircle className="h-4 w-4 text-green-600" />;
    case "rejected":
      return <XCircle className="h-4 w-4 text-red-600" />;
    case "modified":
      return <AlertCircle className="h-4 w-4 text-yellow-600" />;
    default:
      return <Clock className="h-4 w-4 text-blue-600" />;
  }
};

export default function CodingSuggestionsPage() {
  const [suggestions, setSuggestions] = useState<CodingSuggestion[]>(mockCodingSuggestions);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState<"all" | "icd10" | "cpt">("all");
  const [selectedStatus, setSelectedStatus] = useState<"all" | "pending" | "accepted" | "rejected">("all");
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());

  const stats = calculateStats(suggestions);

  // Filter suggestions
  const filteredSuggestions = suggestions.filter((s) => {
    const matchesSearch =
      searchQuery === "" ||
      s.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.patientName.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesType = selectedType === "all" || s.type === selectedType;
    const matchesStatus = selectedStatus === "all" || s.status === selectedStatus;

    return matchesSearch && matchesType && matchesStatus;
  });

  const toggleExpanded = (id: string) => {
    const newExpanded = new Set(expandedCards);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedCards(newExpanded);
  };

  const handleAccept = (id: string) => {
    setSuggestions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, status: "accepted" as const } : s))
    );
    const suggestion = suggestions.find((s) => s.id === id);
    toast.success(`Accepted ${suggestion?.code || "suggestion"}`);
  };

  const handleReject = (id: string) => {
    setSuggestions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, status: "rejected" as const } : s))
    );
    const suggestion = suggestions.find((s) => s.id === id);
    toast.info(`Rejected ${suggestion?.code || "suggestion"}`);
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
            <h1 className="text-2xl font-bold tracking-tight">Coding Suggestions</h1>
            <p className="text-muted-foreground">
              ICD-10 and CPT recommendations with Claim-Evidence-Reasoning citations
            </p>
          </div>
        </div>
        <Button variant="outline">
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh Suggestions
        </Button>
      </div>

      {/* Demo mode banner */}
      <div className="flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
        <AlertCircle className="h-4 w-4 shrink-0" />
        <span>
          <strong>Client-side demo mode</strong> — Showing built-in coding
          suggestions. Connect the backend for live data.
        </span>
      </div>

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="border-l-4 border-l-blue-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Suggestions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">
              {stats.icd10Count} ICD-10 | {stats.cptCount} CPT
            </p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-green-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">HCC Revenue Potential</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{formatCurrency(stats.hccRevenue)}</div>
            <p className="text-xs text-muted-foreground">From ICD-10 suggestions</p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-purple-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total RVU Impact</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">{stats.totalRvu.toFixed(2)}</div>
            <p className="text-xs text-muted-foreground">Work RVU from CPT suggestions</p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-yellow-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Avg. Confidence</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{Math.round(stats.avgConfidence * 100)}%</div>
            <Progress value={stats.avgConfidence * 100} className="mt-2 h-2" />
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-4">
            <div className="relative flex-1 min-w-64">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by code, description, or patient..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Tabs value={selectedType} onValueChange={(v) => setSelectedType(v as any)}>
              <TabsList>
                <TabsTrigger value="all">All</TabsTrigger>
                <TabsTrigger value="icd10">ICD-10</TabsTrigger>
                <TabsTrigger value="cpt">CPT</TabsTrigger>
              </TabsList>
            </Tabs>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value as any)}
              className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="all">All Status</option>
              <option value="pending">Pending</option>
              <option value="accepted">Accepted</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Suggestions List */}
      <div className="space-y-4">
        {filteredSuggestions.map((suggestion) => (
          <Card key={suggestion.id} className="overflow-hidden">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className={`rounded-lg p-2 ${suggestion.type === "icd10" ? "bg-blue-100 dark:bg-blue-900" : "bg-purple-100 dark:bg-purple-900"}`}>
                    {suggestion.type === "icd10" ? (
                      <Stethoscope className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                    ) : (
                      <Code className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant={suggestion.type === "icd10" ? "default" : "secondary"}>
                        {suggestion.type.toUpperCase()}
                      </Badge>
                      <code className="rounded bg-muted px-2 py-1 text-sm font-mono font-bold">
                        {suggestion.code}
                      </code>
                      {suggestion.currentCode && (
                        <>
                          <span className="text-muted-foreground">from</span>
                          <code className="rounded bg-red-100 dark:bg-red-900 px-2 py-1 text-sm font-mono">
                            {suggestion.currentCode}
                          </code>
                        </>
                      )}
                      <div className="flex items-center gap-1">
                        {getStatusIcon(suggestion.status)}
                        <span className="text-xs capitalize">{suggestion.status}</span>
                      </div>
                    </div>
                    <CardTitle className="mt-1 text-lg">{suggestion.description}</CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">
                      {suggestion.patientName} ({suggestion.patientId}) - {suggestion.encounterDate}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <div className={`rounded px-2 py-1 text-sm font-bold ${getConfidenceBg(suggestion.confidence)} ${getConfidenceColor(suggestion.confidence)}`}>
                    {Math.round(suggestion.confidence * 100)}% confidence
                  </div>
                  {suggestion.hccImpact && (
                    <p className="mt-1 text-lg font-bold text-green-600">
                      {formatCurrency(suggestion.hccImpact.estimatedRevenue)}
                    </p>
                  )}
                  {suggestion.workRvu && (
                    <p className="mt-1 text-sm font-medium text-purple-600">
                      RVU: {suggestion.workRvu.toFixed(2)}
                    </p>
                  )}
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              {/* CER Citation Summary */}
              <div className="rounded-lg border p-4 bg-muted/30">
                <div className="flex items-center gap-2 mb-2">
                  <BookOpen className="h-4 w-4" />
                  <span className="font-semibold">Claim-Evidence-Reasoning</span>
                  <Badge className={getStrengthColor(suggestion.cerCitation.strength)}>
                    {suggestion.cerCitation.strength} strength
                  </Badge>
                </div>
                <p className="text-sm font-medium">{suggestion.cerCitation.claim}</p>

                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-2 p-0 h-auto"
                  onClick={() => toggleExpanded(suggestion.id)}
                >
                  {expandedCards.has(suggestion.id) ? (
                    <>
                      <ChevronUp className="mr-1 h-4 w-4" />
                      Hide Details
                    </>
                  ) : (
                    <>
                      <ChevronDown className="mr-1 h-4 w-4" />
                      Show Evidence & Reasoning
                    </>
                  )}
                </Button>
              </div>

              {/* Expanded Details */}
              {expandedCards.has(suggestion.id) && (
                <div className="space-y-4 animate-in slide-in-from-top-2">
                  {/* Evidence */}
                  <div className="rounded-lg border p-4">
                    <h4 className="font-semibold mb-2 flex items-center gap-2">
                      <FileText className="h-4 w-4" />
                      Evidence
                    </h4>
                    <ul className="space-y-1">
                      {suggestion.cerCitation.evidence.map((ev, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-sm">
                          <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 shrink-0" />
                          {ev}
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Reasoning */}
                  <div className="rounded-lg border p-4">
                    <h4 className="font-semibold mb-2 flex items-center gap-2">
                      <AlertCircle className="h-4 w-4" />
                      Reasoning
                    </h4>
                    <p className="text-sm text-muted-foreground">{suggestion.cerCitation.reasoning}</p>
                  </div>

                  {/* Documentation Checklist */}
                  <div className="rounded-lg border p-4">
                    <h4 className="font-semibold mb-2">Documentation Checklist</h4>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {suggestion.documentationChecklist.map((item, idx) => (
                        <div key={idx} className="flex items-start gap-2 text-sm">
                          {item.present === true && <CheckCircle className="h-4 w-4 text-green-600 shrink-0" />}
                          {item.present === false && <XCircle className="h-4 w-4 text-red-600 shrink-0" />}
                          {item.present === null && <AlertCircle className="h-4 w-4 text-yellow-600 shrink-0" />}
                          <div>
                            <span className="font-medium">{item.element}</span>
                            {item.notes && <p className="text-xs text-muted-foreground">{item.notes}</p>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Alternative Codes */}
                  {suggestion.alternativeCodes.length > 0 && (
                    <div className="rounded-lg border p-4">
                      <h4 className="font-semibold mb-2">Alternative Codes to Consider</h4>
                      <div className="space-y-2">
                        {suggestion.alternativeCodes.map((alt, idx) => (
                          <div key={idx} className="flex items-start gap-2 text-sm">
                            <code className="rounded bg-muted px-2 py-0.5 font-mono">{alt.code}</code>
                            <span>{alt.description}</span>
                            <span className="text-muted-foreground">- {alt.reason}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Coding Notes */}
                  {suggestion.codingNotes.length > 0 && (
                    <div className="rounded-lg border p-4 bg-yellow-50 dark:bg-yellow-950">
                      <h4 className="font-semibold mb-2">Coding Notes</h4>
                      <ul className="space-y-1">
                        {suggestion.codingNotes.map((note, idx) => (
                          <li key={idx} className="text-sm flex items-start gap-2">
                            <span className="text-yellow-600">*</span>
                            {note}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* HCC Impact */}
                  {suggestion.hccImpact && (
                    <div className="rounded-lg border p-4 bg-green-50 dark:bg-green-950">
                      <h4 className="font-semibold mb-2 flex items-center gap-2">
                        <DollarSign className="h-4 w-4" />
                        HCC Impact
                      </h4>
                      <div className="grid gap-2 sm:grid-cols-3 text-sm">
                        <div>
                          <span className="text-muted-foreground">HCC Code:</span>
                          <span className="ml-2 font-mono font-bold">{suggestion.hccImpact.hccCode}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">RAF Value:</span>
                          <span className="ml-2 font-bold">{suggestion.hccImpact.rafValue.toFixed(3)}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Est. Revenue:</span>
                          <span className="ml-2 font-bold text-green-600">
                            {formatCurrency(suggestion.hccImpact.estimatedRevenue)}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Action Buttons */}
              {suggestion.status === "pending" && (
                <div className="flex items-center justify-end gap-2 pt-2 border-t">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleReject(suggestion.id)}
                  >
                    <ThumbsDown className="mr-2 h-4 w-4" />
                    Reject
                  </Button>
                  <Button size="sm" onClick={() => handleAccept(suggestion.id)}>
                    <ThumbsUp className="mr-2 h-4 w-4" />
                    Accept
                  </Button>
                </div>
              )}

              {suggestion.status === "accepted" && (
                <div className="flex items-center justify-end gap-2 pt-2 border-t">
                  <Badge variant="outline" className="bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300">
                    <CheckCircle className="mr-1 h-3 w-3" />
                    Accepted
                  </Badge>
                </div>
              )}

              {suggestion.status === "rejected" && (
                <div className="flex items-center justify-end gap-2 pt-2 border-t">
                  <Badge variant="outline" className="bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300">
                    <XCircle className="mr-1 h-3 w-3" />
                    Rejected
                  </Badge>
                </div>
              )}
            </CardContent>
          </Card>
        ))}

        {filteredSuggestions.length === 0 && (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12 text-center">
              <FileText className="h-12 w-12 text-muted-foreground/50" />
              <h3 className="mt-4 text-lg font-semibold">No coding suggestions found</h3>
              <p className="text-sm text-muted-foreground">
                Try adjusting your filters or search criteria
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
