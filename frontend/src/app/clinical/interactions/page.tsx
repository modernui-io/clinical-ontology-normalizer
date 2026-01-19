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
  AlertTriangle,
  AlertCircle,
  Info,
  ArrowLeft,
  Plus,
  X,
  Search,
  Pill,
  CheckCircle,
  ShieldAlert,
  FileText,
} from "lucide-react";

// Types for drug interactions
interface DrugInteraction {
  id: string;
  drug1: string;
  drug2: string;
  severity: "contraindicated" | "major" | "moderate" | "minor";
  interactionType: string;
  description: string;
  clinicalEffect: string;
  management: string;
  references: string[];
}

interface InteractionCheckResult {
  drugsChecked: string[];
  interactionsFound: DrugInteraction[];
  totalInteractions: number;
  bySeverity: Record<string, number>;
  highestSeverity: string | null;
  hasContraindicated: boolean;
  hasMajor: boolean;
}

// Mock drug database for autocomplete
const drugDatabase = [
  "Acetaminophen",
  "Alprazolam",
  "Amiodarone",
  "Amlodipine",
  "Amoxicillin",
  "Aspirin",
  "Atorvastatin",
  "Azithromycin",
  "Carvedilol",
  "Cephalexin",
  "Ciprofloxacin",
  "Clarithromycin",
  "Clopidogrel",
  "Diltiazem",
  "Escitalopram",
  "Fluconazole",
  "Furosemide",
  "Gabapentin",
  "Hydrochlorothiazide",
  "Ibuprofen",
  "Insulin",
  "Itraconazole",
  "Levothyroxine",
  "Linezolid",
  "Lisinopril",
  "Lithium",
  "Lorazepam",
  "Losartan",
  "Metformin",
  "Methotrexate",
  "Metoprolol",
  "Morphine",
  "Naproxen",
  "Nitroglycerin",
  "Omeprazole",
  "Oxycodone",
  "Pantoprazole",
  "Potassium",
  "Prednisone",
  "Rosuvastatin",
  "Sertraline",
  "Sildenafil",
  "Simvastatin",
  "Spironolactone",
  "Tramadol",
  "Trimethoprim",
  "Warfarin",
];

