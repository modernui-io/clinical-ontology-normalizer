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
  ArrowLeft,
  Plus,
  X,
  TrendingUp,
  AlertCircle,
  DollarSign,
  Target,
  Activity,
} from "lucide-react";

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

const confidenceColors: Record<string, string> = {
  high: "bg-green-100 text-green-800",
  medium: "bg-amber-100 text-amber-800",
  low: "bg-red-100 text-red-800",
};

export default function HCCAnalysisPage() {
  const [patientId, setPatientId] = useState("");
  const [icd10Codes, setIcd10Codes] = useState<string[]>([]);
  const [currentCode, setCurrentCode] = useState("");
  const [clinicalNotes, setClinicalNotes] = useState("");
  const [age, setAge] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<HCCAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  const analyze = useCallback(async () => {
    if (!patientId.trim()) return;
    setIsLoading(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        patient_id: patientId.trim(),
        icd10_codes: icd10Codes,
      };
      if (clinicalNotes.trim()) body.clinical_notes = clinicalNotes.trim();
      if (age) body.age = parseInt(age);

      const res = await fetch("/api/v1/hcc-analysis/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.message || "Analysis failed");
      }
      const data: HCCAnalysisResult = await res.json();
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setIsLoading(false);
    }
  }, [patientId, icd10Codes, clinicalNotes, age]);

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <div className="flex items-center gap-4 mb-6">
        <Link href="/clinical">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-1" /> Clinical
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">HCC Gap Analysis</h1>
          <p className="text-muted-foreground">
            Identify HCC coding opportunities and RAF score impact
          </p>
        </div>
      </div>

      {/* Input Form */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">Patient Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label>Patient ID *</Label>
              <Input
                placeholder="Enter patient identifier"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
              />
            </div>
            <div>
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

          <div>
            <Label>Current ICD-10 Codes</Label>
            <div className="flex gap-2 mb-2">
              <Input
                placeholder="Add ICD-10 code (e.g., E11.9)"
                value={currentCode}
                onChange={(e) => setCurrentCode(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCode())}
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

          <div>
            <Label>Clinical Notes (optional)</Label>
            <textarea
              className="w-full mt-1 p-3 border rounded-md text-sm min-h-[100px] resize-y"
              placeholder="Paste clinical notes for NLP-based gap detection..."
              value={clinicalNotes}
              onChange={(e) => setClinicalNotes(e.target.value)}
            />
          </div>

          <Button
            onClick={analyze}
            disabled={isLoading || !patientId.trim()}
            className="w-full md:w-auto"
          >
            <Target className="h-4 w-4 mr-2" />
            {isLoading ? "Analyzing..." : "Analyze HCC Gaps"}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <Card className="mb-6 border-red-200">
          <CardContent className="pt-6">
            <p className="text-red-600 flex items-center gap-2">
              <AlertCircle className="h-4 w-4" /> {error}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {result && (
        <>
          {/* RAF Score Summary */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <Card>
              <CardContent className="pt-4 text-center">
                <p className="text-sm text-muted-foreground">Current RAF</p>
                <p className="text-2xl font-bold">{result.current_raf_score.toFixed(3)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 text-center">
                <p className="text-sm text-muted-foreground">Potential RAF</p>
                <p className="text-2xl font-bold text-green-600">
                  {result.potential_raf_score.toFixed(3)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 text-center">
                <p className="text-sm text-muted-foreground">RAF Gap</p>
                <p className="text-2xl font-bold text-amber-600 flex items-center justify-center gap-1">
                  <TrendingUp className="h-5 w-5" />
                  +{result.raf_gap.toFixed(3)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 text-center">
                <p className="text-sm text-muted-foreground">Revenue Impact</p>
                <p className="text-2xl font-bold text-green-600 flex items-center justify-center gap-1">
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
            <Card className="mb-6">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Activity className="h-5 w-5" />
                  Capture Opportunities ({result.opportunities.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {result.opportunities.map((opp) => (
                    <div
                      key={opp.hcc_code}
                      className="p-4 border rounded-lg space-y-2"
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
                          <p className="text-sm text-muted-foreground mt-1">
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
                            <Badge key={code} variant="secondary" className="text-xs font-mono">
                              {code}
                            </Badge>
                          ))}
                        </div>
                      )}

                      {opp.evidence.length > 0 && (
                        <div className="mt-2 pt-2 border-t">
                          <p className="text-xs text-muted-foreground mb-1">Evidence:</p>
                          {opp.evidence.map((ev, i) => (
                            <p key={i} className="text-xs text-muted-foreground">
                              [{ev.source}] {ev.text} (conf: {(ev.confidence * 100).toFixed(0)}%)
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
                <ol className="list-decimal list-inside space-y-2">
                  {result.priority_actions.map((action, i) => (
                    <li key={i} className="text-sm">{action}</li>
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
