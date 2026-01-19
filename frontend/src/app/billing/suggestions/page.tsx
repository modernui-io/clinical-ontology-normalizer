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
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  FileText,
  Search,
  ArrowLeft,
  CheckCircle,
  XCircle,
  AlertCircle,
  Code,
  Stethoscope,
  ChevronDown,
  ChevronUp,
  ThumbsUp,
  ThumbsDown,
  Sparkles,
  Loader2,
  Plus,
  Eye,
  ClipboardCopy,
  RotateCcw,
} from "lucide-react";

// Types
interface SuggestedCode {
  id: string;
  code: string;
  codeType: "CPT" | "ICD10";
  description: string;
  confidence: number;
  evidenceText: string;
  evidenceStart: number;
  evidenceEnd: number;
  rationale: string;
  category: string;
  workRvu: number;
  status: "pending" | "accepted" | "rejected";
}

interface AnalysisResult {
  requestId: string;
  textLength: number;
  suggestions: SuggestedCode[];
  totalConcepts: number;
  emLevel: string | null;
  processingTimeMs: number;
}

// Mock AI analysis function
const mockAnalyzeText = async (text: string): Promise<AnalysisResult> => {
  // Simulate API delay
  await new Promise((resolve) => setTimeout(resolve, 1500));

  const suggestions: SuggestedCode[] = [];

  // Analyze text for patterns and generate suggestions
  const textLower = text.toLowerCase();

  // Diabetes patterns
  if (textLower.includes("diabetes") || textLower.includes("dm ") || textLower.includes("a1c")) {
    if (textLower.includes("nephropathy") || textLower.includes("ckd") || textLower.includes("kidney")) {
      suggestions.push({
        id: "1",
        code: "E11.22",
        codeType: "ICD10",
        description: "Type 2 diabetes mellitus with diabetic chronic kidney disease",
        confidence: 0.92,
        evidenceText: "...diabetes mellitus with diabetic chronic kidney disease...",
        evidenceStart: textLower.indexOf("diabet"),
        evidenceEnd: textLower.indexOf("diabet") + 50,
        rationale: "Documentation mentions diabetes with kidney involvement. E11.22 captures the causal relationship between T2DM and CKD per ICD-10 guidelines.",
        category: "Endocrine, nutritional and metabolic diseases",
        workRvu: 0,
        status: "pending",
      });
    }
    if (textLower.includes("neuropathy") || textLower.includes("numbness") || textLower.includes("tingling")) {
      suggestions.push({
        id: "2",
        code: "E11.42",
        codeType: "ICD10",
        description: "Type 2 diabetes mellitus with diabetic polyneuropathy",
        confidence: 0.85,
        evidenceText: "...peripheral neuropathy symptoms...",
        evidenceStart: textLower.indexOf("neuro") > -1 ? textLower.indexOf("neuro") : 0,
        evidenceEnd: textLower.indexOf("neuro") > -1 ? textLower.indexOf("neuro") + 30 : 30,
        rationale: "Neuropathy symptoms documented in diabetic patient suggest diabetic polyneuropathy.",
        category: "Endocrine, nutritional and metabolic diseases",
        workRvu: 0,
        status: "pending",
      });
    }
  }

  // Heart failure patterns
  if (textLower.includes("heart failure") || textLower.includes("chf") || textLower.includes("ef ") || textLower.includes("ejection fraction")) {
    const efMatch = text.match(/ef\s*(?:of\s*)?(\d+)/i) || text.match(/ejection fraction[:\s]+(\d+)/i);
    const ef = efMatch ? parseInt(efMatch[1]) : null;

    if (ef && ef <= 40) {
      suggestions.push({
        id: "3",
        code: "I50.22",
        codeType: "ICD10",
        description: "Chronic systolic (congestive) heart failure",
        confidence: 0.95,
        evidenceText: `...ejection fraction ${ef}%...`,
        evidenceStart: textLower.indexOf("ef") > -1 ? textLower.indexOf("ef") : textLower.indexOf("heart"),
        evidenceEnd: textLower.indexOf("ef") > -1 ? textLower.indexOf("ef") + 20 : textLower.indexOf("heart") + 30,
        rationale: `EF of ${ef}% indicates systolic heart failure (HFrEF). I50.22 is appropriate for chronic systolic heart failure.`,
        category: "Diseases of the circulatory system",
        workRvu: 0,
        status: "pending",
      });
    } else if (textLower.includes("systolic")) {
      suggestions.push({
        id: "3",
        code: "I50.22",
        codeType: "ICD10",
        description: "Chronic systolic (congestive) heart failure",
        confidence: 0.88,
        evidenceText: "...chronic systolic heart failure...",
        evidenceStart: textLower.indexOf("heart failure"),
        evidenceEnd: textLower.indexOf("heart failure") + 30,
        rationale: "Systolic heart failure explicitly documented. I50.22 captures chronic systolic HF.",
        category: "Diseases of the circulatory system",
        workRvu: 0,
        status: "pending",
      });
    }
  }

  // CKD patterns
  if (textLower.includes("ckd") || textLower.includes("chronic kidney") || textLower.includes("egfr")) {
    const stageMatch = text.match(/(?:ckd|chronic kidney disease)\s*stage\s*(\d)/i);
    const egfrMatch = text.match(/egfr[:\s]+(\d+)/i);
    const egfr = egfrMatch ? parseInt(egfrMatch[1]) : null;

    let stage: number | null = stageMatch ? parseInt(stageMatch[1]) : null;
    if (!stage && egfr) {
      if (egfr < 15) stage = 5;
      else if (egfr < 30) stage = 4;
      else if (egfr < 60) stage = 3;
    }

    if (stage && stage >= 3) {
      const codeMap: Record<number, string> = { 3: "N18.3", 4: "N18.4", 5: "N18.5" };
      const descMap: Record<number, string> = {
        3: "Chronic kidney disease, stage 3 (moderate)",
        4: "Chronic kidney disease, stage 4 (severe)",
        5: "Chronic kidney disease, stage 5",
      };
      suggestions.push({
        id: "4",
        code: codeMap[stage] || "N18.9",
        codeType: "ICD10",
        description: descMap[stage] || "Chronic kidney disease, unspecified",
        confidence: egfr ? 0.93 : 0.80,
        evidenceText: egfr ? `...eGFR ${egfr} mL/min...` : `...CKD Stage ${stage}...`,
        evidenceStart: textLower.indexOf("egfr") > -1 ? textLower.indexOf("egfr") : textLower.indexOf("ckd"),
        evidenceEnd: (textLower.indexOf("egfr") > -1 ? textLower.indexOf("egfr") : textLower.indexOf("ckd")) + 20,
        rationale: `${egfr ? `eGFR of ${egfr} indicates` : "Documentation shows"} CKD Stage ${stage}. Specific staging code required for HCC capture.`,
        category: "Diseases of the genitourinary system",
        workRvu: 0,
        status: "pending",
      });
    }
  }

  // Procedure patterns
  if (textLower.includes("colonoscopy")) {
    suggestions.push({
      id: "5",
      code: "45378",
      codeType: "CPT",
      description: "Colonoscopy, flexible; diagnostic",
      confidence: 0.75,
      evidenceText: "...colonoscopy performed...",
      evidenceStart: textLower.indexOf("colonoscopy"),
      evidenceEnd: textLower.indexOf("colonoscopy") + 20,
      rationale: "Colonoscopy procedure documented. Review for any biopsies or additional procedures that may require higher-level code.",
      category: "Digestive System",
      workRvu: 3.36,
      status: "pending",
    });
  }

  if (textLower.includes("injection") && (textLower.includes("joint") || textLower.includes("knee") || textLower.includes("shoulder"))) {
    suggestions.push({
      id: "6",
      code: "20610",
      codeType: "CPT",
      description: "Arthrocentesis, aspiration and/or injection, major joint",
      confidence: 0.82,
      evidenceText: "...joint injection...",
      evidenceStart: textLower.indexOf("injection"),
      evidenceEnd: textLower.indexOf("injection") + 25,
      rationale: "Joint injection documented. 20610 appropriate for major joint (knee, shoulder, hip). Verify joint size for correct code.",
      category: "Musculoskeletal System",
      workRvu: 0.94,
      status: "pending",
    });
  }

  // E/M code suggestion based on time or complexity
  let emLevel: string | null = null;
  const timeMatch = text.match(/(?:total\s+)?time[:\s]+(\d+)\s*(?:min|minutes)/i);
  if (timeMatch) {
    const time = parseInt(timeMatch[1]);
    if (time >= 40) {
      emLevel = "99215";
      suggestions.unshift({
        id: "em",
        code: "99215",
        codeType: "CPT",
        description: "Office visit, established patient, high MDM or 40-54 min",
        confidence: 0.88,
        evidenceText: `...time: ${time} minutes...`,
        evidenceStart: textLower.indexOf("time"),
        evidenceEnd: textLower.indexOf("time") + 20,
        rationale: `Documented time of ${time} minutes supports 99215 (40-54 min threshold). Time-based billing.`,
        category: "Evaluation and Management",
        workRvu: 2.80,
        status: "pending",
      });
    } else if (time >= 30) {
      emLevel = "99214";
      suggestions.unshift({
        id: "em",
        code: "99214",
        codeType: "CPT",
        description: "Office visit, established patient, moderate MDM or 30-39 min",
        confidence: 0.88,
        evidenceText: `...time: ${time} minutes...`,
        evidenceStart: textLower.indexOf("time"),
        evidenceEnd: textLower.indexOf("time") + 20,
        rationale: `Documented time of ${time} minutes supports 99214 (30-39 min threshold). Time-based billing.`,
        category: "Evaluation and Management",
        workRvu: 1.92,
        status: "pending",
      });
    }
  }

  return {
    requestId: Math.random().toString(36).substring(7),
    textLength: text.length,
    suggestions,
    totalConcepts: suggestions.length,
    emLevel,
    processingTimeMs: 1500,
  };
};

