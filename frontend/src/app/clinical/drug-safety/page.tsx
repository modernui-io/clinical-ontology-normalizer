"use client";

/**
 * Drug Safety — Search, Profile, Safety Check, and Interaction Checker
 *
 * Connects to POST /drug-safety/check (patient-context safety check),
 * POST /drug-safety/interactions (drug-drug interactions),
 * GET /drug-safety/profile/{name}, GET /drug-safety/search, GET /drug-safety/stats.
 * Falls back to demo data when API is unavailable.
 */

import { useState, useEffect } from "react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertTriangle,
  AlertCircle,
  Pill,
  Search,
  Loader2,
  ShieldCheck,
  ArrowLeft,
  FileText,
  Info,
  CheckCircle2,
  UserCheck,
} from "lucide-react";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Auth helpers (same pattern as openehr page)
// ---------------------------------------------------------------------------

const API_BASE = "/api/drug-safety";

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
// Types (mirrors backend schemas)
// ---------------------------------------------------------------------------

interface ContraindicationItem {
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
  contraindications: ContraindicationItem[];
  warnings: string[];
  black_box_warnings: string[];
  dosing_guidelines: DosingGuideline[];
  pregnancy_category: string | null;
  lactation_safety: string | null;
  adverse_effects: string[];
  therapeutic_classes: string[];
  processing_time_ms: number;
}

interface DrugProfile {
  drug_name: string;
  generic_name: string;
  drug_class: string;
  contraindications: ContraindicationItem[];
  warnings: string[];
  black_box_warnings: string[];
  dosing_guidelines: DosingGuideline[];
  pregnancy_category: string | null;
  lactation_safety: string | null;
  common_adverse_effects: string[];
  serious_adverse_effects: string[];
  max_daily_dose: string | null;
}

interface DrugSearchResult {
  drug_name: string;
  generic_name: string;
  drug_class: string;
}

interface InteractionItem {
  drug_a: string;
  drug_b: string;
  severity: string;
  description: string;
  mechanism: string;
  clinical_effect: string;
  management: string;
}

interface InteractionResult {
  request_id: string;
  drugs_checked: string[];
  total_interactions: number;
  major_count: number;
  moderate_count: number;
  minor_count: number;
  interactions: InteractionItem[];
  processing_time_ms: number;
}

interface StatsResponse {
  total_profiles: number;
  categories: Record<string, number>;
}

// ---------------------------------------------------------------------------
// Demo fallback data
// ---------------------------------------------------------------------------

function demoSafetyCheck(drug: string): SafetyCheckResult {
  return {
    request_id: "demo-001",
    drug_name: drug,
    normalized_name: drug.toLowerCase(),
    overall_safety: "caution",
    contraindications: [
      { condition: "Active bleeding", severity: "absolute", rationale: "Risk of hemorrhage" },
      { condition: "Severe hepatic impairment", severity: "relative", rationale: "Impaired metabolism" },
    ],
    warnings: [
      "Monitor INR regularly when used with anticoagulants",
      "May cause GI bleeding with prolonged use",
    ],
    black_box_warnings: ["Increased risk of serious cardiovascular thrombotic events"],
    dosing_guidelines: [
      { population: "Elderly (>65)", adjustment: "Start at lower dose", reason: "Increased bleeding risk" },
      { population: "Renal impairment", adjustment: "Reduce dose by 50%", reason: "Reduced clearance" },
    ],
    pregnancy_category: "D",
    lactation_safety: "Caution advised",
    adverse_effects: ["Nausea", "Headache", "Dizziness", "GI upset", "Bruising"],
    therapeutic_classes: ["Anticoagulant", "Cardiovascular"],
    processing_time_ms: 42,
  };
}

