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
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  AlertCircle,
  Info,
  Search,
  Pill,
  Activity,
} from "lucide-react";

interface Contraindication {
  condition: string;
  severity: string;
  rationale: string;
}

interface DosingGuideline {
  population: string;
  adjustment: string;
  reason: string;
}

interface SafetyCheckResult {
  request_id: string;
  drug_name: string;
  normalized_name: string;
  overall_safety: string;
  contraindications: Contraindication[];
  warnings: string[];
  black_box_warnings: string[];
  dosing_guidelines: DosingGuideline[];
  pregnancy_category: string | null;
  lactation_safety: string | null;
  adverse_effects: string[];
  therapeutic_classes: string[];
  processing_time_ms: number;
}

const safetyStyles: Record<string, { badge: string; icon: typeof ShieldCheck }> = {
  safe: { badge: "bg-green-500 text-white", icon: ShieldCheck },
  caution: { badge: "bg-amber-500 text-white", icon: AlertTriangle },
  warning: { badge: "bg-orange-500 text-white", icon: AlertTriangle },
  contraindicated: { badge: "bg-red-600 text-white", icon: ShieldAlert },
};

export default function DrugSafetyPage() {
  const [drugName, setDrugName] = useState("");
  const [conditions, setConditions] = useState<string[]>([]);
  const [currentCondition, setCurrentCondition] = useState("");
  const [age, setAge] = useState("");
  const [pregnant, setPregnant] = useState(false);
  const [lactating, setLactating] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<SafetyCheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const addCondition = useCallback(() => {
    const trimmed = currentCondition.trim();
    if (trimmed && !conditions.includes(trimmed)) {
      setConditions([...conditions, trimmed]);
      setCurrentCondition("");
    }
  }, [currentCondition, conditions]);

  const removeCondition = (c: string) => {
    setConditions(conditions.filter((x) => x !== c));
  };

  const checkSafety = useCallback(async () => {
    if (!drugName.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const body = {
        drug_name: drugName.trim(),
        patient: {
          conditions,
          age: age ? parseInt(age) : undefined,
          pregnant,
          lactating,
        },
      };

      const response = await fetch("/api/drug-safety/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data: SafetyCheckResult = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsLoading(false);
    }
  }, [drugName, conditions, age, pregnant, lactating]);

  const SafetyIcon = result
    ? safetyStyles[result.overall_safety]?.icon || Info
    : Info;

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
            <Pill className="h-6 w-6" />
            Drug Safety Checker
          </h1>
          <p className="text-muted-foreground">
            Check drug safety with patient-specific contraindications and
            warnings
          </p>
        </div>
      </div>

      {/* Input */}
      <Card>
        <CardHeader>
          <CardTitle>Safety Check</CardTitle>
          <CardDescription>
            Enter a drug name and patient context
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Drug name */}
          <div>
            <Label htmlFor="drug">Drug Name</Label>
            <Input
              id="drug"
              placeholder="e.g., warfarin, metformin, lisinopril"
              value={drugName}
              onChange={(e) => setDrugName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") checkSafety();
              }}
            />
          </div>

          {/* Patient conditions */}
          <div>
            <Label>Patient Conditions (optional)</Label>
            <div className="flex gap-2">
              <Input
                placeholder="e.g., renal impairment, liver disease"
                value={currentCondition}
                onChange={(e) => setCurrentCondition(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addCondition();
                  }
                }}
              />
              <Button onClick={addCondition} size="sm" variant="outline">
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            {conditions.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {conditions.map((c) => (
                  <Badge key={c} variant="secondary" className="px-3 py-1">
                    {c}
                    <button
                      onClick={() => removeCondition(c)}
                      className="ml-2 hover:text-destructive"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Demographics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <Label htmlFor="age">Age</Label>
              <Input
                id="age"
                type="number"
                placeholder="Age"
                value={age}
                onChange={(e) => setAge(e.target.value)}
              />
            </div>
            <div className="flex items-end gap-2">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={pregnant}
                  onChange={(e) => setPregnant(e.target.checked)}
                  className="rounded"
                />
                Pregnant
              </label>
            </div>
            <div className="flex items-end gap-2">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={lactating}
                  onChange={(e) => setLactating(e.target.checked)}
                  className="rounded"
                />
                Lactating
              </label>
            </div>
          </div>

          <Button
            onClick={checkSafety}
            disabled={!drugName.trim() || isLoading}
          >
            {isLoading ? (
              <Activity className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Search className="mr-2 h-4 w-4" />
            )}
            {isLoading ? "Checking..." : "Check Safety"}
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
          {/* Overall Safety */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <SafetyIcon className="h-5 w-5" />
                  {result.normalized_name}
                </CardTitle>
                <Badge
                  className={
                    safetyStyles[result.overall_safety]?.badge ||
                    "bg-gray-500 text-white"
                  }
                >
                  {result.overall_safety.toUpperCase()}
                </Badge>
              </div>
              {result.therapeutic_classes.length > 0 && (
                <CardDescription>
                  Class: {result.therapeutic_classes.join(", ")}
                </CardDescription>
              )}
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Processed in {result.processing_time_ms.toFixed(0)}ms
            </CardContent>
          </Card>

          {/* Black Box Warnings */}
          {result.black_box_warnings.length > 0 && (
            <Card className="border-red-300 dark:border-red-900">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-red-600">
                  <ShieldAlert className="h-5 w-5" />
                  Black Box Warnings
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {result.black_box_warnings.map((w, i) => (
                    <li
                      key={i}
                      className="text-sm flex items-start gap-2 text-red-700 dark:text-red-400"
                    >
                      <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                      {w}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Contraindications */}
          {result.contraindications.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Contraindications</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {result.contraindications.map((c, i) => (
                    <div key={i} className="rounded-lg border p-3">
                      <div className="flex items-center gap-2">
                        <Badge variant="destructive">{c.severity}</Badge>
                        <span className="font-medium text-sm">
                          {c.condition}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        {c.rationale}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Warnings & Adverse Effects */}
          <div className="grid gap-6 md:grid-cols-2">
            {result.warnings.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                    Warnings
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="list-disc list-inside text-sm space-y-1">
                    {result.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}

            {result.adverse_effects.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Cautions</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="list-disc list-inside text-sm space-y-1">
                    {result.adverse_effects.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Dosing Guidelines */}
          {result.dosing_guidelines.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Dosing Guidelines</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {result.dosing_guidelines.map((d, i) => (
                    <div key={i} className="rounded-lg border p-3">
                      <div className="font-medium text-sm">{d.population}</div>
                      <p className="text-sm text-muted-foreground">
                        {d.adjustment}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Reason: {d.reason}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Pregnancy/Lactation */}
          {(result.pregnancy_category || result.lactation_safety) && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">
                  Special Populations
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {result.pregnancy_category && (
                  <div className="text-sm">
                    <span className="font-medium">Pregnancy: </span>
                    {result.pregnancy_category}
                  </div>
                )}
                {result.lactation_safety && (
                  <div className="text-sm">
                    <span className="font-medium">Lactation: </span>
                    {result.lactation_safety}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