// Helper functions
const getConfidenceColor = (confidence: number): string => {
  if (confidence >= 0.9) return "text-green-600";
  if (confidence >= 0.7) return "text-yellow-600";
  return "text-red-600";
};

const getConfidenceBg = (confidence: number): string => {
  if (confidence >= 0.9) return "bg-green-100 dark:bg-green-900/30";
  if (confidence >= 0.7) return "bg-yellow-100 dark:bg-yellow-900/30";
  return "bg-red-100 dark:bg-red-900/30";
};

// Sample clinical notes for quick testing
const SAMPLE_NOTES = [
  {
    title: "Diabetes Follow-up",
    text: `Patient: 65 y/o male
Chief Complaint: Diabetes follow-up

History: Type 2 diabetes mellitus with diabetic nephropathy. Recent labs show eGFR 42 mL/min, HbA1c 9.2%.
Also has chronic systolic heart failure with EF 35% on last echo. BNP was 450 pg/mL.

Assessment:
1. Type 2 diabetes with chronic kidney disease - poorly controlled
2. Chronic systolic heart failure - stable on current regimen

Plan:
- Increase metformin, consider adding GLP-1 agonist
- Continue carvedilol and lisinopril
- Recheck labs in 3 months

Total time: 35 minutes spent counseling and coordinating care.`,
  },
  {
    title: "Joint Injection",
    text: `Patient: 58 y/o female
Chief Complaint: Right knee pain

Physical Exam: Right knee with mild effusion, decreased ROM
Procedure: Performed joint injection of right knee with 40mg triamcinolone

Assessment: Osteoarthritis of right knee
Plan: Follow up in 4-6 weeks

Total time: 20 minutes`,
  },
  {
    title: "Colonoscopy Note",
    text: `Patient: 52 y/o male
Indication: Screening colonoscopy

Procedure: Colonoscopy performed under moderate sedation.
Findings: Two polyps removed from ascending colon. No masses or strictures.
Path pending.

Assessment: Colonic polyps
Plan: Follow up on pathology. Repeat colonoscopy in 5 years if adenomatous.`,
  },
];

