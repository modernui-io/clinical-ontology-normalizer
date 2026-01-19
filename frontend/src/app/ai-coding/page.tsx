"use client";

import { useState, useCallback } from "react";
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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  Play,
  AlertTriangle,
  Lightbulb,
  Download,
  Copy,
  Zap,
  Activity,
  BarChart3,
  FileCheck,
  Send,
  Loader2,
  Sparkles,
} from "lucide-react";
import {
  suggestCodes,
  validateCodes,
  calculateHCC,
  getCodingRules,
  type AICodingSuggestResponse,
  type AICodingValidateResponse,
  type AICodingHCCResponse,
  type AICodingRulesResponse,
  type AICodeSuggestion,
  type AICodingOpportunity,
  type AIValidationIssue,
} from "@/lib/api";

// ============================================================================
// Helper Functions
// ============================================================================

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
      return "text-green-600";
    case "medium":
      return "text-yellow-600";
    case "low":
      return "text-red-600";
    default:
      return "text-gray-600";
  }
};

const getConfidenceBg = (confidence: string): string => {
  switch (confidence) {
    case "high":
      return "bg-green-100 dark:bg-green-900";
    case "medium":
      return "bg-yellow-100 dark:bg-yellow-900";
    case "low":
      return "bg-red-100 dark:bg-red-900";
    default:
      return "bg-gray-100 dark:bg-gray-900";
  }
};

const getSeverityIcon = (severity: string) => {
  switch (severity) {
    case "error":
      return <XCircle className="h-4 w-4 text-red-600" />;
    case "warning":
      return <AlertTriangle className="h-4 w-4 text-yellow-600" />;
    case "info":
      return <AlertCircle className="h-4 w-4 text-blue-600" />;
    default:
      return <AlertCircle className="h-4 w-4 text-gray-600" />;
  }
};

