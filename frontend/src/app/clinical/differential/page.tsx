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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowLeft,
  Plus,
  X,
  Search,
  Stethoscope,
  AlertTriangle,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Activity,
  Brain,
} from "lucide-react";

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
  probability: number;
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

const urgencyStyles: Record<string, string> = {
  emergent: "bg-red-600 text-white",
  urgent: "bg-orange-500 text-white",
  semi_urgent: "bg-amber-500 text-white",
  routine: "bg-blue-500 text-white",
};

const strengthStyles: Record<string, string> = {
  strong: "bg-green-500 text-white",
  moderate: "bg-amber-500 text-white",
  weak: "bg-gray-500 text-white",
};

export default function DifferentialDiagnosisPage() {
  const [findings, setFindings] = useState<string[]>([]);
  const [currentFinding, setCurrentFinding] = useState("");
  const [age, setAge] = useState<string>("");
  const [gender, setGender] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<DifferentialResult | null>(null);
  const [error, setError] = useState<string | null>(null);
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
    if (next.has(name)) {
      next.delete(name);
    } else {
      next.add(name);
    }
    setExpandedDx(next);
  };

  const generateDifferential = useCallback(async () => {
    if (findings.length === 0) return;

    setIsLoading(true);
    setError(null);

    try {
      const body: Record<string, unknown> = {
        findings,
        max_diagnoses: 10,
      };
      if (age) body.age = parseInt(age);
      if (gender) body.gender = gender;

      const response = await fetch("/api/differential-diagnosis/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data: DifferentialResult = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsLoading(false);
    }
  }, [findings, age, gender]);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/clinical">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Brain className="h-6 w-6" />
            Differential Diagnosis Generator
          </h1>
          <p className="text-muted-foreground">
            Generate ranked differential diagnoses from clinical findings with
            CER citations
          </p>
        </div>
      </div>

      {/* Input Section */}
      <Card>
        <CardHeader>
          <CardTitle>Clinical Findings</CardTitle>
          <CardDescription>
            Enter presenting symptoms and clinical findings
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Findings input */}
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

          {/* Findings tags */}
          {findings.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {findings.map((f) => (
                <Badge
                  key={f}
                  variant="secondary"
                  className="px-3 py-1 text-sm"
                >
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

          {/* Demographics */}
          <div className="grid grid-cols-2 gap-4 max-w-md">
            <div>
              <Label htmlFor="age">Age (optional)</Label>
              <Input
                id="age"
                type="number"
                placeholder="e.g., 55"
                value={age}
                onChange={(e) => setAge(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="gender">Gender (optional)</Label>
              <select
                id="gender"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={gender}
                onChange={(e) => setGender(e.target.value)}
              >
                <option value="">Not specified</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>
          </div>

          {/* Generate button */}
          <Button
            onClick={generateDifferential}
            disabled={findings.length === 0 || isLoading}
            className="w-full sm:w-auto"
          >
            {isLoading ? (
              <Activity className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Stethoscope className="mr-2 h-4 w-4" />
            )}
            {isLoading ? "Generating..." : "Generate Differential"}
          </Button>

          {error && (
            <div className="text-sm text-red-600 flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          )}
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
                  Red Flags - Cannot Miss Diagnoses
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
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>
                    Ranked Differential ({result.total_candidates} candidates)
                  </CardTitle>
                  <CardDescription>
                    Processed in {result.processing_time_ms.toFixed(0)}ms
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {result.diagnoses.map((dx, idx) => (
                  <div
                    key={dx.name}
                    className="rounded-lg border p-4 transition-colors hover:bg-muted/50"
                  >
                    {/* Header row */}
                    <div
                      className="flex items-center gap-3 cursor-pointer"
                      onClick={() => toggleExpand(dx.name)}
                    >
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-sm shrink-0">
                        {idx + 1}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-semibold">{dx.name}</span>
                          <Badge className={urgencyStyles[dx.urgency] || "bg-gray-500 text-white"}>
                            {dx.urgency.replace("_", " ")}
                          </Badge>
                          <Badge variant="outline">{dx.domain}</Badge>
                        </div>
                        <div className="text-sm text-muted-foreground mt-1">
                          Probability: {(dx.probability * 100).toFixed(0)}% |
                          Evidence strength:{" "}
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

                    {/* Expanded details */}
                    {expandedDx.has(dx.name) && (
                      <div className="mt-4 pl-11 space-y-4">
                        {/* CER Citation */}
                        <div className="space-y-2">
                          <h4 className="font-medium text-sm">
                            Clinical Reasoning (CER)
                          </h4>
                          <p className="text-sm text-muted-foreground">
                            {dx.cer_citation.reasoning}
                          </p>

                          {dx.cer_citation.supporting_evidence.length > 0 && (
                            <div>
                              <span className="text-xs font-medium text-green-600">
                                Supporting:
                              </span>
                              <ul className="list-disc list-inside text-sm text-muted-foreground">
                                {dx.cer_citation.supporting_evidence.map(
                                  (e, i) => (
                                    <li key={i}>{e}</li>
                                  )
                                )}
                              </ul>
                            </div>
                          )}

                          {dx.cer_citation.opposing_evidence.length > 0 && (
                            <div>
                              <span className="text-xs font-medium text-red-600">
                                Opposing:
                              </span>
                              <ul className="list-disc list-inside text-sm text-muted-foreground">
                                {dx.cer_citation.opposing_evidence.map(
                                  (e, i) => (
                                    <li key={i}>{e}</li>
                                  )
                                )}
                              </ul>
                            </div>
                          )}
                        </div>

                        {/* Clinical Pearls */}
                        {dx.cer_citation.clinical_pearls.length > 0 && (
                          <div>
                            <h4 className="font-medium text-sm">
                              Clinical Pearls
                            </h4>
                            <ul className="list-disc list-inside text-sm text-muted-foreground">
                              {dx.cer_citation.clinical_pearls.map((p, i) => (
                                <li key={i}>{p}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Suggested Workup */}
                        {dx.suggested_workup.length > 0 && (
                          <div>
                            <h4 className="font-medium text-sm">
                              Suggested Workup
                            </h4>
                            <div className="flex flex-wrap gap-1.5 mt-1">
                              {dx.suggested_workup.map((w, i) => (
                                <Badge key={i} variant="outline" className="text-xs">
                                  {w}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Diagnostic Criteria */}
                        {dx.cer_citation.diagnostic_criteria.length > 0 && (
                          <div>
                            <h4 className="font-medium text-sm">
                              Diagnostic Criteria
                            </h4>
                            <ul className="list-disc list-inside text-sm text-muted-foreground">
                              {dx.cer_citation.diagnostic_criteria.map(
                                (c, i) => (
                                  <li key={i}>{c}</li>
                                )
                              )}
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
            <div className="grid gap-6 md:grid-cols-2">
              {result.suggested_history.length > 0 && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">
                      Additional History to Gather
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="list-disc list-inside text-sm space-y-1">
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
                    <ul className="list-disc list-inside text-sm space-y-1">
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