export default function CodeSuggestionsPage() {
  const [clinicalText, setClinicalText] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());
  const [highlightedEvidence, setHighlightedEvidence] = useState<{
    start: number;
    end: number;
  } | null>(null);
  const [activeTab, setActiveTab] = useState<"all" | "icd10" | "cpt">("all");

  const handleAnalyze = useCallback(async () => {
    if (!clinicalText.trim()) return;

    setIsAnalyzing(true);
    setResult(null);
    setHighlightedEvidence(null);

    try {
      const analysisResult = await mockAnalyzeText(clinicalText);
      setResult(analysisResult);
    } catch (error) {
      console.error("Analysis failed:", error);
    } finally {
      setIsAnalyzing(false);
    }
  }, [clinicalText]);

  const handleAccept = (id: string) => {
    if (!result) return;
    setResult({
      ...result,
      suggestions: result.suggestions.map((s) =>
        s.id === id ? { ...s, status: "accepted" as const } : s
      ),
    });
  };

  const handleReject = (id: string) => {
    if (!result) return;
    setResult({
      ...result,
      suggestions: result.suggestions.map((s) =>
        s.id === id ? { ...s, status: "rejected" as const } : s
      ),
    });
  };

  const toggleExpanded = (id: string) => {
    const newExpanded = new Set(expandedCards);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedCards(newExpanded);
  };

  const handleShowEvidence = (suggestion: SuggestedCode) => {
    setHighlightedEvidence({
      start: suggestion.evidenceStart,
      end: suggestion.evidenceEnd,
    });
  };

  const loadSampleNote = (index: number) => {
    setClinicalText(SAMPLE_NOTES[index].text);
    setResult(null);
    setHighlightedEvidence(null);
  };

  const handleReset = () => {
    setClinicalText("");
    setResult(null);
    setHighlightedEvidence(null);
    setExpandedCards(new Set());
  };

  const handleAddToWorksheet = (suggestion: SuggestedCode) => {
    // In a real implementation, this would add to the worksheet
    alert(`Added ${suggestion.code} to worksheet`);
    handleAccept(suggestion.id);
  };

  // Filter suggestions by type
  const filteredSuggestions = result?.suggestions.filter((s) => {
    if (activeTab === "all") return true;
    if (activeTab === "icd10") return s.codeType === "ICD10";
    if (activeTab === "cpt") return s.codeType === "CPT";
    return true;
  }) || [];

  // Stats
  const acceptedCount = result?.suggestions.filter((s) => s.status === "accepted").length || 0;
  const pendingCount = result?.suggestions.filter((s) => s.status === "pending").length || 0;

  // Render text with highlights
  const renderHighlightedText = () => {
    if (!highlightedEvidence || !clinicalText) return clinicalText;

    const before = clinicalText.slice(0, highlightedEvidence.start);
    const highlighted = clinicalText.slice(highlightedEvidence.start, highlightedEvidence.end);
    const after = clinicalText.slice(highlightedEvidence.end);

    return (
      <>
        {before}
        <mark className="bg-yellow-300 dark:bg-yellow-700 px-0.5 rounded">{highlighted}</mark>
        {after}
      </>
    );
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
            <h1 className="text-2xl font-bold tracking-tight">
              AI Code Suggestions
            </h1>
            <p className="text-muted-foreground">
              Paste clinical notes to get ICD-10 and CPT code recommendations
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleReset}>
            <RotateCcw className="mr-2 h-4 w-4" />
            Reset
          </Button>
          <Link href="/billing/worksheet">
            <Button variant="outline">
              <ClipboardCopy className="mr-2 h-4 w-4" />
              View Worksheet
            </Button>
          </Link>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Input Panel */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Clinical Note
              </CardTitle>
              <CardDescription>
                Paste or type clinical documentation to analyze
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Sample Notes */}
              <div className="flex flex-wrap gap-2">
                <span className="text-sm text-muted-foreground">
                  Quick start:
                </span>
                {SAMPLE_NOTES.map((sample, idx) => (
                  <Button
                    key={idx}
                    variant="outline"
                    size="sm"
                    onClick={() => loadSampleNote(idx)}
                  >
                    {sample.title}
                  </Button>
                ))}
              </div>

              {/* Text Input */}
              <div className="relative">
                {highlightedEvidence ? (
                  <div className="min-h-64 rounded-md border bg-background p-3 text-sm whitespace-pre-wrap font-mono">
                    {renderHighlightedText()}
                  </div>
                ) : (
                  <Textarea
                    placeholder="Paste clinical note here...

Example:
Patient is a 65 y/o male with type 2 diabetes mellitus with diabetic nephropathy.
Recent labs show eGFR 42 mL/min, HbA1c 9.2%. Also has chronic systolic heart failure
with EF 35% on last echo.

Total time: 35 minutes spent counseling and coordinating care."
                    value={clinicalText}
                    onChange={(e) => setClinicalText(e.target.value)}
                    className="min-h-64 font-mono text-sm"
                  />
                )}
                {highlightedEvidence && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="absolute top-2 right-2"
                    onClick={() => setHighlightedEvidence(null)}
                  >
                    Edit Text
                  </Button>
                )}
              </div>

              {/* Character count */}
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{clinicalText.length} characters</span>
                {result && (
                  <span>Analyzed in {result.processingTimeMs}ms</span>
                )}
              </div>

              {/* Analyze Button */}
              <Button
                className="w-full"
                size="lg"
                onClick={handleAnalyze}
                disabled={!clinicalText.trim() || isAnalyzing}
              >
                {isAnalyzing ? (
                  <>
                    <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-2 h-5 w-5" />
                    Analyze for Codes
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Results Panel */}
        <div className="space-y-4">
          {/* Stats */}
          {result && (
            <div className="grid gap-4 grid-cols-3">
              <Card className="border-l-4 border-l-blue-500">
                <CardContent className="pt-4">
                  <div className="text-2xl font-bold">
                    {result.suggestions.length}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Codes Suggested
                  </p>
                </CardContent>
              </Card>
              <Card className="border-l-4 border-l-green-500">
                <CardContent className="pt-4">
                  <div className="text-2xl font-bold text-green-600">
                    {acceptedCount}
                  </div>
                  <p className="text-xs text-muted-foreground">Accepted</p>
                </CardContent>
              </Card>
              <Card className="border-l-4 border-l-yellow-500">
                <CardContent className="pt-4">
                  <div className="text-2xl font-bold text-yellow-600">
                    {pendingCount}
                  </div>
                  <p className="text-xs text-muted-foreground">Pending</p>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Results Card */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Search className="h-5 w-5" />
                  Suggested Codes
                </CardTitle>
                {result && (
                  <Tabs
                    value={activeTab}
                    onValueChange={(v) => setActiveTab(v as "all" | "icd10" | "cpt")}
                  >
                    <TabsList className="h-8">
                      <TabsTrigger value="all" className="text-xs">
                        All
                      </TabsTrigger>
                      <TabsTrigger value="icd10" className="text-xs">
                        ICD-10
                      </TabsTrigger>
                      <TabsTrigger value="cpt" className="text-xs">
                        CPT
                      </TabsTrigger>
                    </TabsList>
                  </Tabs>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {!result && !isAnalyzing && (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Sparkles className="h-12 w-12 text-muted-foreground/30" />
                  <h3 className="mt-4 text-lg font-semibold">
                    Ready to Analyze
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Paste a clinical note and click &quot;Analyze for Codes&quot;
                  </p>
                </div>
              )}

              {isAnalyzing && (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Loader2 className="h-12 w-12 text-blue-500 animate-spin" />
                  <h3 className="mt-4 text-lg font-semibold">
                    Analyzing Clinical Text
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Extracting concepts and matching codes...
                  </p>
                </div>
              )}

              {result && filteredSuggestions.length === 0 && (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <AlertCircle className="h-12 w-12 text-muted-foreground/30" />
                  <h3 className="mt-4 text-lg font-semibold">
                    No Codes Found
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    {activeTab === "all"
                      ? "No codes could be extracted from this text"
                      : `No ${activeTab.toUpperCase()} codes found`}
                  </p>
                </div>
              )}

              {result && filteredSuggestions.length > 0 && (
                <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
                  {filteredSuggestions.map((suggestion) => (
                    <div
                      key={suggestion.id}
                      className={`rounded-lg border p-4 transition-all ${
                        suggestion.status === "accepted"
                          ? "border-green-500 bg-green-50 dark:bg-green-950/30"
                          : suggestion.status === "rejected"
                          ? "border-red-500 bg-red-50 dark:bg-red-950/30 opacity-60"
                          : "hover:border-blue-300"
                      }`}
                    >
                      {/* Code Header */}
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-3">
                          <div
                            className={`rounded-lg p-2 ${
                              suggestion.codeType === "ICD10"
                                ? "bg-blue-100 dark:bg-blue-900/50"
                                : "bg-purple-100 dark:bg-purple-900/50"
                            }`}
                          >
                            {suggestion.codeType === "ICD10" ? (
                              <Stethoscope className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                            ) : (
                              <Code className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                            )}
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <Badge
                                variant={
                                  suggestion.codeType === "ICD10"
                                    ? "default"
                                    : "secondary"
                                }
                              >
                                {suggestion.codeType}
                              </Badge>
                              <code className="rounded bg-muted px-2 py-0.5 text-sm font-mono font-bold">
                                {suggestion.code}
                              </code>
                              {suggestion.status !== "pending" && (
                                <Badge
                                  variant="outline"
                                  className={
                                    suggestion.status === "accepted"
                                      ? "border-green-500 text-green-600"
                                      : "border-red-500 text-red-600"
                                  }
                                >
                                  {suggestion.status === "accepted" ? (
                                    <CheckCircle className="mr-1 h-3 w-3" />
                                  ) : (
                                    <XCircle className="mr-1 h-3 w-3" />
                                  )}
                                  {suggestion.status}
                                </Badge>
                              )}
                            </div>
                            <p className="mt-1 text-sm font-medium">
                              {suggestion.description}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {suggestion.category}
                            </p>
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <div
                            className={`rounded px-2 py-1 text-sm font-bold ${getConfidenceBg(
                              suggestion.confidence
                            )} ${getConfidenceColor(suggestion.confidence)}`}
                          >
                            {Math.round(suggestion.confidence * 100)}%
                          </div>
                          {suggestion.workRvu > 0 && (
                            <p className="text-xs text-muted-foreground mt-1">
                              RVU: {suggestion.workRvu.toFixed(2)}
                            </p>
                          )}
                        </div>
                      </div>

                      {/* Confidence Bar */}
                      <div className="mt-3">
                        <Progress
                          value={suggestion.confidence * 100}
                          className="h-1.5"
                        />
                      </div>

                      {/* Evidence & Rationale Toggle */}
                      <div className="mt-3 pt-3 border-t">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="p-0 h-auto text-sm"
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
                              Show Rationale
                            </>
                          )}
                        </Button>

                        {expandedCards.has(suggestion.id) && (
                          <div className="mt-3 space-y-2 animate-in slide-in-from-top-2">
                            <div className="rounded bg-muted/50 p-3">
                              <p className="text-xs font-semibold text-muted-foreground mb-1">
                                RATIONALE
                              </p>
                              <p className="text-sm">{suggestion.rationale}</p>
                            </div>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleShowEvidence(suggestion)}
                            >
                              <Eye className="mr-2 h-3 w-3" />
                              Highlight Evidence in Text
                            </Button>
                          </div>
                        )}
                      </div>

                      {/* Action Buttons */}
                      {suggestion.status === "pending" && (
                        <div className="mt-3 pt-3 border-t flex justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleReject(suggestion.id)}
                          >
                            <ThumbsDown className="mr-1 h-3 w-3" />
                            Reject
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleAddToWorksheet(suggestion)}
                          >
                            <Plus className="mr-1 h-3 w-3" />
                            Add to Worksheet
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => handleAccept(suggestion.id)}
                          >
                            <ThumbsUp className="mr-1 h-3 w-3" />
                            Accept
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