function demoInteractionResult(drugs: string[]): InteractionResult {
  return {
    request_id: "demo-002",
    drugs_checked: drugs,
    total_interactions: 2,
    major_count: 1,
    moderate_count: 1,
    minor_count: 0,
    interactions: [
      {
        drug_a: drugs[0] || "warfarin",
        drug_b: drugs[1] || "aspirin",
        severity: "major",
        description: "Increased risk of bleeding when combined",
        mechanism: "Both drugs affect coagulation through different pathways",
        clinical_effect: "Significantly elevated bleeding risk",
        management: "Monitor INR closely; consider alternative analgesic",
      },
      {
        drug_a: drugs[0] || "warfarin",
        drug_b: drugs[1] || "aspirin",
        severity: "moderate",
        description: "Potential for increased GI mucosal injury",
        mechanism: "Additive effect on gastric mucosa",
        clinical_effect: "Increased risk of GI bleeding",
        management: "Consider PPI co-therapy for gastroprotection",
      },
    ],
    processing_time_ms: 38,
  };
}

function demoProfile(name: string): DrugProfile {
  return {
    drug_name: name,
    generic_name: name.toLowerCase(),
    drug_class: "Anticoagulant",
    contraindications: [
      { condition: "Active bleeding", severity: "absolute", rationale: "Risk of hemorrhage" },
    ],
    warnings: ["Monitor INR regularly", "Risk of hemorrhage in elderly patients"],
    black_box_warnings: [],
    dosing_guidelines: [
      { population: "Adults", adjustment: "5mg daily initial", reason: "Standard starting dose" },
    ],
    pregnancy_category: "X",
    lactation_safety: "Compatible with breastfeeding",
    common_adverse_effects: ["Bruising", "Nausea", "Hair loss"],
    serious_adverse_effects: ["Major hemorrhage", "Skin necrosis"],
    max_daily_dose: "10mg",
  };
}

function demoSearchResults(q: string): DrugSearchResult[] {
  const allDrugs: DrugSearchResult[] = [
    { drug_name: "Warfarin", generic_name: "warfarin sodium", drug_class: "Anticoagulant" },
    { drug_name: "Aspirin", generic_name: "acetylsalicylic acid", drug_class: "NSAID / Antiplatelet" },
    { drug_name: "Metformin", generic_name: "metformin hydrochloride", drug_class: "Biguanide" },
    { drug_name: "Lisinopril", generic_name: "lisinopril", drug_class: "ACE Inhibitor" },
    { drug_name: "Atorvastatin", generic_name: "atorvastatin calcium", drug_class: "Statin" },
    { drug_name: "Metoprolol", generic_name: "metoprolol tartrate", drug_class: "Beta-Blocker" },
  ];
  const lower = q.toLowerCase();
  return allDrugs.filter(
    (d) => d.drug_name.toLowerCase().includes(lower) || d.generic_name.includes(lower),
  );
}

// ---------------------------------------------------------------------------
// Severity badge helper
// ---------------------------------------------------------------------------

