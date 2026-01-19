"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
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
import { Progress } from "@/components/ui/progress";
import { Label } from "@/components/ui/label";
import {
  ArrowLeft,
  Target,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  CheckCircle,
  Clock,
  FileText,
  Activity,
  Calculator,
  ChevronDown,
  ChevronUp,
  Download,
  History,
  Plus,
  RefreshCw,
} from "lucide-react";

// Types
interface HCCCategory {
  code: string;
  description: string;
  category: string;
  rafValue: number;
  status: "captured" | "suspected" | "gap";
  icd10Code: string;
  lastCaptured: string | null;
  evidence: string[];
}

interface PatientHCCProfile {
  patientId: string;
  patientName: string;
  dateOfBirth: string;
  medicare: boolean;
  currentRAF: number;
  projectedRAF: number;
  currentHCCs: HCCCategory[];
  suspectedGaps: HCCCategory[];
  historicalHCCs: HCCCategory[];
  yearlyTrend: {
    year: number;
    raf: number;
    hccCount: number;
  }[];
}

// Mock patient data
const mockPatientProfile: PatientHCCProfile = {
  patientId: "P001",
  patientName: "John Smith",
  dateOfBirth: "1958-03-15",
  medicare: true,
  currentRAF: 1.245,
  projectedRAF: 1.912,
  currentHCCs: [
    {
      code: "HCC37",
      description: "Diabetes with Chronic Complications",
      category: "diabetes",
      rafValue: 0.302,
      status: "captured",
      icd10Code: "E11.9",
      lastCaptured: "2026-01-15",
      evidence: ["Type 2 diabetes documented in problem list", "HbA1c 8.2%"],
    },
    {
      code: "HCC85",
      description: "Heart Failure",
      category: "cardiovascular",
      rafValue: 0.323,
      status: "captured",
      icd10Code: "I50.22",
      lastCaptured: "2026-01-12",
      evidence: ["Chronic systolic heart failure", "EF 35% on echo"],
    },
    {
      code: "HCC18",
      description: "Diabetes with No Complications",
      category: "diabetes",
      rafValue: 0.105,
      status: "captured",
      icd10Code: "E11.9",
      lastCaptured: "2025-10-20",
      evidence: ["Type 2 diabetes on medication list"],
    },
  ],
  suspectedGaps: [
    {
      code: "HCC327",
      description: "Chronic Kidney Disease, Stage 4",
      category: "renal",
      rafValue: 0.237,
      status: "gap",
      icd10Code: "N18.4",
      lastCaptured: null,
      evidence: [
        "eGFR: 22 mL/min (Stage 4 threshold)",
        "Nephrology note: CKD Stage 4",
        "Currently coded as N18.9 (unspecified)",
      ],
    },
    {
      code: "HCC111",
      description: "Chronic Obstructive Pulmonary Disease",
      category: "respiratory",
      rafValue: 0.335,
      status: "suspected",
      icd10Code: "J44.1",
      lastCaptured: "2025-03-01",
      evidence: [
        "COPD documented in 2025",
        "Uses albuterol and Symbicort",
        "Needs recapture for 2026",
      ],
    },
    {
      code: "HCC48",
      description: "Morbid Obesity",
      category: "metabolic",
      rafValue: 0.250,
      status: "gap",
      icd10Code: "E66.01",
      lastCaptured: null,
      evidence: [
        "BMI: 41.2 kg/m2 documented",
        "Currently coded as E66.9 (unspecified)",
      ],
    },
  ],
  historicalHCCs: [
    {
      code: "HCC111",
      description: "Chronic Obstructive Pulmonary Disease",
      category: "respiratory",
      rafValue: 0.335,
      status: "captured",
      icd10Code: "J44.1",
      lastCaptured: "2025-03-01",
      evidence: ["COPD with exacerbation"],
    },
    {
      code: "HCC108",
      description: "Vascular Disease",
      category: "vascular",
      rafValue: 0.288,
      status: "captured",
      icd10Code: "I70.201",
      lastCaptured: "2024-11-15",
      evidence: ["Peripheral arterial disease"],
    },
  ],
  yearlyTrend: [
    { year: 2024, raf: 1.523, hccCount: 5 },
    { year: 2025, raf: 1.412, hccCount: 4 },
    { year: 2026, raf: 1.245, hccCount: 3 },
  ],
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

const getCategoryColor = (category: string): string => {
  const colors: Record<string, string> = {
    diabetes: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
    cardiovascular: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
    renal: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    respiratory: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200",
    metabolic: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
    neurological: "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200",
    psychiatric: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200",
    vascular: "bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-200",
    immune: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  };
  return colors[category] || "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
};

const getStatusBadge = (status: string) => {
  switch (status) {
    case "captured":
      return (
        <Badge variant="outline" className="border-green-500 text-green-600">
          <CheckCircle className="mr-1 h-3 w-3" />
          Captured
        </Badge>
      );
    case "suspected":
      return (
        <Badge variant="outline" className="border-yellow-500 text-yellow-600">
          <AlertCircle className="mr-1 h-3 w-3" />
          Needs Recapture
        </Badge>
      );
    case "gap":
      return (
        <Badge variant="outline" className="border-red-500 text-red-600">
          <Target className="mr-1 h-3 w-3" />
          Gap
        </Badge>
      );
    default:
      return null;
  }
};

// Annual payment per 1.0 RAF (approximate)
const ANNUAL_PMPM = 14400;

export default function PatientHCCAnalysisPage() {
  const params = useParams();
  const patientId = params.patientId as string;

  const [profile, setProfile] = useState<PatientHCCProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedGaps, setExpandedGaps] = useState<Set<string>>(new Set());
  const [whatIfRAF, setWhatIfRAF] = useState<number | null>(null);
  const [selectedGapsForWhatIf, setSelectedGapsForWhatIf] = useState<Set<string>>(new Set());

  useEffect(() => {
    // Simulate API call
    const loadProfile = async () => {
      setLoading(true);
      await new Promise((resolve) => setTimeout(resolve, 500));
      setProfile({ ...mockPatientProfile, patientId });
      setLoading(false);
    };
    loadProfile();
  }, [patientId]);

  const toggleGapExpanded = (code: string) => {
    const newExpanded = new Set(expandedGaps);
    if (newExpanded.has(code)) {
      newExpanded.delete(code);
    } else {
      newExpanded.add(code);
    }
    setExpandedGaps(newExpanded);
  };

  const toggleWhatIfGap = (code: string, rafValue: number) => {
    const newSelected = new Set(selectedGapsForWhatIf);
    if (newSelected.has(code)) {
      newSelected.delete(code);
      setWhatIfRAF((prev) => (prev || profile?.currentRAF || 0) - rafValue);
    } else {
      newSelected.add(code);
      setWhatIfRAF((prev) => (prev || profile?.currentRAF || 0) + rafValue);
    }
    setSelectedGapsForWhatIf(newSelected);
  };

  const resetWhatIf = () => {
    setSelectedGapsForWhatIf(new Set());
    setWhatIfRAF(null);
  };

  if (loading || !profile) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <RefreshCw className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  const totalGapRAF = profile.suspectedGaps.reduce((sum, g) => sum + g.rafValue, 0);
  const totalGapRevenue = totalGapRAF * ANNUAL_PMPM;
  const rafIncrease = profile.projectedRAF - profile.currentRAF;

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/billing/hcc">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              HCC Analysis: {profile.patientName}
            </h1>
            <p className="text-muted-foreground">
              Patient ID: {profile.patientId} | DOB:{" "}
              {new Date(profile.dateOfBirth).toLocaleDateString()} |{" "}
              {profile.medicare ? "Medicare Advantage" : "Commercial"}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Download className="mr-2 h-4 w-4" />
            Export Report
          </Button>
          <Button variant="outline">
            <History className="mr-2 h-4 w-4" />
            View History
          </Button>
        </div>
      </div>

      {/* RAF Score Overview */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="border-l-4 border-l-blue-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Current RAF Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{profile.currentRAF.toFixed(3)}</div>
            <p className="text-xs text-muted-foreground">
              {profile.currentHCCs.length} HCCs captured
            </p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-green-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Projected RAF</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <span className="text-3xl font-bold text-green-600">
                {profile.projectedRAF.toFixed(3)}
              </span>
              <TrendingUp className="h-5 w-5 text-green-600" />
            </div>
            <p className="text-xs text-muted-foreground">
              If all gaps captured (+{rafIncrease.toFixed(3)})
            </p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-purple-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">
              Revenue Opportunity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-purple-600">
              {formatCurrency(totalGapRevenue)}
            </div>
            <p className="text-xs text-muted-foreground">
              {profile.suspectedGaps.length} gaps identified
            </p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-orange-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">YoY RAF Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <span className="text-3xl font-bold text-orange-600">
                {(profile.yearlyTrend[1].raf - profile.yearlyTrend[2].raf).toFixed(3)}
              </span>
              <TrendingDown className="h-5 w-5 text-orange-600" />
            </div>
            <p className="text-xs text-muted-foreground">
              Decrease from prior year
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Current HCCs */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-500" />
              Current HCCs ({profile.currentHCCs.length})
            </CardTitle>
            <CardDescription>
              HCCs captured for the current measurement year
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {profile.currentHCCs.map((hcc) => (
                <div
                  key={hcc.code}
                  className="rounded-lg border p-3 bg-green-50/50 dark:bg-green-950/20"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono">
                          {hcc.code}
                        </Badge>
                        <span className={`rounded px-1.5 py-0.5 text-xs ${getCategoryColor(hcc.category)}`}>
                          {hcc.category}
                        </span>
                      </div>
                      <p className="mt-1 text-sm font-medium">{hcc.description}</p>
                      <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                        <code className="bg-muted px-1 rounded">{hcc.icd10Code}</code>
                        <span>|</span>
                        <span>Last: {hcc.lastCaptured}</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="text-lg font-bold text-green-600">
                        +{hcc.rafValue.toFixed(3)}
                      </span>
                      <p className="text-xs text-muted-foreground">RAF</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* HCC Gaps */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-5 w-5 text-red-500" />
              Suspected HCC Gaps ({profile.suspectedGaps.length})
            </CardTitle>
            <CardDescription>
              Potential HCCs supported by clinical evidence but not yet captured
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {profile.suspectedGaps.map((gap) => (
                <div
                  key={gap.code}
                  className={`rounded-lg border p-4 transition-all ${
                    selectedGapsForWhatIf.has(gap.code)
                      ? "border-purple-500 bg-purple-50 dark:bg-purple-950/30"
                      : "hover:border-blue-300"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge variant="outline" className="font-mono">
                          {gap.code}
                        </Badge>
                        <span className={`rounded px-1.5 py-0.5 text-xs ${getCategoryColor(gap.category)}`}>
                          {gap.category}
                        </span>
                        {getStatusBadge(gap.status)}
                      </div>
                      <p className="mt-2 font-medium">{gap.description}</p>
                      <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
                        <span>Recommended:</span>
                        <code className="bg-green-100 dark:bg-green-900 px-1.5 rounded font-mono">
                          {gap.icd10Code}
                        </code>
                        {gap.lastCaptured && (
                          <>
                            <span>|</span>
                            <span>Last captured: {gap.lastCaptured}</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="text-right ml-4">
                      <span className="text-xl font-bold text-green-600">
                        +{gap.rafValue.toFixed(3)}
                      </span>
                      <p className="text-sm text-muted-foreground">
                        {formatCurrency(gap.rafValue * ANNUAL_PMPM)}
                      </p>
                    </div>
                  </div>

                  {/* Evidence Toggle */}
                  <div className="mt-3 pt-3 border-t">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="p-0 h-auto"
                      onClick={() => toggleGapExpanded(gap.code)}
                    >
                      {expandedGaps.has(gap.code) ? (
                        <>
                          <ChevronUp className="mr-1 h-4 w-4" />
                          Hide Evidence
                        </>
                      ) : (
                        <>
                          <ChevronDown className="mr-1 h-4 w-4" />
                          Show Evidence ({gap.evidence.length})
                        </>
                      )}
                    </Button>

                    {expandedGaps.has(gap.code) && (
                      <div className="mt-3 space-y-2 animate-in slide-in-from-top-2">
                        {gap.evidence.map((ev, idx) => (
                          <div
                            key={idx}
                            className="flex items-start gap-2 text-sm"
                          >
                            <FileText className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
                            <span>{ev}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="mt-3 pt-3 border-t flex justify-between items-center">
                    <Button
                      variant={selectedGapsForWhatIf.has(gap.code) ? "default" : "outline"}
                      size="sm"
                      onClick={() => toggleWhatIfGap(gap.code, gap.rafValue)}
                    >
                      <Calculator className="mr-1 h-3 w-3" />
                      {selectedGapsForWhatIf.has(gap.code) ? "Remove from What-If" : "Add to What-If"}
                    </Button>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm">
                        Create Query
                      </Button>
                      <Button size="sm">
                        <Plus className="mr-1 h-3 w-3" />
                        Capture HCC
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* What-If Calculator */}
      <Card className="border-purple-200 dark:border-purple-800">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calculator className="h-5 w-5 text-purple-500" />
            RAF What-If Calculator
          </CardTitle>
          <CardDescription>
            Model the impact of capturing specific HCC gaps
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 md:grid-cols-4">
            <div className="space-y-2">
              <Label>Current RAF</Label>
              <div className="text-3xl font-bold">
                {profile.currentRAF.toFixed(3)}
              </div>
            </div>
            <div className="space-y-2">
              <Label>Selected Gaps</Label>
              <div className="text-3xl font-bold text-purple-600">
                {selectedGapsForWhatIf.size}
              </div>
              <p className="text-xs text-muted-foreground">
                +{Array.from(selectedGapsForWhatIf).reduce((sum, code) => {
                  const gap = profile.suspectedGaps.find((g) => g.code === code);
                  return sum + (gap?.rafValue || 0);
                }, 0).toFixed(3)} RAF
              </p>
            </div>
            <div className="space-y-2">
              <Label>Projected RAF</Label>
              <div className="text-3xl font-bold text-green-600">
                {(whatIfRAF || profile.currentRAF).toFixed(3)}
              </div>
            </div>
            <div className="space-y-2">
              <Label>Revenue Impact</Label>
              <div className="text-3xl font-bold text-green-600">
                {formatCurrency(
                  ((whatIfRAF || profile.currentRAF) - profile.currentRAF) *
                    ANNUAL_PMPM
                )}
              </div>
            </div>
          </div>

          {selectedGapsForWhatIf.size > 0 && (
            <div className="mt-4 pt-4 border-t flex items-center justify-between">
              <div className="flex flex-wrap gap-2">
                {Array.from(selectedGapsForWhatIf).map((code) => {
                  const gap = profile.suspectedGaps.find((g) => g.code === code);
                  return (
                    <Badge key={code} variant="secondary" className="gap-1">
                      {code}
                      <span className="text-green-600">
                        +{gap?.rafValue.toFixed(3)}
                      </span>
                    </Badge>
                  );
                })}
              </div>
              <Button variant="outline" size="sm" onClick={resetWhatIf}>
                Reset
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Historical Trend */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Historical HCC Trend
          </CardTitle>
          <CardDescription>
            Year-over-year RAF score and HCC count
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            {profile.yearlyTrend.map((year, idx) => (
              <div
                key={year.year}
                className={`rounded-lg border p-4 ${
                  idx === profile.yearlyTrend.length - 1
                    ? "border-blue-500 bg-blue-50/50 dark:bg-blue-950/20"
                    : ""
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-lg font-bold">{year.year}</span>
                  {idx === profile.yearlyTrend.length - 1 && (
                    <Badge>Current</Badge>
                  )}
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">RAF Score</span>
                    <span className="font-mono font-bold">
                      {year.raf.toFixed(3)}
                    </span>
                  </div>
                  <Progress value={(year.raf / 2) * 100} className="h-2" />
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">HCCs Captured</span>
                    <span className="font-bold">{year.hccCount}</span>
                  </div>
                  {idx < profile.yearlyTrend.length - 1 && (
                    <div className="flex justify-between text-sm pt-2 border-t">
                      <span className="text-muted-foreground">Change</span>
                      <span
                        className={`font-bold ${
                          profile.yearlyTrend[idx + 1].raf < year.raf
                            ? "text-red-600"
                            : "text-green-600"
                        }`}
                      >
                        {profile.yearlyTrend[idx + 1].raf < year.raf ? "" : "+"}
                        {(profile.yearlyTrend[idx + 1].raf - year.raf).toFixed(3)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Historical HCCs */}
          <div className="mt-6 pt-4 border-t">
            <h4 className="font-semibold mb-3 flex items-center gap-2">
              <History className="h-4 w-4" />
              Previously Captured HCCs (Not Yet Recaptured in 2026)
            </h4>
            <div className="grid gap-3 md:grid-cols-2">
              {profile.historicalHCCs.map((hcc) => (
                <div
                  key={hcc.code}
                  className="rounded-lg border p-3 bg-yellow-50/50 dark:bg-yellow-950/20"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono">
                          {hcc.code}
                        </Badge>
                        <Badge variant="outline" className="border-yellow-500 text-yellow-600">
                          <Clock className="mr-1 h-3 w-3" />
                          Needs Recapture
                        </Badge>
                      </div>
                      <p className="mt-1 text-sm font-medium">{hcc.description}</p>
                      <p className="text-xs text-muted-foreground">
                        Last captured: {hcc.lastCaptured}
                      </p>
                    </div>
                    <div className="text-right">
                      <span className="text-lg font-bold text-yellow-600">
                        +{hcc.rafValue.toFixed(3)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