const getPriorityColor = (priority: string): string => {
  switch (priority) {
    case "high":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    case "medium":
      return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200";
    case "low":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

// Sample clinical note for demo
const SAMPLE_CLINICAL_NOTE = `Chief Complaint: Follow-up for diabetes management

History of Present Illness:
65-year-old male with history of Type 2 diabetes mellitus with diabetic nephropathy,
hypertension, and COPD presents for routine follow-up. Patient reports increased
shortness of breath over the past 2 weeks. Denies chest pain. Blood glucose control
has been suboptimal with recent A1c of 8.2%.

Past Medical History:
- Type 2 diabetes mellitus with diabetic nephropathy
- Hypertension
- COPD - GOLD Stage 2
- Hyperlipidemia
- Chronic kidney disease stage 3 (eGFR 42)

Current Medications:
- Metformin 1000mg BID
- Lisinopril 20mg daily
- Amlodipine 10mg daily
- Tiotropium inhaler daily
- Atorvastatin 40mg daily

Vitals:
BP: 142/88, HR: 78, RR: 18, O2 Sat: 94% on RA

Physical Exam:
General: Alert, oriented, mild respiratory distress
Lungs: Decreased breath sounds bilateral bases, scattered wheezes
Heart: Regular rate, no murmurs
Extremities: 1+ edema bilateral lower extremities

Labs:
- HbA1c: 8.2%
- Creatinine: 1.8 (baseline 1.6)
- eGFR: 42 mL/min
- BNP: 350 pg/mL

Assessment and Plan:
1. Type 2 diabetes with diabetic nephropathy - suboptimal control
   - Increase metformin monitoring, consider adding GLP-1 agonist
   - Continue ACE inhibitor for renal protection

2. COPD exacerbation - mild
   - Start prednisone taper
   - Continue tiotropium
   - Chest x-ray ordered

3. CKD Stage 3 - stable
   - Monitor creatinine
   - Nephrology referral if worsening

4. Hypertension - not at goal
   - Continue current regimen
   - Recheck in 2 weeks

Total time spent: 35 minutes

Follow-up in 4 weeks.`;

export default function AICodingPage() {
  const [activeTab, setActiveTab] = useState("suggest");
  const [clinicalText, setClinicalText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Results state
  const [suggestResult, setSuggestResult] = useState<AICodingSuggestResponse | null>(null);
  const [validateResult, setValidateResult] = useState<AICodingValidateResponse | null>(null);
  const [hccResult, setHccResult] = useState<AICodingHCCResponse | null>(null);
  const [rulesResult, setRulesResult] = useState<AICodingRulesResponse | null>(null);

  // Code validation inputs
  const [diagnosisCodes, setDiagnosisCodes] = useState("");
  const [procedureCodes, setProcedureCodes] = useState("");

  // HCC inputs
  const [hccCodes, setHccCodes] = useState("");

  // Expanded cards
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());

  // Selected codes for worksheet
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set());

  const toggleExpanded = (id: string) => {
    const newExpanded = new Set(expandedCards);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedCards(newExpanded);
  };

  const toggleCodeSelection = (code: string) => {
    const newSelected = new Set(selectedCodes);
    if (newSelected.has(code)) {
      newSelected.delete(code);
    } else {
      newSelected.add(code);
    }
    setSelectedCodes(newSelected);
  };

  const loadSampleNote = () => {
    setClinicalText(SAMPLE_CLINICAL_NOTE);
  };

  const handleSuggestCodes = async () => {
    if (!clinicalText.trim()) {
      setError("Please enter clinical text to analyze");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await suggestCodes({
        clinical_text: clinicalText,
        max_diagnosis_codes: 15,
        max_procedure_codes: 10,
        include_hcc: true,
      });
      setSuggestResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to analyze clinical text");
    } finally {
      setIsLoading(false);
    }
  };

  const handleValidateCodes = async () => {
    if (!diagnosisCodes.trim() && !procedureCodes.trim()) {
      setError("Please enter at least one diagnosis or procedure code");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const dxCodes = diagnosisCodes.split(/[,\s]+/).filter(Boolean);
      const procCodes = procedureCodes.split(/[,\s]+/).filter(Boolean);

      const result = await validateCodes({
        diagnosis_codes: dxCodes,
        procedure_codes: procCodes,
      });
      setValidateResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to validate codes");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCalculateHCC = async () => {
    if (!hccCodes.trim()) {
      setError("Please enter ICD-10 codes for HCC calculation");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const codes = hccCodes.split(/[,\s]+/).filter(Boolean);
      const result = await calculateHCC({
        icd10_codes: codes,
        clinical_text: clinicalText || undefined,
      });
      setHccResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to calculate HCC risk");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGetRules = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await getCodingRules();
      setRulesResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch coding rules");
    } finally {
      setIsLoading(false);
    }
  };

  const copySelectedCodes = () => {
    const codes = Array.from(selectedCodes).join(", ");
    navigator.clipboard.writeText(codes);
  };

  const exportWorksheet = () => {
    if (!suggestResult) return;

    const selectedDx = suggestResult.diagnosis_codes.filter(c => selectedCodes.has(c.code));
    const selectedProc = suggestResult.procedure_codes.filter(c => selectedCodes.has(c.code));

    const worksheet = {
      timestamp: new Date().toISOString(),
      diagnosis_codes: selectedDx.map(c => ({
        code: c.code,
        description: c.description,
        confidence: c.confidence,
        hcc_code: c.hcc_code,
        raf_value: c.raf_value,
      })),
      procedure_codes: selectedProc.map(c => ({
        code: c.code,
        description: c.description,
        confidence: c.confidence,
      })),
      em_code: suggestResult.em_code ? {
        code: suggestResult.em_code.code,
        description: suggestResult.em_code.description,
        rationale: suggestResult.em_rationale,
      } : null,
    };

    const blob = new Blob([JSON.stringify(worksheet, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `coding-worksheet-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
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
            <div className="flex items-center gap-2">
              <Sparkles className="h-6 w-6 text-purple-600" />
              <h1 className="text-2xl font-bold tracking-tight">AI Auto-Coding</h1>
            </div>
            <p className="text-muted-foreground">
              Intelligent code suggestions powered by TF-IDF text analysis
            </p>
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <Card className="border-red-200 bg-red-50 dark:bg-red-950">
          <CardContent className="flex items-center gap-2 pt-6">
            <XCircle className="h-5 w-5 text-red-600" />
            <span className="text-red-600">{error}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setError(null)}
              className="ml-auto"
            >
              Dismiss
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4 lg:w-auto">
          <TabsTrigger value="suggest" className="gap-2">
            <Zap className="h-4 w-4" />
            Suggest Codes
          </TabsTrigger>
          <TabsTrigger value="validate" className="gap-2">
            <FileCheck className="h-4 w-4" />
            Validate
          </TabsTrigger>
          <TabsTrigger value="hcc" className="gap-2">
            <DollarSign className="h-4 w-4" />
            HCC Analysis
          </TabsTrigger>
          <TabsTrigger value="rules" className="gap-2">
            <BookOpen className="h-4 w-4" />
            Coding Rules
          </TabsTrigger>
        </TabsList>

        {/* Suggest Codes Tab */}
        <TabsContent value="suggest" className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Input Panel */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  Clinical Documentation
                </CardTitle>
                <CardDescription>
                  Enter or paste clinical text to analyze for code suggestions
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={loadSampleNote}>
                    <FileText className="mr-2 h-4 w-4" />
                    Load Sample Note
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setClinicalText("")}
                  >
                    Clear
                  </Button>
                </div>
                <Textarea
                  placeholder="Paste clinical documentation here..."
                  value={clinicalText}
                  onChange={(e) => setClinicalText(e.target.value)}
                  className="min-h-[400px] font-mono text-sm"
                />
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    {clinicalText.length} characters
                  </span>
                  <Button
                    onClick={handleSuggestCodes}
                    disabled={isLoading || !clinicalText.trim()}
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Analyzing...
                      </>
                    ) : (
                      <>
                        <Play className="mr-2 h-4 w-4" />
                        Analyze & Suggest Codes
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Results Summary Panel */}
            {suggestResult && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5" />
                    Analysis Summary
                  </CardTitle>
                  <CardDescription>
                    Processed in {suggestResult.processing_time_ms.toFixed(0)}ms
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Stats Grid */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="rounded-lg border p-3">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Stethoscope className="h-4 w-4" />
                        Diagnosis Codes
                      </div>
                      <div className="text-2xl font-bold">
                        {suggestResult.total_diagnosis_suggestions}
                      </div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Code className="h-4 w-4" />
                        Procedure Codes
                      </div>
                      <div className="text-2xl font-bold">
                        {suggestResult.total_procedure_suggestions}
                      </div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <CheckCircle className="h-4 w-4" />
                        High Confidence
                      </div>
                      <div className="text-2xl font-bold text-green-600">
                        {suggestResult.high_confidence_count}
                      </div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Lightbulb className="h-4 w-4" />
                        Opportunities
                      </div>
                      <div className="text-2xl font-bold text-purple-600">
                        {suggestResult.coding_opportunities.length}
                      </div>
                    </div>
                  </div>

                  {/* E/M Code Suggestion */}
                  {suggestResult.em_code && (
                    <div className="rounded-lg border p-4 bg-purple-50 dark:bg-purple-950">
                      <div className="flex items-center gap-2 mb-2">
                        <Activity className="h-5 w-5 text-purple-600" />
                        <span className="font-semibold">E/M Level Recommendation</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <code className="rounded bg-purple-200 dark:bg-purple-800 px-3 py-1 text-lg font-mono font-bold">
                          {suggestResult.em_code.code}
                        </code>
                        <span>{suggestResult.em_code.description}</span>
                      </div>
                      {suggestResult.em_rationale && (
                        <p className="mt-2 text-sm text-muted-foreground">
                          {suggestResult.em_rationale}
                        </p>
                      )}
                    </div>
                  )}

                  {/* HCC Summary */}
                  {suggestResult.hcc_analysis && (
                    <div className="rounded-lg border p-4 bg-green-50 dark:bg-green-950">
                      <div className="flex items-center gap-2 mb-2">
                        <DollarSign className="h-5 w-5 text-green-600" />
                        <span className="font-semibold">HCC Risk Analysis</span>
                      </div>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="text-muted-foreground">Total RAF Score:</span>
                          <span className="ml-2 font-bold">
                            {suggestResult.hcc_analysis.total_raf_score.toFixed(3)}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Est. Annual Revenue:</span>
                          <span className="ml-2 font-bold text-green-600">
                            {formatCurrency(suggestResult.hcc_analysis.estimated_annual_revenue)}
                          </span>
                        </div>
                      </div>
                      {suggestResult.hcc_analysis.hcc_codes.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {suggestResult.hcc_analysis.hcc_codes.map((hcc) => (
                            <Badge key={hcc} variant="secondary" className="font-mono">
                              {hcc}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Selected Codes Actions */}
                  {selectedCodes.size > 0 && (
                    <div className="flex items-center gap-2 pt-4 border-t">
                      <Badge variant="outline">{selectedCodes.size} codes selected</Badge>
                      <Button variant="outline" size="sm" onClick={copySelectedCodes}>
                        <Copy className="mr-2 h-4 w-4" />
                        Copy
                      </Button>
                      <Button variant="outline" size="sm" onClick={exportWorksheet}>
                        <Download className="mr-2 h-4 w-4" />
                        Export Worksheet
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Code Suggestions List */}
          {suggestResult && (
            <div className="space-y-6">
              {/* Diagnosis Codes */}
              {suggestResult.diagnosis_codes.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Stethoscope className="h-5 w-5 text-blue-600" />
                      ICD-10 Diagnosis Codes
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-12">Select</TableHead>
                          <TableHead>Code</TableHead>
                          <TableHead>Description</TableHead>
                          <TableHead>Category</TableHead>
                          <TableHead>Confidence</TableHead>
                          <TableHead>HCC</TableHead>
                          <TableHead>RAF</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {suggestResult.diagnosis_codes.map((suggestion) => (
                          <TableRow key={suggestion.code}>
                            <TableCell>
                              <input
                                type="checkbox"
                                checked={selectedCodes.has(suggestion.code)}
                                onChange={() => toggleCodeSelection(suggestion.code)}
                                className="h-4 w-4 rounded border-gray-300"
                              />
                            </TableCell>
                            <TableCell>
                              <code className="rounded bg-blue-100 dark:bg-blue-900 px-2 py-1 font-mono font-bold">
                                {suggestion.code}
                              </code>
                            </TableCell>
                            <TableCell className="max-w-xs truncate">
                              {suggestion.description}
                            </TableCell>
                            <TableCell>
                              <Badge variant="outline">{suggestion.category}</Badge>
                            </TableCell>
                            <TableCell>
                              <Badge className={getConfidenceBg(suggestion.confidence)}>
                                {Math.round(suggestion.confidence_score * 100)}%
                              </Badge>
                            </TableCell>
                            <TableCell>
                              {suggestion.hcc_code ? (
                                <code className="rounded bg-green-100 dark:bg-green-900 px-2 py-0.5 font-mono text-xs">
                                  {suggestion.hcc_code}
                                </code>
                              ) : (
                                <span className="text-muted-foreground">-</span>
                              )}
                            </TableCell>
                            <TableCell>
                              {suggestion.raf_value > 0 ? (
                                <span className="font-semibold text-green-600">
                                  {suggestion.raf_value.toFixed(3)}
                                </span>
                              ) : (
                                <span className="text-muted-foreground">-</span>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              )}

              {/* Procedure Codes */}
              {suggestResult.procedure_codes.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Code className="h-5 w-5 text-purple-600" />
                      CPT Procedure Codes
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-12">Select</TableHead>
                          <TableHead>Code</TableHead>
                          <TableHead>Description</TableHead>
                          <TableHead>Category</TableHead>
                          <TableHead>Confidence</TableHead>
                          <TableHead>Match Reason</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {suggestResult.procedure_codes.map((suggestion) => (
                          <TableRow key={suggestion.code}>
                            <TableCell>
                              <input
                                type="checkbox"
                                checked={selectedCodes.has(suggestion.code)}
                                onChange={() => toggleCodeSelection(suggestion.code)}
                                className="h-4 w-4 rounded border-gray-300"
                              />
                            </TableCell>
                            <TableCell>
                              <code className="rounded bg-purple-100 dark:bg-purple-900 px-2 py-1 font-mono font-bold">
                                {suggestion.code}
                              </code>
                            </TableCell>
                            <TableCell className="max-w-xs truncate">
                              {suggestion.description}
                            </TableCell>
                            <TableCell>
                              <Badge variant="outline">{suggestion.category}</Badge>
                            </TableCell>
                            <TableCell>
                              <Badge className={getConfidenceBg(suggestion.confidence)}>
                                {Math.round(suggestion.confidence_score * 100)}%
                              </Badge>
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {suggestion.match_reason}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              )}

              {/* Coding Opportunities */}
              {suggestResult.coding_opportunities.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Lightbulb className="h-5 w-5 text-yellow-600" />
                      Coding Opportunities
                    </CardTitle>
                    <CardDescription>
                      Identified opportunities to improve coding accuracy and capture
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {suggestResult.coding_opportunities.map((opp, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-3 rounded-lg border p-4"
                        >
                          <Badge className={getPriorityColor(opp.priority)}>
                            {opp.priority}
                          </Badge>
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <Badge variant="outline">{opp.opportunity_type}</Badge>
                              {opp.current_code && (
                                <code className="rounded bg-muted px-2 py-0.5 font-mono text-sm">
                                  {opp.current_code}
                                </code>
                              )}
                            </div>
                            <p className="mt-1 text-sm">{opp.description}</p>
                            <p className="mt-1 text-sm text-muted-foreground">
                              Impact: {opp.impact}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </TabsContent>

        {/* Validate Tab */}
        <TabsContent value="validate" className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileCheck className="h-5 w-5" />
                  Code Validation
                </CardTitle>
                <CardDescription>
                  Check codes for errors, duplicates, and bundling issues
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="dx-codes">ICD-10 Diagnosis Codes</Label>
                  <Input
                    id="dx-codes"
                    placeholder="E11.21, I10, J44.9"
                    value={diagnosisCodes}
                    onChange={(e) => setDiagnosisCodes(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Separate codes with commas or spaces
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="proc-codes">CPT Procedure Codes</Label>
                  <Input
                    id="proc-codes"
                    placeholder="99214, 93000, 71046"
                    value={procedureCodes}
                    onChange={(e) => setProcedureCodes(e.target.value)}
                  />
                </div>
                <Button onClick={handleValidateCodes} disabled={isLoading}>
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Validating...
                    </>
                  ) : (
                    <>
                      <FileCheck className="mr-2 h-4 w-4" />
                      Validate Codes
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {validateResult && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    {validateResult.is_valid ? (
                      <CheckCircle className="h-5 w-5 text-green-600" />
                    ) : (
                      <XCircle className="h-5 w-5 text-red-600" />
                    )}
                    Validation Result
                  </CardTitle>
                  <CardDescription>{validateResult.summary}</CardDescription>
                </CardHeader>
                <CardContent>
                  {validateResult.issues.length > 0 ? (
                    <div className="space-y-3">
                      {validateResult.issues.map((issue, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-3 rounded-lg border p-3"
                        >
                          {getSeverityIcon(issue.severity)}
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <Badge variant="outline">{issue.issue_type}</Badge>
                              {issue.codes_involved.map((code) => (
                                <code
                                  key={code}
                                  className="rounded bg-muted px-2 py-0.5 font-mono text-sm"
                                >
                                  {code}
                                </code>
                              ))}
                            </div>
                            <p className="mt-1 text-sm">{issue.message}</p>
                            {issue.suggestion && (
                              <p className="mt-1 text-sm text-muted-foreground">
                                Suggestion: {issue.suggestion}
                              </p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-8 text-center">
                      <CheckCircle className="h-12 w-12 text-green-600" />
                      <h3 className="mt-4 text-lg font-semibold">All codes validated</h3>
                      <p className="text-sm text-muted-foreground">
                        No issues found with the provided codes
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>

        {/* HCC Tab */}
        <TabsContent value="hcc" className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <DollarSign className="h-5 w-5" />
                  HCC Risk Calculator
                </CardTitle>
                <CardDescription>
                  Calculate HCC risk scores and estimated revenue from ICD-10 codes
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="hcc-codes">ICD-10 Diagnosis Codes</Label>
                  <Input
                    id="hcc-codes"
                    placeholder="E11.21, I50.22, N18.4, J44.9"
                    value={hccCodes}
                    onChange={(e) => setHccCodes(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Enter ICD-10 codes to calculate HCC risk adjustment
                  </p>
                </div>
                <Button onClick={handleCalculateHCC} disabled={isLoading}>
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Calculating...
                    </>
                  ) : (
                    <>
                      <Activity className="mr-2 h-4 w-4" />
                      Calculate HCC Risk
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {hccResult && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5" />
                    HCC Analysis Result
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="rounded-lg border p-4 bg-green-50 dark:bg-green-950">
                      <div className="text-sm text-muted-foreground">Total RAF Score</div>
                      <div className="text-3xl font-bold text-green-600">
                        {hccResult.total_raf_score.toFixed(3)}
                      </div>
                    </div>
                    <div className="rounded-lg border p-4 bg-blue-50 dark:bg-blue-950">
                      <div className="text-sm text-muted-foreground">Est. Annual Revenue</div>
                      <div className="text-3xl font-bold text-blue-600">
                        {formatCurrency(hccResult.estimated_annual_revenue)}
                      </div>
                    </div>
                  </div>

                  {hccResult.hcc_details.length > 0 && (
                    <div>
                      <h4 className="font-semibold mb-2">HCC Mappings</h4>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>ICD-10</TableHead>
                            <TableHead>HCC Code</TableHead>
                            <TableHead>RAF Value</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {hccResult.hcc_details.map((detail, idx) => (
                            <TableRow key={idx}>
                              <TableCell>
                                <div>
                                  <code className="font-mono font-bold">{detail.icd10_code}</code>
                                  <p className="text-xs text-muted-foreground truncate max-w-xs">
                                    {detail.icd10_description}
                                  </p>
                                </div>
                              </TableCell>
                              <TableCell>
                                <Badge variant="secondary" className="font-mono">
                                  {detail.hcc_code}
                                </Badge>
                              </TableCell>
                              <TableCell className="font-semibold text-green-600">
                                {detail.raf_value.toFixed(3)}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}

                  {hccResult.opportunities.length > 0 && (
                    <div>
                      <h4 className="font-semibold mb-2">Additional Opportunities</h4>
                      <div className="space-y-2">
                        {hccResult.opportunities.map((opp, idx) => (
                          <div key={idx} className="rounded-lg border p-3 text-sm">
                            <Badge className={getPriorityColor(opp.priority)}>
                              {opp.priority}
                            </Badge>
                            <p className="mt-1">{opp.description}</p>
                            <p className="text-muted-foreground">{opp.impact}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>

        {/* Rules Tab */}
        <TabsContent value="rules" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <BookOpen className="h-5 w-5" />
                    Coding Rules & Guidelines
                  </CardTitle>
                  <CardDescription>
                    Reference coding rules, sequencing guidelines, and bundling edits
                  </CardDescription>
                </div>
                <Button onClick={handleGetRules} disabled={isLoading}>
                  {isLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <>
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Load Rules
                    </>
                  )}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {rulesResult ? (
                <div className="space-y-4">
                  {rulesResult.rules.map((rule) => (
                    <div key={rule.rule_id} className="rounded-lg border p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline">{rule.category}</Badge>
                            <code className="rounded bg-muted px-2 py-0.5 font-mono text-xs">
                              {rule.rule_id}
                            </code>
                          </div>
                          <h4 className="mt-2 font-semibold">{rule.title}</h4>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {rule.description}
                          </p>
                        </div>
                        {rule.source && (
                          <Badge variant="secondary">{rule.source}</Badge>
                        )}
                      </div>
                      {rule.codes_affected.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-1">
                          <span className="text-xs text-muted-foreground">Codes:</span>
                          {rule.codes_affected.map((code) => (
                            <code
                              key={code}
                              className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs"
                            >
                              {code}
                            </code>
                          ))}
                        </div>
                      )}
                      {rule.examples.length > 0 && (
                        <div className="mt-3">
                          <span className="text-xs text-muted-foreground">Examples:</span>
                          <ul className="mt-1 list-inside list-disc text-sm">
                            {rule.examples.map((ex, idx) => (
                              <li key={idx}>{ex}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <BookOpen className="h-12 w-12 text-muted-foreground/50" />
                  <h3 className="mt-4 text-lg font-semibold">No rules loaded</h3>
                  <p className="text-sm text-muted-foreground">
                    Click &quot;Load Rules&quot; to fetch coding guidelines
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