// Mock interaction database
const interactionDatabase: DrugInteraction[] = [
  {
    id: "1",
    drug1: "warfarin",
    drug2: "aspirin",
    severity: "major",
    interactionType: "bleeding_risk",
    description: "Additive anticoagulant/antiplatelet effects",
    clinicalEffect: "Significantly increased bleeding risk, GI hemorrhage",
    management: "Avoid unless specifically indicated (mechanical valve); monitor INR closely",
    references: ["CHEST guidelines"],
  },
  {
    id: "2",
    drug1: "warfarin",
    drug2: "ibuprofen",
    severity: "major",
    interactionType: "bleeding_risk",
    description: "NSAIDs inhibit platelet function and may increase warfarin levels",
    clinicalEffect: "Increased bleeding risk, GI hemorrhage",
    management: "Avoid combination; use acetaminophen for pain",
    references: ["FDA warfarin label"],
  },
  {
    id: "3",
    drug1: "simvastatin",
    drug2: "clarithromycin",
    severity: "contraindicated",
    interactionType: "pharmacokinetic",
    description: "Clarithromycin strongly inhibits CYP3A4",
    clinicalEffect: "10-fold increase in simvastatin levels, rhabdomyolysis risk",
    management: "Contraindicated; suspend simvastatin during clarithromycin course",
    references: ["FDA clarithromycin label"],
  },
  {
    id: "4",
    drug1: "simvastatin",
    drug2: "itraconazole",
    severity: "contraindicated",
    interactionType: "pharmacokinetic",
    description: "Itraconazole strongly inhibits CYP3A4, markedly increasing simvastatin levels",
    clinicalEffect: "Rhabdomyolysis, myopathy, acute kidney injury",
    management: "Contraindicated; use alternative statin (pravastatin, rosuvastatin)",
    references: ["FDA simvastatin label"],
  },
  {
    id: "5",
    drug1: "linezolid",
    drug2: "sertraline",
    severity: "contraindicated",
    interactionType: "serotonin_syndrome",
    description: "Linezolid is an MAO inhibitor; sertraline is an SSRI",
    clinicalEffect: "Serotonin syndrome: hyperthermia, rigidity, autonomic instability",
    management: "Contraindicated; wait 2 weeks after stopping sertraline before linezolid",
    references: ["FDA linezolid label"],
  },
  {
    id: "6",
    drug1: "sildenafil",
    drug2: "nitroglycerin",
    severity: "contraindicated",
    interactionType: "hypotension",
    description: "Both drugs cause vasodilation via nitric oxide pathway",
    clinicalEffect: "Severe hypotension, syncope, MI, death",
    management: "Contraindicated; do not use nitrates within 24h of sildenafil",
    references: ["FDA sildenafil label"],
  },
  {
    id: "7",
    drug1: "metformin",
    drug2: "lisinopril",
    severity: "moderate",
    interactionType: "hypoglycemia",
    description: "ACE inhibitors may enhance hypoglycemic effect",
    clinicalEffect: "Increased risk of hypoglycemia",
    management: "Monitor blood glucose; may need to reduce metformin dose",
    references: ["UpToDate"],
  },
  {
    id: "8",
    drug1: "amlodipine",
    drug2: "simvastatin",
    severity: "moderate",
    interactionType: "pharmacokinetic",
    description: "Amlodipine inhibits CYP3A4, increasing simvastatin levels",
    clinicalEffect: "Increased risk of myopathy",
    management: "Limit simvastatin to 20mg daily with amlodipine",
    references: ["FDA simvastatin label"],
  },
  {
    id: "9",
    drug1: "omeprazole",
    drug2: "clopidogrel",
    severity: "moderate",
    interactionType: "pharmacokinetic",
    description: "Omeprazole inhibits CYP2C19, reducing clopidogrel activation",
    clinicalEffect: "Reduced antiplatelet effect, increased cardiovascular events",
    management: "Consider pantoprazole instead; or use H2 blocker",
    references: ["FDA clopidogrel label"],
  },
  {
    id: "10",
    drug1: "gabapentin",
    drug2: "morphine",
    severity: "moderate",
    interactionType: "pharmacodynamic",
    description: "Additive CNS depression",
    clinicalEffect: "Enhanced sedation, respiratory depression",
    management: "Start with lower doses; monitor for respiratory depression",
    references: ["FDA gabapentin label"],
  },
  {
    id: "11",
    drug1: "alprazolam",
    drug2: "oxycodone",
    severity: "major",
    interactionType: "pharmacodynamic",
    description: "Additive CNS and respiratory depression",
    clinicalEffect: "Profound sedation, respiratory depression, coma, death",
    management: "Avoid combination; FDA black box warning",
    references: ["FDA black box warning"],
  },
  {
    id: "12",
    drug1: "spironolactone",
    drug2: "lisinopril",
    severity: "major",
    interactionType: "hyperkalemia",
    description: "Both drugs increase potassium retention",
    clinicalEffect: "Severe hyperkalemia, cardiac arrhythmia",
    management: "Monitor potassium frequently; avoid if K>5.0 or eGFR<30",
    references: ["ACC/AHA heart failure guidelines"],
  },
  {
    id: "13",
    drug1: "amiodarone",
    drug2: "metoprolol",
    severity: "major",
    interactionType: "pharmacodynamic",
    description: "Additive effects on cardiac conduction",
    clinicalEffect: "Severe bradycardia, heart block, cardiac arrest",
    management: "Use with caution; monitor ECG and heart rate closely",
    references: ["FDA amiodarone label"],
  },
  {
    id: "14",
    drug1: "methotrexate",
    drug2: "trimethoprim",
    severity: "contraindicated",
    interactionType: "pharmacokinetic",
    description: "Trimethoprim inhibits renal excretion of methotrexate",
    clinicalEffect: "Increased methotrexate levels, severe myelosuppression",
    management: "Avoid combination; if unavoidable, monitor closely and reduce methotrexate dose",
    references: ["FDA methotrexate label"],
  },
  {
    id: "15",
    drug1: "levothyroxine",
    drug2: "omeprazole",
    severity: "moderate",
    interactionType: "pharmacokinetic",
    description: "PPIs reduce gastric acid needed for levothyroxine dissolution",
    clinicalEffect: "Decreased levothyroxine absorption",
    management: "Monitor TSH; may need higher levothyroxine dose",
    references: ["UpToDate"],
  },
];

