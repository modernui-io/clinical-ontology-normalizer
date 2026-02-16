"use client";

/**
 * Differential Diagnosis Generator — ranked diagnoses from clinical findings
 *
 * Connects to POST /differential-diagnosis/generate. Falls back to demo data
 * when the API is unavailable.
 */

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
import {
  ArrowLeft,
  Plus,
  X,
  Stethoscope,
  AlertTriangle,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Brain,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Auth helpers
// ---------------------------------------------------------------------------

const API_BASE = "/api/differential-diagnosis";

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

interface CERCitation {
  claim: string;
  supporting_evidence: string[];
  opposing_evidence: string[];
  reasoning: string;
  strength: string;
  clinical_pearls: string[];
  diagnostic_criteria: string[];
  must_rule_out: string[];
}

interface DiagnosisCandidate {
  name: string;
  ranking_score: number;
  urgency: string;
  domain: string;
  concept_id: number | null;
  cer_citation: CERCitation;
  suggested_workup: string[];
}

interface DifferentialResult {
  request_id: string;
  findings: string[];
  total_candidates: number;
  diagnoses: DiagnosisCandidate[];
  red_flags: string[];
  suggested_history: string[];
  suggested_exam: string[];
  processing_time_ms: number;
}

// ---------------------------------------------------------------------------
// Demo fallback
// ---------------------------------------------------------------------------

function demoResult(findings: string[]): DifferentialResult {
  return {
    request_id: "demo-ddx-001",
    findings,
    total_candidates: 4,
    diagnoses: [
      {
        name: "Acute Coronary Syndrome",
        ranking_score: 0.87,
        urgency: "emergent",
        domain: "cardiology",
        concept_id: 312327,
        cer_citation: {
          claim: "ACS is the most likely diagnosis given chest pain with ST changes",
          supporting_evidence: [
            "Chest pain is the cardinal symptom of ACS",
            "ST elevation indicates transmural ischemia",
            "Dyspnea suggests impaired cardiac output",
          ],
          opposing_evidence: [
            "Need to rule out aortic dissection with similar presentation",
          ],
          reasoning:
            "The combination of acute chest pain, dyspnea, and ST elevation strongly suggests ACS. Immediate evaluation with ECG, troponins, and cardiology consultation is warranted.",
          strength: "strong",
          clinical_pearls: [
            "Women and diabetics may present atypically",
            "Serial troponins more sensitive than single draw",
            "Do not delay reperfusion therapy for diagnostic certainty",
          ],
          diagnostic_criteria: [
            "Typical chest pain or equivalent",
            "ECG changes (ST elevation/depression, new LBBB)",
            "Elevated cardiac biomarkers (troponin)",
          ],
          must_rule_out: ["Aortic dissection", "Pulmonary embolism", "Tension pneumothorax"],
        },
        suggested_workup: ["12-lead ECG", "Serial troponin", "Chest X-ray", "CBC", "BMP"],
      },
      {
        name: "Pulmonary Embolism",
        ranking_score: 0.68,
        urgency: "emergent",
        domain: "pulmonology",
        concept_id: 440417,
        cer_citation: {
          claim: "PE should be considered in acute dyspnea with chest pain",
          supporting_evidence: [
            "Dyspnea is the most common symptom of PE",
            "Chest pain (pleuritic) present in ~50% of PE cases",
          ],
          opposing_evidence: [
            "ST elevation more typical of ACS than PE",
          ],
          reasoning:
            "PE can mimic ACS and should be actively excluded. D-dimer and CTPA should be considered.",
          strength: "moderate",
          clinical_pearls: [
            "Wells score helps stratify PE probability",
            "Right heart strain on ECG may suggest PE",
          ],
          diagnostic_criteria: [
            "Clinical suspicion + Wells score",
            "Elevated D-dimer in low-risk patients",
            "CTPA for definitive diagnosis",
          ],
          must_rule_out: [],
        },
        suggested_workup: ["D-dimer", "CT pulmonary angiography", "Lower extremity doppler"],
      },
      {
        name: "Unstable Angina",
        ranking_score: 0.52,
        urgency: "urgent",
        domain: "cardiology",
        concept_id: 315296,
        cer_citation: {
          claim: "Unstable angina presents with rest pain without biomarker elevation",
          supporting_evidence: [
            "Chest pain at rest suggests unstable plaque",
          ],
          opposing_evidence: [
            "ST elevation would upgrade to STEMI rather than UA",
          ],
          reasoning:
            "If troponins are negative, unstable angina remains in the differential for acute chest pain.",
          strength: "moderate",
          clinical_pearls: [
            "Serial troponins needed to distinguish from NSTEMI",
          ],
          diagnostic_criteria: [
            "Ischemic symptoms at rest or accelerating pattern",
            "No elevation of cardiac biomarkers",
            "ECG changes possible but without ST elevation",
          ],
          must_rule_out: [],
        },
        suggested_workup: ["Serial troponin at 0h and 3h", "Continuous telemetry"],
      },
      {
        name: "Aortic Dissection",
        ranking_score: 0.35,
        urgency: "emergent",
        domain: "cardiology",
        concept_id: 317576,
        cer_citation: {
          claim: "Aortic dissection must be ruled out in severe chest pain",
          supporting_evidence: [
            "Sudden severe chest pain is characteristic",
          ],
          opposing_evidence: [
            "Typically described as tearing/ripping, not pressure",
            "ST elevation less common in dissection",
          ],
          reasoning:
            "Though less likely, aortic dissection is catastrophic if missed. Blood pressure differential and CT angiography should be considered.",
          strength: "weak",
          clinical_pearls: [
            "Check bilateral arm blood pressures",
            "Chest X-ray may show widened mediastinum",
            "Type A requires emergent surgery",
          ],
          diagnostic_criteria: [
            "Acute severe chest/back pain",
            "Blood pressure differential >20mmHg",
            "CT angiography or TEE for confirmation",
          ],
          must_rule_out: [],
        },
        suggested_workup: ["CT aortic angiography", "Bilateral arm BPs", "D-dimer"],
      },
    ],
    red_flags: [
      "Acute MI / STEMI — immediate catheterization may be needed",
      "Aortic dissection — check for BP differential and widened mediastinum",
      "Tension pneumothorax — assess for tracheal deviation and absent breath sounds",
    ],
    suggested_history: [
      "Onset, character, and radiation of pain",
      "Associated symptoms: diaphoresis, nausea, syncope",
      "Prior cardiac history, PCI, CABG",
      "Risk factors: smoking, diabetes, hypertension, family history",
      "Recent immobilization or long travel (PE risk)",
    ],
    suggested_exam: [
      "Vital signs with bilateral arm blood pressures",
      "Cardiac auscultation for murmurs and S3/S4",
      "Lung auscultation for crackles or absent breath sounds",
      "JVD assessment",
      "Lower extremity edema and calf tenderness",
    ],
    processing_time_ms: 234,
  };
}

// ---------------------------------------------------------------------------
// Style maps
// ---------------------------------------------------------------------------

const urgencyStyles: Record<string, string> = {
  emergent: "bg-red-600 text-white",
  urgent: "bg-orange-500 text-white",
  semi_urgent: "bg-amber-500 text-white",
  routine: "bg-blue-500 text-white",
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DifferentialDiagnosisPage() {
  const [demoMode, setDemoMode] = useState(false);
  const [findings, setFindings] = useState<string[]>([]);
  const [currentFinding, setCurrentFinding] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<DifferentialResult | null>(null);
  const [expandedDx, setExpandedDx] = useState<Set<string>>(new Set());

  const addFinding = useCallback(() => {
    const trimmed = currentFinding.trim();
    if (trimmed && !findings.includes(trimmed)) {
      setFindings([...findings, trimmed]);
      setCurrentFinding("");
    }
  }, [currentFinding, findings]);

  const removeFinding = (finding: string) => {
    setFindings(findings.filter((f) => f !== finding));
  };

  const toggleExpand = (name: string) => {
    const next = new Set(expandedDx);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    setExpandedDx(next);
  };

  const loadDemo = () => {
    setFindings(["chest pain", "dyspnea", "ST elevation", "diaphoresis"]);
    setAge("62");
    setGender("male");
  };

  const generateDifferential = useCallback(async () => {
    if (findings.length === 0) {
      toast.error("Add at least one clinical finding");
      return;
    }

    setIsLoading(true);
    setResult(null);
    setDemoMode(false);

    try {
      const body: Record<string, unknown> = { findings, max_diagnoses: 10 };
      if (age) body.age = parseInt(age);
      if (gender) body.gender = gender;

      const token = getStoredToken();
      const response = await fetch(`${API_BASE}/generate`, {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error();
      const data: DifferentialResult = await response.json();
      setResult(data);
      setExpandedDx(new Set());
      toast.success(`Generated ${data.total_candidates} differential diagnoses`);
    } catch {
      setDemoMode(true);
      const demo = demoResult(findings);
      setResult(demo);
      setExpandedDx(new Set());
      toast.info("Demo mode — API unavailable");
    } finally {
      setIsLoading(false);
    }
  }, [findings, age, gender]);

  return (
    <div className="container mx-auto max-w-5xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/clinical">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
        </Link>
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-bold tracking-tight">
            <Brain className="h-7 w-7" />
            Differential Diagnosis
          </h1>
          <p className="text-muted-foreground">
            Ranked diagnoses from clinical findings with CER citations
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

      {/* Input */}
      <Card>
        <CardHeader>
          <CardTitle>Clinical Findings</CardTitle>
          <CardDescription>
            Enter presenting symptoms and clinical findings
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Enter a finding (e.g., chest pain, dyspnea, fever)"
              value={currentFinding}
              onChange={(e) => setCurrentFinding(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addFinding();
                }
              }}
            />
            <Button onClick={addFinding} size="sm">
              <Plus className="h-4 w-4" />
            </Button>
          </div>

          {findings.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {findings.map((f) => (
                <Badge key={f} variant="secondary" className="px-3 py-1 text-sm">
                  {f}
                  <button
                    onClick={() => removeFinding(f)}
                    className="ml-2 hover:text-destructive"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          )}

          <div className="grid max-w-md grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="age">Age (optional)</Label>
              <Input
                id="age"
                type="number"
                placeholder="e.g., 55"
                value={age}
                onChange={(e) => setAge(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="gender">Gender (optional)</Label>
              <select
                id="gender"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                value={gender}
                onChange={(e) => setGender(e.target.value)}
              >
                <option value="">Not specified</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              onClick={generateDifferential}
              disabled={findings.length === 0 || isLoading}
            >
              {isLoading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Stethoscope className="mr-2 h-4 w-4" />
              )}
              Generate Differential
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
          {/* Red Flags */}
          {result.red_flags.length > 0 && (
            <Card className="border-red-200 dark:border-red-900">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-red-600">
                  <AlertTriangle className="h-5 w-5" />
                  Red Flags — Cannot Miss Diagnoses
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {result.red_flags.map((flag, i) => (
                    <Badge key={i} variant="destructive">
                      {flag}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Differential List */}
          <Card>
            <CardHeader>
              <CardTitle>
                Ranked Differential ({result.total_candidates} candidates)
              </CardTitle>
              <CardDescription>
                Processed in {result.processing_time_ms.toFixed(0)}ms
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {result.diagnoses.map((dx, idx) => (
                  <div
                    key={dx.name}
                    className="rounded-lg border p-4 transition-colors hover:bg-muted/50"
                  >
                    <div
                      className="flex cursor-pointer items-center gap-3"
                      onClick={() => toggleExpand(dx.name)}
                    >
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
                        {idx + 1}
                      </div>
                      <div className="flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold">{dx.name}</span>
                          <Badge
                            className={
                              urgencyStyles[dx.urgency] || "bg-gray-500 text-white"
                            }
                          >
                            {dx.urgency.replace("_", " ")}
                          </Badge>
                          <Badge variant="outline">{dx.domain}</Badge>
                        </div>
                        <div className="mt-1 text-sm text-muted-foreground">
                          Score: {(dx.ranking_score * 100).toFixed(0)}% | Evidence:{" "}
                          <span
                            className={`font-medium ${
                              dx.cer_citation.strength === "strong"
                                ? "text-green-600"
                                : dx.cer_citation.strength === "moderate"
                                  ? "text-amber-600"
                                  : "text-gray-600"
                            }`}
                          >
                            {dx.cer_citation.strength}
                          </span>
                        </div>
                      </div>
                      <div className="shrink-0">
                        {expandedDx.has(dx.name) ? (
                          <ChevronUp className="h-5 w-5" />
                        ) : (
                          <ChevronDown className="h-5 w-5" />
                        )}
                      </div>
                    </div>

                    {expandedDx.has(dx.name) && (
                      <div className="mt-4 space-y-4 pl-11">
                        <div className="space-y-2">
                          <h4 className="text-sm font-medium">Clinical Reasoning (CER)</h4>
                          <p className="text-sm text-muted-foreground">
                            {dx.cer_citation.reasoning}
                          </p>

                          {dx.cer_citation.supporting_evidence.length > 0 && (
                            <div>
                              <span className="text-xs font-medium text-green-600">
                                Supporting:
                              </span>
                              <ul className="list-inside list-disc text-sm text-muted-foreground">
                                {dx.cer_citation.supporting_evidence.map((e, i) => (
                                  <li key={i}>{e}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {dx.cer_citation.opposing_evidence.length > 0 && (
                            <div>
                              <span className="text-xs font-medium text-red-600">
                                Opposing:
                              </span>
                              <ul className="list-inside list-disc text-sm text-muted-foreground">
                                {dx.cer_citation.opposing_evidence.map((e, i) => (
                                  <li key={i}>{e}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>

                        {dx.cer_citation.clinical_pearls.length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium">Clinical Pearls</h4>
                            <ul className="list-inside list-disc text-sm text-muted-foreground">
                              {dx.cer_citation.clinical_pearls.map((p, i) => (
                                <li key={i}>{p}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {dx.suggested_workup.length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium">Suggested Workup</h4>
                            <div className="mt-1 flex flex-wrap gap-1.5">
                              {dx.suggested_workup.map((w, i) => (
                                <Badge key={i} variant="outline" className="text-xs">
                                  {w}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}

                        {dx.cer_citation.diagnostic_criteria.length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium">Diagnostic Criteria</h4>
                            <ul className="list-inside list-disc text-sm text-muted-foreground">
                              {dx.cer_citation.diagnostic_criteria.map((c, i) => (
                                <li key={i}>{c}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Suggested Next Steps */}
          {(result.suggested_history.length > 0 ||
            result.suggested_exam.length > 0) && (
            <div className="grid gap-4 md:grid-cols-2">
              {result.suggested_history.length > 0 && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">
                      Additional History to Gather
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="list-inside list-disc space-y-1 text-sm">
                      {result.suggested_history.map((h, i) => (
                        <li key={i}>{h}</li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}
              {result.suggested_exam.length > 0 && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">
                      Physical Exam Maneuvers
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="list-inside list-disc space-y-1 text-sm">
                      {result.suggested_exam.map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