function SeverityBadge({ severity }: { severity: string }) {
  const s = severity.toLowerCase();
  const variant =
    s === "major" || s === "absolute"
      ? "destructive"
      : s === "moderate" || s === "relative"
        ? "secondary"
        : "outline";
  return (
    <Badge variant={variant} className="capitalize text-xs">
      {severity}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function DrugSafetyPage() {
  const [demoMode, setDemoMode] = useState(false);
  const [stats, setStats] = useState<StatsResponse | null>(null);

  // Tab 1 — Safety Check
  const [checkDrug, setCheckDrug] = useState("");
  const [checkAge, setCheckAge] = useState("");
  const [checkConditions, setCheckConditions] = useState("");
  const [checkMedications, setCheckMedications] = useState("");
  const [checkPregnant, setCheckPregnant] = useState(false);
  const [checkLoading, setCheckLoading] = useState(false);
  const [checkResult, setCheckResult] = useState<SafetyCheckResult | null>(null);

  // Tab 2 — Interactions
  const [interMeds, setInterMeds] = useState("");
  const [interLoading, setInterLoading] = useState(false);
  const [interResult, setInterResult] = useState<InteractionResult | null>(null);

  // Tab 3 — Search / Profile
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<DrugSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [selectedProfile, setSelectedProfile] = useState<DrugProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);

  // Fetch stats on mount
  useEffect(() => {
    const token = getStoredToken();
    fetch(`${API_BASE}/stats`, { headers: authHeaders(token) })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => setStats(d))
      .catch(() => setStats({ total_profiles: 247, categories: { Anticoagulant: 18, NSAID: 24, Antihypertensive: 31, Antidiabetic: 22 } }));
  }, []);

  // ------- Safety Check -------
  const handleSafetyCheck = async () => {
    if (!checkDrug.trim()) {
      toast.error("Drug name is required");
      return;
    }
    setCheckLoading(true);
    setCheckResult(null);
    setDemoMode(false);
    try {
      const token = getStoredToken();
      const res = await fetch(`${API_BASE}/check`, {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({
          drug_name: checkDrug.trim(),
          patient: {
            age: checkAge ? parseInt(checkAge) : undefined,
            conditions: checkConditions ? checkConditions.split(",").map((s) => s.trim()).filter(Boolean) : [],
            medications: checkMedications ? checkMedications.split(",").map((s) => s.trim()).filter(Boolean) : [],
            pregnant: checkPregnant,
          },
        }),
      });
      if (!res.ok) throw new Error();
      const data: SafetyCheckResult = await res.json();
      setCheckResult(data);
      toast.success(`Safety check complete — ${data.overall_safety}`);
    } catch {
      setDemoMode(true);
      setCheckResult(demoSafetyCheck(checkDrug.trim()));
      toast.info("Demo mode — API unavailable");
    } finally {
      setCheckLoading(false);
    }
  };

  // ------- Interaction Check -------
  const handleInteractions = async () => {
    const meds = interMeds
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (meds.length < 2) {
      toast.error("Enter at least 2 medications separated by commas");
      return;
    }
    setInterLoading(true);
    setInterResult(null);
    setDemoMode(false);
    try {
      const token = getStoredToken();
      const res = await fetch(`${API_BASE}/interactions`, {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ medications: meds }),
      });
      if (!res.ok) throw new Error();
      const data: InteractionResult = await res.json();
      setInterResult(data);
      toast.success(`Found ${data.total_interactions} interaction(s)`);
    } catch {
      setDemoMode(true);
      setInterResult(demoInteractionResult(meds));
      toast.info("Demo mode — API unavailable");
    } finally {
      setInterLoading(false);
    }
  };

  // ------- Search -------
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearchLoading(true);
    setSearchResults([]);
    setDemoMode(false);
    try {
      const token = getStoredToken();
      const res = await fetch(
        `${API_BASE}/search?q=${encodeURIComponent(searchQuery.trim())}`,
        { headers: authHeaders(token) },
      );
      if (!res.ok) throw new Error();
      const data = await res.json();
      setSearchResults(data.profiles || []);
    } catch {
      setDemoMode(true);
      setSearchResults(demoSearchResults(searchQuery.trim()));
    } finally {
      setSearchLoading(false);
    }
  };

  // ------- Profile -------
  const handleProfile = async (name: string) => {
    setProfileLoading(true);
    setSelectedProfile(null);
    try {
      const token = getStoredToken();
      const res = await fetch(`${API_BASE}/profile/${encodeURIComponent(name)}`, {
        headers: authHeaders(token),
      });
      if (!res.ok) throw new Error();
      setSelectedProfile(await res.json());
    } catch {
      setDemoMode(true);
      setSelectedProfile(demoProfile(name));
    } finally {
      setProfileLoading(false);
    }
  };

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
            <Pill className="h-7 w-7" />
            Drug Safety
          </h1>
          <p className="text-muted-foreground">
            Safety checks, interaction screening, and drug profiles
          </p>
        </div>
      </div>

      {/* Demo mode banner */}
      {demoMode && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>
            <strong>Client-side demo mode</strong> — API is unavailable.
            Showing simulated results.
          </span>
        </div>
      )}

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold tabular-nums">{stats.total_profiles}</p>
              <p className="text-xs text-muted-foreground">Total Profiles</p>
            </CardContent>
          </Card>
          {Object.entries(stats.categories)
            .slice(0, 4)
            .map(([cat, count]) => (
              <Card key={cat}>
                <CardContent className="p-4 text-center">
                  <p className="text-2xl font-bold tabular-nums">{count}</p>
                  <p className="text-xs capitalize text-muted-foreground">{cat}</p>
                </CardContent>
              </Card>
            ))}
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="safety-check" className="space-y-4">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="safety-check" className="gap-2">
            <UserCheck className="h-4 w-4" />
            Safety Check
          </TabsTrigger>
          <TabsTrigger value="interactions" className="gap-2">
            <ShieldCheck className="h-4 w-4" />
            Interactions
          </TabsTrigger>
          <TabsTrigger value="search" className="gap-2">
            <Search className="h-4 w-4" />
            Search &amp; Profile
          </TabsTrigger>
        </TabsList>

        {/* ================================================================
            TAB 1 — Safety Check (patient context)
            ================================================================ */}
        <TabsContent value="safety-check" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Patient-Context Safety Check</CardTitle>
              <CardDescription>
                Enter a drug and optional patient demographics to get
                contraindications, warnings, dosing adjustments, and pregnancy safety.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="check-drug">Drug Name</Label>
                  <Input
                    id="check-drug"
                    placeholder="e.g., warfarin"
                    value={checkDrug}
                    onChange={(e) => setCheckDrug(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="check-age">Age</Label>
                  <Input
                    id="check-age"
                    type="number"
                    placeholder="e.g., 68"
                    value={checkAge}
                    onChange={(e) => setCheckAge(e.target.value)}
                  />
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="check-conditions">
                    Conditions <span className="text-muted-foreground">(comma-separated)</span>
                  </Label>
                  <Input
                    id="check-conditions"
                    placeholder="e.g., hypertension, CKD"
                    value={checkConditions}
                    onChange={(e) => setCheckConditions(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="check-meds">
                    Current Medications <span className="text-muted-foreground">(comma-separated)</span>
                  </Label>
                  <Input
                    id="check-meds"
                    placeholder="e.g., aspirin, lisinopril"
                    value={checkMedications}
                    onChange={(e) => setCheckMedications(e.target.value)}
                  />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  id="check-pregnant"
                  type="checkbox"
                  checked={checkPregnant}
                  onChange={(e) => setCheckPregnant(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300"
                />
                <Label htmlFor="check-pregnant" className="text-sm">
                  Pregnant
                </Label>
              </div>

              <div className="flex gap-2">
                <Button onClick={handleSafetyCheck} disabled={checkLoading}>
                  {checkLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <ShieldCheck className="mr-2 h-4 w-4" />
                  )}
                  Run Safety Check
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setCheckDrug("warfarin");
                    setCheckAge("72");
                    setCheckConditions("atrial fibrillation, hypertension");
                    setCheckMedications("aspirin, lisinopril");
                    setCheckPregnant(false);
                  }}
                >
                  Load Demo
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Safety Check Results */}
          {checkResult && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Pill className="h-5 w-5" />
                  {checkResult.drug_name}
                  <Badge
                    variant={
                      checkResult.overall_safety === "safe"
                        ? "secondary"
                        : checkResult.overall_safety === "caution"
                          ? "outline"
                          : "destructive"
                    }
                    className="ml-2 capitalize"
                  >
                    {checkResult.overall_safety}
                  </Badge>
                  <span className="ml-auto text-xs font-normal text-muted-foreground">
                    {checkResult.processing_time_ms}ms
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                {/* Black box warnings */}
                {checkResult.black_box_warnings.length > 0 && (
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2 text-red-600">
                      <AlertTriangle className="h-4 w-4" />
                      Black Box Warnings
                    </Label>
                    {checkResult.black_box_warnings.map((w, i) => (
                      <div
                        key={i}
                        className="rounded-md border-2 border-red-400 bg-red-50 p-3 text-sm text-red-800 dark:border-red-700 dark:bg-red-950 dark:text-red-200"
                      >
                        {w}
                      </div>
                    ))}
                  </div>
                )}

                {/* Contraindications */}
                {checkResult.contraindications.length > 0 && (
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <AlertCircle className="h-4 w-4 text-red-500" />
                      Contraindications
                    </Label>
                    {checkResult.contraindications.map((ci, i) => (
                      <div key={i} className="flex items-start gap-3 rounded-md border bg-muted/50 p-3 text-sm">
                        <SeverityBadge severity={ci.severity} />
                        <div>
                          <p className="font-medium">{ci.condition}</p>
                          <p className="text-muted-foreground">{ci.rationale}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Warnings */}
                {checkResult.warnings.length > 0 && (
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-amber-500" />
                      Warnings
                    </Label>
                    {checkResult.warnings.map((w, i) => (
                      <div
                        key={i}
                        className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-950"
                      >
                        {w}
                      </div>
                    ))}
                  </div>
                )}

                {/* Dosing guidelines */}
                {checkResult.dosing_guidelines.length > 0 && (
                  <div className="space-y-2">
                    <Label>Dosing Guidelines</Label>
                    <div className="overflow-x-auto rounded-md border">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b bg-muted/50">
                            <th className="px-4 py-2 text-left font-medium">Population</th>
                            <th className="px-4 py-2 text-left font-medium">Adjustment</th>
                            <th className="px-4 py-2 text-left font-medium">Reason</th>
                          </tr>
                        </thead>
                        <tbody>
                          {checkResult.dosing_guidelines.map((dg, i) => (
                            <tr key={i} className="border-b last:border-0">
                              <td className="px-4 py-2 font-medium">{dg.population}</td>
                              <td className="px-4 py-2">{dg.adjustment}</td>
                              <td className="px-4 py-2 text-muted-foreground">{dg.reason}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Pregnancy + Lactation */}
                <div className="grid gap-3 sm:grid-cols-2">
                  {checkResult.pregnancy_category && (
                    <div className="rounded-md border p-3">
                      <p className="text-xs font-medium text-muted-foreground">Pregnancy Category</p>
                      <p className="text-lg font-bold">{checkResult.pregnancy_category}</p>
                    </div>
                  )}
                  {checkResult.lactation_safety && (
                    <div className="rounded-md border p-3">
                      <p className="text-xs font-medium text-muted-foreground">Lactation Safety</p>
                      <p className="text-lg font-bold">{checkResult.lactation_safety}</p>
                    </div>
                  )}
                </div>

                {/* Adverse effects */}
                {checkResult.adverse_effects.length > 0 && (
                  <div className="space-y-2">
                    <Label>Adverse Effects</Label>
                    <div className="flex flex-wrap gap-2">
                      {checkResult.adverse_effects.map((ae, i) => (
                        <Badge key={i} variant="secondary" className="text-xs">
                          {ae}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ================================================================
            TAB 2 — Drug-Drug Interactions
            ================================================================ */}
        <TabsContent value="interactions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Drug-Drug Interaction Checker</CardTitle>
              <CardDescription>
                Enter two or more medications to check for interactions, severity,
                and management recommendations.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="inter-meds">
                  Medications <span className="text-muted-foreground">(comma-separated, min 2)</span>
                </Label>
                <Input
                  id="inter-meds"
                  placeholder="e.g., warfarin, aspirin, metformin"
                  value={interMeds}
                  onChange={(e) => setInterMeds(e.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <Button onClick={handleInteractions} disabled={interLoading}>
                  {interLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <ShieldCheck className="mr-2 h-4 w-4" />
                  )}
                  Check Interactions
                </Button>
                <Button variant="outline" onClick={() => setInterMeds("warfarin, aspirin")}>
                  Load Demo
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Interaction Results */}
          {interResult && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  Interaction Results
                  <span className="ml-auto text-xs font-normal text-muted-foreground">
                    {interResult.processing_time_ms}ms
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Summary counts */}
                <div className="grid grid-cols-4 gap-3">
                  <Card>
                    <CardContent className="p-4 text-center">
                      <p className="text-2xl font-bold tabular-nums">{interResult.total_interactions}</p>
                      <p className="text-xs text-muted-foreground">Total</p>
                    </CardContent>
                  </Card>
                  <Card className="border-red-200 dark:border-red-900">
                    <CardContent className="p-4 text-center">
                      <p className="text-2xl font-bold tabular-nums text-red-600">{interResult.major_count}</p>
                      <p className="text-xs text-muted-foreground">Major</p>
                    </CardContent>
                  </Card>
                  <Card className="border-amber-200 dark:border-amber-900">
                    <CardContent className="p-4 text-center">
                      <p className="text-2xl font-bold tabular-nums text-amber-600">{interResult.moderate_count}</p>
                      <p className="text-xs text-muted-foreground">Moderate</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-4 text-center">
                      <p className="text-2xl font-bold tabular-nums">{interResult.minor_count}</p>
                      <p className="text-xs text-muted-foreground">Minor</p>
                    </CardContent>
                  </Card>
                </div>

                {/* Interaction details */}
                {interResult.interactions.length > 0 ? (
                  <div className="space-y-3">
                    {interResult.interactions.map((ix, i) => {
                      const borderColor =
                        ix.severity === "major"
                          ? "border-l-red-500"
                          : ix.severity === "moderate"
                            ? "border-l-amber-500"
                            : "border-l-blue-500";
                      return (
                        <div key={i} className={`rounded-md border border-l-4 ${borderColor} p-4 space-y-2`}>
                          <div className="flex items-center gap-2">
                            <SeverityBadge severity={ix.severity} />
                            <span className="text-sm font-medium">
                              {ix.drug_a} + {ix.drug_b}
                            </span>
                          </div>
                          <p className="text-sm">{ix.description}</p>
                          {ix.mechanism && (
                            <p className="text-xs text-muted-foreground">
                              <strong>Mechanism:</strong> {ix.mechanism}
                            </p>
                          )}
                          {ix.clinical_effect && (
                            <p className="text-xs text-muted-foreground">
                              <strong>Clinical Effect:</strong> {ix.clinical_effect}
                            </p>
                          )}
                          {ix.management && (
                            <div className="mt-2 rounded bg-muted p-2 text-xs">
                              <strong>Management:</strong> {ix.management}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="py-8 text-center">
                    <CheckCircle2 className="mx-auto mb-2 h-8 w-8 text-green-500" />
                    <p className="text-sm font-medium">No interactions found</p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ================================================================
            TAB 3 — Search & Profile
            ================================================================ */}
        <TabsContent value="search" className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            {/* Search panel */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Search className="h-5 w-5" />
                  Drug Search
                </CardTitle>
                <CardDescription>Search for drug profiles by name</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <Input
                    placeholder="e.g., warfarin"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                  />
                  <Button onClick={handleSearch} disabled={searchLoading} size="icon">
                    {searchLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Search className="h-4 w-4" />
                    )}
                  </Button>
                </div>

                {searchResults.length > 0 && (
                  <div className="max-h-72 space-y-2 overflow-y-auto">
                    {searchResults.map((r, i) => (
                      <button
                        key={i}
                        onClick={() => handleProfile(r.drug_name)}
                        className="w-full rounded-lg border bg-card p-3 text-left transition-colors hover:bg-accent"
                      >
                        <p className="font-medium">{r.drug_name}</p>
                        <p className="text-xs text-muted-foreground">
                          {r.generic_name} — {r.drug_class}
                        </p>
                      </button>
                    ))}
                  </div>
                )}

                {!searchLoading && searchQuery && searchResults.length === 0 && (
                  <div className="py-8 text-center text-muted-foreground">
                    <Info className="mx-auto mb-2 h-8 w-8 opacity-50" />
                    <p className="text-sm">No drugs found</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Profile panel */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  Drug Profile
                </CardTitle>
              </CardHeader>
              <CardContent>
                {profileLoading && (
                  <div className="py-12 text-center">
                    <Loader2 className="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
                  </div>
                )}

                {selectedProfile && !profileLoading && (
                  <div className="space-y-4">
                    <div>
                      <h3 className="flex items-center gap-2 text-lg font-semibold">
                        {selectedProfile.drug_name}
                        {selectedProfile.black_box_warnings.length > 0 && (
                          <Badge variant="destructive" className="text-xs">
                            <AlertTriangle className="mr-1 h-3 w-3" />
                            Black Box
                          </Badge>
                        )}
                      </h3>
                      <p className="text-sm text-muted-foreground">
                        {selectedProfile.generic_name} — {selectedProfile.drug_class}
                      </p>
                    </div>

                    {selectedProfile.warnings.length > 0 && (
                      <div className="space-y-1">
                        <Label className="flex items-center gap-2">
                          <AlertTriangle className="h-4 w-4 text-amber-500" />
                          Warnings
                        </Label>
                        {selectedProfile.warnings.map((w, i) => (
                          <div
                            key={i}
                            className="rounded-md border border-amber-200 bg-amber-50 p-2 text-sm dark:border-amber-800 dark:bg-amber-950"
                          >
                            {w}
                          </div>
                        ))}
                      </div>
                    )}

                    {selectedProfile.common_adverse_effects.length > 0 && (
                      <div className="space-y-1">
                        <Label>Common Adverse Effects</Label>
                        <div className="flex flex-wrap gap-1.5">
                          {selectedProfile.common_adverse_effects.map((ae, i) => (
                            <Badge key={i} variant="secondary" className="text-xs">
                              {ae}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {selectedProfile.serious_adverse_effects.length > 0 && (
                      <div className="space-y-1">
                        <Label className="text-red-600">Serious Adverse Effects</Label>
                        <div className="flex flex-wrap gap-1.5">
                          {selectedProfile.serious_adverse_effects.map((ae, i) => (
                            <Badge key={i} variant="destructive" className="text-xs">
                              {ae}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-3">
                      {selectedProfile.pregnancy_category && (
                        <div className="rounded-md border p-3">
                          <p className="text-xs text-muted-foreground">Pregnancy</p>
                          <p className="text-lg font-bold">{selectedProfile.pregnancy_category}</p>
                        </div>
                      )}
                      {selectedProfile.max_daily_dose && (
                        <div className="rounded-md border p-3">
                          <p className="text-xs text-muted-foreground">Max Daily Dose</p>
                          <p className="text-lg font-bold">{selectedProfile.max_daily_dose}</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {!selectedProfile && !profileLoading && (
                  <div className="py-12 text-center text-muted-foreground">
                    <FileText className="mx-auto mb-2 h-8 w-8 opacity-50" />
                    <p className="text-sm">Select a drug to view its profile</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      {/* Disclaimer */}
      <Card>
        <CardContent className="py-4">
          <div className="flex items-start gap-3 text-xs text-muted-foreground">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">Clinical Disclaimer</p>
              <p>
                This drug safety information is for reference purposes only. Always
                consult authoritative clinical resources and use professional judgment
                when making prescribing decisions.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