// Severity styling
const severityStyles = {
  contraindicated: {
    badge: "bg-red-600 text-white",
    border: "border-red-500",
    bg: "bg-red-50 dark:bg-red-950",
    icon: <AlertCircle className="h-5 w-5 text-red-600" />,
    label: "Contraindicated",
  },
  major: {
    badge: "bg-red-500 text-white",
    border: "border-red-400",
    bg: "bg-red-50 dark:bg-red-950",
    icon: <AlertTriangle className="h-5 w-5 text-red-500" />,
    label: "Major",
  },
  moderate: {
    badge: "bg-amber-500 text-white",
    border: "border-amber-400",
    bg: "bg-amber-50 dark:bg-amber-950",
    icon: <AlertTriangle className="h-5 w-5 text-amber-500" />,
    label: "Moderate",
  },
  minor: {
    badge: "bg-blue-500 text-white",
    border: "border-blue-400",
    bg: "bg-blue-50 dark:bg-blue-950",
    icon: <Info className="h-5 w-5 text-blue-500" />,
    label: "Minor",
  },
};

// Interaction type labels
const interactionTypeLabels: Record<string, string> = {
  pharmacokinetic: "Pharmacokinetic",
  pharmacodynamic: "Pharmacodynamic",
  bleeding_risk: "Bleeding Risk",
  serotonin_syndrome: "Serotonin Syndrome",
  hypotension: "Hypotension",
  hyperkalemia: "Hyperkalemia",
  hypoglycemia: "Hypoglycemia",
  nephrotoxicity: "Nephrotoxicity",
  hepatotoxicity: "Hepatotoxicity",
  qt_prolongation: "QT Prolongation",
  duplicate_therapy: "Duplicate Therapy",
};

