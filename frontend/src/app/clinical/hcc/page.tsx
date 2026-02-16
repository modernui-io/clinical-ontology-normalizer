"use client";

/**
 * HCC Gap Analysis — Identify coding opportunities and RAF score impact
 *
 * Connects to POST /hcc-analysis/analyze. Falls back to demo data
 * when the API is unavailable.
 */

import { useState, useCallback } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ArrowLeft,
  Plus,
  X,
  TrendingUp,
  AlertCircle,
  DollarSign,
  Target,
  Activity,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Auth helpers
// ---------------------------------------------------------------------------

const API_BASE = "/api/hcc-analysis";

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem("auth_tokens");
    if (stored) {
      const tokens = JSON.parse(stored);
      return tokens.access_token || null;
    }
  } catch {
    // Ignore
  }
  return null;
}

function authHeaders(token: string | null): HeadersInit {
  const h: HeadersInit = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HCCEvidence {
  source: string;
  text: string;
  confidence: number;
}

interface HCCOpportunity {
  hcc_code: string;
  hcc_description: string;
  category: string;
  gap_type: string;
  confidence: string;
  recommended_icd10: string[];
  evidence: HCCEvidence[];
  raf_impact: number;
  coder_notes: string;
  priority: number;
}

interface HCCAnalysisResult {
  request_id: string;
  patient_id: string;
  current_raf_score: number;
  potential_raf_score: number;
  raf_gap: number;
  captured_hccs: string[];
  opportunities: HCCOpportunity[];
  priority_actions: string[];
  total_revenue_impact: number | null;
  processing_time_ms: number;
}

// ---------------------------------------------------------------------------
// Demo fallback
// ---------------------------------------------------------------------------

function demoResult(pid: string): HCCAnalysisResult {
  return {
    request_id: "demo-hcc-001",
    patient_id: pid,
    current_raf_score: 1.245,
    potential_raf_score: 2.018,
    raf_gap: 0.773,
    captured_hccs: ["HCC19", "HCC85"],
    opportunities: [
      {
        hcc_code: "HCC18",
        hcc_description: "Diabetes with Chronic Complications",
        category: "Endocrine",
        gap_type: "suspect",
        confidence: "high",
        recommended_icd10: ["E11.65", "E11.22"],
        evidence: [
          { source: "NLP", text: "HbA1c 9.2% noted in progress note", confidence: 0.92 },
          { source: "Lab", text: "eGFR trending downward over 12 months", confidence: 0.85 },
        ],
        raf_impact: 0.318,
        coder_notes: "Upgrade E11.9 to E11.65 based on nephropathy evidence",
        priority: 1,
      },
      {
        hcc_code: "HCC108",
        hcc_description: "Vascular Disease",
        category: "Cardiovascular",
        gap_type: "undercoded",
        confidence: "medium",
        recommended_icd10: ["I73.9"],
        evidence: [
          { source: "NLP", text: "Peripheral vascular disease mentioned in HPI", confidence: 0.78 },
        ],
        raf_impact: 0.288,
        coder_notes: "Add I73.9 — peripheral vascular disease noted but not coded",
        priority: 2,
      },
      {
        hcc_code: "HCC111",
        hcc_description: "Chronic Obstructive Pulmonary Disease",
        category: "Respiratory",
        gap_type: "suspect",
        confidence: "medium",
        recommended_icd10: ["J44.1"],
        evidence: [
          { source: "NLP", text: "Uses albuterol inhaler prn, chronic cough", confidence: 0.72 },
        ],
        raf_impact: 0.167,
        coder_notes: "Consider J44.1 based on medication and symptom history",
        priority: 3,
      },
    ],
    priority_actions: [
      "Upgrade DM diagnosis from E11.9 to E11.65 (diabetic nephropathy) — highest RAF impact",
      "Add I73.9 for peripheral vascular disease noted in clinical notes",
      "Evaluate COPD coding based on inhaler use and chronic cough history",
      "Schedule comprehensive annual wellness visit to capture all active conditions",
      "Review lab trends for additional chronic kidney disease staging",
    ],
    total_revenue_impact: 6842,
    processing_time_ms: 156,
  };
}

const confidenceColors: Record<string, string> = {
  high: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  low: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function HCCAnalysisPage() {
  const [demoMode, setDemoMode] = useState(false);
  const [patientId, setPatientId] = useState("");
  const [icd10Codes, setIcd10Codes] = useState<string[]>([]);
  const [currentCode, setCurrentCode] = useState("");
  const [clinicalNotes, setClinicalNotes] = useState("");
  const [age, setAge] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<HCCAnalysisResult | null>(null);

  const addCode = useCallback(() => {
    const trimmed = currentCode.trim().toUpperCase();
    if (trimmed && !icd10Codes.includes(trimmed)) {
      setIcd10Codes([...icd10Codes, trimmed]);
      setCurrentCode("");
    }
  }, [currentCode, icd10Codes]);

  const removeCode = (code: string) => {
    setIcd10Codes(icd10Codes.filter((c) => c !== code));
  };

  const loadDemo = () => {
    setPatientId("P-12345");
    setIcd10Codes(["E11.9", "I10", "E78.5"]);
    setAge("68");
    setClinicalNotes(
      "Patient with poorly controlled type 2 diabetes, hypertension, and hyperlipidemia. " +
        "Recent HbA1c 9.2%. Diabetic nephropathy suspected. Uses albuterol inhaler prn. " +
        "Peripheral vascular disease noted on exam.",
    );
  };

  const analyze = useCallback(async () => {
    if (!patientId.trim()) {
      toast.error("Patient ID is required");
      return;
    }
    setIsLoading(true);
    setResult(null);
    setDemoMode(false);

    try {
      const body: Record<string, unknown> = {
        patient_id: patientId.trim(),
        icd10_codes: icd10Codes,
      };
      if (clinicalNotes.trim()) body.clinical_notes = clinicalNotes.trim();
      if (age) body.age = parseInt(age);

      const token = getStoredToken();
      const res = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error();
      const data: HCCAnalysisResult = await res.json();
      setResult(data);
      toast.success(
        `Found ${data.opportunities.length} opportunities (+${data.raf_gap.toFixed(3)} RAF)`,
      );
    } catch {
      setDemoMode(true);
      setResult(demoResult(patientId.trim()));
      toast.info("Demo mode — API unavailable");
    } finally {
      setIsLoading(false);
    }
  }, [patientId, icd10Codes, clinicalNotes, age]);

  return (
    <div className="container mx-auto max-w-6xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/clinical">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-1 h-4 w-4" /> Clinical
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">HCC Gap Analysis</h1>
          <p className="text-muted-foreground">
            Identify HCC coding opportunities and RAF score impact
          </p>
        </div>
      </div>

      {/* Demo mode banner */}
      {demoMode && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>
            <strong>Client-side demo mode</strong> — API is unavailable. Showing
            simulated results.
          </span>
        </div>
      )}

      {/* Input Form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Patient Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Patient ID *</Label>
              <Input
                placeholder="Enter patient identifier"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Age</Label>
              <Input
                type="number"
                placeholder="Patient age"
                value={age}
                onChange={(e) => setAge(e.target.value)}
                min="0"
                max="150"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Current ICD-10 Codes</Label>
            <div className="flex gap-2">
              <Input
                placeholder="Add ICD-10 code (e.g., E11.9)"
                value={currentCode}
                onChange={(e) => setCurrentCode(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addCode();
                  }
                }}
              />
              <Button type="button" onClick={addCode} size="sm">
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            {icd10Codes.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {icd10Codes.map((code) => (
                  <Badge key={code} variant="secondary" className="gap-1">
                    {code}
                    <X
                      className="h-3 w-3 cursor-pointer"
                      onClick={() => removeCode(code)}
                    />
                  </Badge>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label>Clinical Notes (optional)</Label>
            <textarea
              className="min-h-[100px] w-full resize-y rounded-md border bg-background p-3 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              placeholder="Paste clinical notes for NLP-based gap detection..."
              value={clinicalNotes}
              onChange={(e) => setClinicalNotes(e.target.value)}
            />
          </div>

          <div className="flex gap-2">
            <Button onClick={analyze} disabled={isLoading || !patientId.trim()}>
              {isLoading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Target className="mr-2 h-4 w-4" />
              )}
              Analyze HCC Gaps
            </Button>
            <Button variant="outline" onClick={loadDemo}>
              Load Demo
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {result && (
        <>
          {/* RAF Score Summary */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <Card>
              <CardContent className="p-4 text-center">
                <p className="text-xs text-muted-foreground">Current RAF</p>
                <p className="text-2xl font-bold tabular-nums">
                  {result.current_raf_score.toFixed(3)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <p className="text-xs text-muted-foreground">Potential RAF</p>
                <p className="text-2xl font-bold tabular-nums text-green-600">
                  {result.potential_raf_score.toFixed(3)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <p className="text-xs text-muted-foreground">RAF Gap</p>
                <p className="flex items-center justify-center gap-1 text-2xl font-bold tabular-nums text-amber-600">
                  <TrendingUp className="h-5 w-5" />
                  +{result.raf_gap.toFixed(3)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <p className="text-xs text-muted-foreground">Revenue Impact</p>
                <p className="flex items-center justify-center gap-1 text-2xl font-bold tabular-nums text-green-600">
                  <DollarSign className="h-5 w-5" />
                  {result.total_revenue_impact
                    ? `$${result.total_revenue_impact.toLocaleString()}`
                    : "N/A"}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Opportunities */}
          {result.opportunities.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Activity className="h-5 w-5" />
                  Capture Opportunities ({result.opportunities.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {result.opportunities.map((opp) => (
                    <div
                      key={opp.hcc_code}
                      className="space-y-2 rounded-lg border p-4"
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <code className="font-mono font-bold">
                              {opp.hcc_code}
                            </code>
                            <span className="text-sm font-medium">
                              {opp.hcc_description}
                            </span>
                          </div>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {opp.coder_notes}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge className={confidenceColors[opp.confidence] || ""}>
                            {opp.confidence}
                          </Badge>
                          <Badge variant="outline">
                            +{opp.raf_impact.toFixed(3)} RAF
                          </Badge>
                        </div>
                      </div>

                      {opp.recommended_icd10.length > 0 && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">
                            Recommended codes:
                          </span>
                          {opp.recommended_icd10.map((code) => (
                            <Badge
                              key={code}
                              variant="secondary"
                              className="font-mono text-xs"
                            >
                              {code}
                            </Badge>
                          ))}
                        </div>
                      )}

                      {opp.evidence.length > 0 && (
                        <div className="mt-2 border-t pt-2">
                          <p className="mb-1 text-xs text-muted-foreground">
                            Evidence:
                          </p>
                          {opp.evidence.map((ev, i) => (
                            <p key={i} className="text-xs text-muted-foreground">
                              [{ev.source}] {ev.text} (conf:{" "}
                              {(ev.confidence * 100).toFixed(0)}%)
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Priority Actions */}
          {result.priority_actions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Priority Actions</CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="list-inside list-decimal space-y-2">
                  {result.priority_actions.map((action, i) => (
                    <li key={i} className="text-sm">
                      {action}
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