export default function DrugInteractionsPage() {
  const [medications, setMedications] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [result, setResult] = useState<InteractionCheckResult | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  const handleInputChange = (value: string) => {
    setInputValue(value);
    if (value.length > 0) {
      const filtered = drugDatabase.filter((drug) =>
        drug.toLowerCase().includes(value.toLowerCase())
      );
      setSuggestions(filtered.slice(0, 8));
      setShowSuggestions(true);
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  const addMedication = (drug: string) => {
    const normalizedDrug = drug.trim();
    if (
      normalizedDrug &&
      !medications.some((m) => m.toLowerCase() === normalizedDrug.toLowerCase())
    ) {
      setMedications([...medications, normalizedDrug]);
    }
    setInputValue("");
    setSuggestions([]);
    setShowSuggestions(false);
    setResult(null);
  };

  const removeMedication = (index: number) => {
    setMedications(medications.filter((_, i) => i !== index));
    setResult(null);
  };

  const checkInteractions = useCallback(() => {
    if (medications.length < 2) {
      return;
    }

    setIsChecking(true);

    // Simulate API call delay
    setTimeout(() => {
      const normalizedMeds = medications.map((m) => m.toLowerCase());
      const foundInteractions: DrugInteraction[] = [];

      // Check all pairs of medications
      for (let i = 0; i < normalizedMeds.length; i++) {
        for (let j = i + 1; j < normalizedMeds.length; j++) {
          const drug1 = normalizedMeds[i];
          const drug2 = normalizedMeds[j];

          // Find interactions in database
          const interaction = interactionDatabase.find(
            (int) =>
              (int.drug1.toLowerCase() === drug1 &&
                int.drug2.toLowerCase() === drug2) ||
              (int.drug1.toLowerCase() === drug2 &&
                int.drug2.toLowerCase() === drug1)
          );

          if (interaction) {
            foundInteractions.push({
              ...interaction,
              drug1: medications[i],
              drug2: medications[j],
            });
          }
        }
      }

      // Calculate severity counts
      const bySeverity: Record<string, number> = {};
      let hasContraindicated = false;
      let hasMajor = false;
      let highestSeverity: string | null = null;

      const severityOrder = ["contraindicated", "major", "moderate", "minor"];

      foundInteractions.forEach((int) => {
        bySeverity[int.severity] = (bySeverity[int.severity] || 0) + 1;

        if (int.severity === "contraindicated") {
          hasContraindicated = true;
          highestSeverity = "contraindicated";
        } else if (int.severity === "major" && !hasContraindicated) {
          hasMajor = true;
          highestSeverity = highestSeverity || "major";
        } else if (!highestSeverity) {
          highestSeverity = int.severity;
        }
      });

      // Sort by severity
      foundInteractions.sort(
        (a, b) => severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity)
      );

      setResult({
        drugsChecked: medications,
        interactionsFound: foundInteractions,
        totalInteractions: foundInteractions.length,
        bySeverity,
        highestSeverity,
        hasContraindicated,
        hasMajor,
      });

      setIsChecking(false);
    }, 500);
  }, [medications]);

  const clearAll = () => {
    setMedications([]);
    setInputValue("");
    setResult(null);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/clinical">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Drug Interaction Checker
            </h1>
            <p className="text-muted-foreground">
              Check for potential drug-drug interactions in medication lists
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Medication Input Panel */}
        <div className="lg:col-span-1 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Pill className="h-5 w-5" />
                Medications
              </CardTitle>
              <CardDescription>
                Enter medications to check for interactions
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Drug Input */}
              <div className="relative">
                <Label htmlFor="drug-input">Add Medication</Label>
                <div className="relative mt-1.5">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="drug-input"
                    placeholder="Type drug name..."
                    value={inputValue}
                    onChange={(e) => handleInputChange(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && inputValue) {
                        addMedication(inputValue);
                      }
                    }}
                    className="pl-10"
                  />
                  {inputValue && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                      onClick={() => addMedication(inputValue)}
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  )}
                </div>

                {/* Suggestions Dropdown */}
                {showSuggestions && suggestions.length > 0 && (
                  <div className="absolute z-10 w-full mt-1 bg-background border rounded-md shadow-lg max-h-60 overflow-auto">
                    {suggestions.map((drug, idx) => (
                      <button
                        key={idx}
                        className="w-full px-3 py-2 text-left text-sm hover:bg-muted transition-colors"
                        onClick={() => addMedication(drug)}
                      >
                        {drug}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Current Medications List */}
              <div>
                <Label>Current Medications ({medications.length})</Label>
                <div className="mt-2 space-y-2 min-h-[100px]">
                  {medications.length === 0 ? (
                    <p className="text-sm text-muted-foreground py-4 text-center">
                      No medications added yet
                    </p>
                  ) : (
                    medications.map((med, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-2 rounded-md bg-muted"
                      >
                        <div className="flex items-center gap-2">
                          <Pill className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm font-medium">{med}</span>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0"
                          onClick={() => removeMedication(idx)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2">
                <Button
                  className="flex-1"
                  onClick={checkInteractions}
                  disabled={medications.length < 2 || isChecking}
                >
                  {isChecking ? (
                    <>
                      <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      Checking...
                    </>
                  ) : (
                    <>
                      <ShieldAlert className="mr-2 h-4 w-4" />
                      Check Interactions
                    </>
                  )}
                </Button>
                <Button variant="outline" onClick={clearAll}>
                  Clear
                </Button>
              </div>

              {medications.length < 2 && medications.length > 0 && (
                <p className="text-xs text-muted-foreground text-center">
                  Add at least 2 medications to check for interactions
                </p>
              )}
            </CardContent>
          </Card>

          {/* Quick Add Common Combinations */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Example Combinations</CardTitle>
              <CardDescription className="text-xs">
                Click to load example medication lists
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start text-xs"
                onClick={() => {
                  setMedications(["Warfarin", "Aspirin", "Omeprazole"]);
                  setResult(null);
                }}
              >
                Anticoagulation: Warfarin + Aspirin + Omeprazole
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start text-xs"
                onClick={() => {
                  setMedications(["Lisinopril", "Spironolactone", "Potassium"]);
                  setResult(null);
                }}
              >
                Heart Failure: Lisinopril + Spironolactone + K+
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start text-xs"
                onClick={() => {
                  setMedications(["Simvastatin", "Amlodipine", "Clarithromycin"]);
                  setResult(null);
                }}
              >
                Statin Risk: Simvastatin + Amlodipine + Clarithromycin
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start text-xs"
                onClick={() => {
                  setMedications(["Oxycodone", "Alprazolam", "Gabapentin"]);
                  setResult(null);
                }}
              >
                CNS Depression: Oxycodone + Alprazolam + Gabapentin
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Results Panel */}
        <div className="lg:col-span-2 space-y-4">
          {result ? (
            <>
              {/* Summary Card */}
              <Card
                className={
                  result.hasContraindicated
                    ? "border-red-500"
                    : result.hasMajor
                    ? "border-red-400"
                    : result.totalInteractions > 0
                    ? "border-amber-400"
                    : "border-green-500"
                }
              >
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    {result.totalInteractions === 0 ? (
                      <>
                        <CheckCircle className="h-5 w-5 text-green-500" />
                        No Interactions Found
                      </>
                    ) : result.hasContraindicated ? (
                      <>
                        <AlertCircle className="h-5 w-5 text-red-600" />
                        Contraindicated Combination Detected
                      </>
                    ) : result.hasMajor ? (
                      <>
                        <AlertTriangle className="h-5 w-5 text-red-500" />
                        Major Interactions Found
                      </>
                    ) : (
                      <>
                        <AlertTriangle className="h-5 w-5 text-amber-500" />
                        Interactions Found
                      </>
                    )}
                  </CardTitle>
                  <CardDescription>
                    Checked {result.drugsChecked.length} medications
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 sm:grid-cols-4">
                    <div className="text-center p-3 rounded-lg bg-muted">
                      <p className="text-2xl font-bold">{result.totalInteractions}</p>
                      <p className="text-xs text-muted-foreground">
                        Total Interactions
                      </p>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-red-50 dark:bg-red-950">
                      <p className="text-2xl font-bold text-red-600">
                        {(result.bySeverity["contraindicated"] || 0) +
                          (result.bySeverity["major"] || 0)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Critical/Major
                      </p>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-amber-50 dark:bg-amber-950">
                      <p className="text-2xl font-bold text-amber-600">
                        {result.bySeverity["moderate"] || 0}
                      </p>
                      <p className="text-xs text-muted-foreground">Moderate</p>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-blue-50 dark:bg-blue-950">
                      <p className="text-2xl font-bold text-blue-600">
                        {result.bySeverity["minor"] || 0}
                      </p>
                      <p className="text-xs text-muted-foreground">Minor</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Detailed Interactions */}
              {result.interactionsFound.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <FileText className="h-5 w-5" />
                      Interaction Details
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {result.interactionsFound.map((interaction, idx) => {
                        const style = severityStyles[interaction.severity];
                        return (
                          <div
                            key={idx}
                            className={`rounded-lg border ${style.border} ${style.bg} p-4`}
                          >
                            <div className="flex items-start gap-3">
                              <div className="mt-0.5">{style.icon}</div>
                              <div className="flex-1 space-y-3">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="font-semibold">
                                    {interaction.drug1} + {interaction.drug2}
                                  </span>
                                  <Badge className={style.badge}>
                                    {style.label}
                                  </Badge>
                                  <Badge variant="outline">
                                    {interactionTypeLabels[interaction.interactionType] ||
                                      interaction.interactionType}
                                  </Badge>
                                </div>

                                <div className="grid gap-2 text-sm">
                                  <div>
                                    <span className="font-medium">Mechanism: </span>
                                    <span className="text-muted-foreground">
                                      {interaction.description}
                                    </span>
                                  </div>
                                  <div>
                                    <span className="font-medium">Clinical Effect: </span>
                                    <span className="text-muted-foreground">
                                      {interaction.clinicalEffect}
                                    </span>
                                  </div>
                                  <div className="p-2 rounded bg-background border">
                                    <span className="font-medium text-blue-600 dark:text-blue-400">
                                      Management:{" "}
                                    </span>
                                    <span>{interaction.management}</span>
                                  </div>
                                </div>

                                {interaction.references.length > 0 && (
                                  <div className="text-xs text-muted-foreground">
                                    References: {interaction.references.join(", ")}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>
              )}

              {result.totalInteractions === 0 && (
                <Card>
                  <CardContent className="py-12">
                    <div className="text-center space-y-4">
                      <div className="flex justify-center">
                        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
                          <CheckCircle className="h-8 w-8 text-green-600" />
                        </div>
                      </div>
                      <div>
                        <h3 className="text-lg font-medium">
                          No Known Interactions
                        </h3>
                        <p className="text-muted-foreground">
                          No significant drug-drug interactions were found between
                          the medications listed
                        </p>
                        <p className="text-xs text-muted-foreground mt-2">
                          Note: This check may not include all possible
                          interactions. Always consult clinical references for
                          complete information.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <Card>
              <CardContent className="py-12">
                <div className="text-center space-y-4">
                  <div className="flex justify-center">
                    <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                      <ShieldAlert className="h-8 w-8 text-muted-foreground" />
                    </div>
                  </div>
                  <div>
                    <h3 className="text-lg font-medium">
                      Drug Interaction Checker
                    </h3>
                    <p className="text-muted-foreground">
                      Add medications to the list and click "Check Interactions" to
                      identify potential drug-drug interactions
                    </p>
                  </div>
                  <div className="pt-4 space-y-2 text-sm text-muted-foreground">
                    <p>This tool checks for:</p>
                    <ul className="space-y-1">
                      <li className="flex items-center justify-center gap-2">
                        <AlertCircle className="h-4 w-4 text-red-600" />
                        Contraindicated combinations
                      </li>
                      <li className="flex items-center justify-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-red-500" />
                        Major interactions
                      </li>
                      <li className="flex items-center justify-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-amber-500" />
                        Moderate interactions
                      </li>
                      <li className="flex items-center justify-center gap-2">
                        <Info className="h-4 w-4 text-blue-500" />
                        Minor interactions
                      </li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Disclaimer */}
          <Card>
            <CardContent className="py-4">
              <div className="flex items-start gap-3 text-xs text-muted-foreground">
                <Info className="h-4 w-4 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium">Clinical Disclaimer</p>
                  <p>
                    This drug interaction checker is for informational purposes
                    only and should not replace clinical judgment. Always verify
                    interactions with authoritative clinical resources (Lexicomp,
                    Micromedex, Clinical Pharmacology) before making clinical
                    decisions. This database may not include all possible
                    interactions.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
