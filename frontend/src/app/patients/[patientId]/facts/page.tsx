"use client";

import { useCallback, useEffect, useState, useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getPatientFacts, ClinicalFact } from "@/lib/api";
import DataSourceModeBanner from "@/components/readiness/DataSourceModeBanner";
import { useAuth } from "@/hooks/use-auth";

const ASSERTION_COLORS: Record<string, string> = {
  present: "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-200",
  absent: "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-200",
  possible: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-200",
};

const DOMAIN_CONFIG: Record<string, { color: string; icon: string; label: string; subcategories: string[] }> = {
  condition: {
    color: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-200",
    icon: "🩺",
    label: "Conditions",
    subcategories: ["Cardiovascular", "Respiratory", "Infectious", "Endocrine", "Neurological", "Oncological", "Other"],
  },
  drug: {
    color: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-200",
    icon: "💊",
    label: "Medications",
    subcategories: ["Antibiotics", "Cardiovascular", "Pain Management", "Psychiatric", "Endocrine", "Other"],
  },
  measurement: {
    color: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-200",
    icon: "📊",
    label: "Measurements",
    subcategories: ["Vital Signs", "Lab Results", "Imaging", "Other"],
  },
  procedure: {
    color: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-200",
    icon: "🔧",
    label: "Procedures",
    subcategories: ["Surgical", "Diagnostic", "Therapeutic", "Other"],
  },
  observation: {
    color: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-200",
    icon: "👁️",
    label: "Observations",
    subcategories: ["Social History", "Family History", "Symptoms", "Other"],
  },
};

// Keyword-based subcategory mapping
const SUBCATEGORY_KEYWORDS: Record<string, Record<string, string[]>> = {
  condition: {
    Cardiovascular: ["heart", "cardiac", "hypertension", "arrhythmia", "coronary", "vascular", "angina", "infarction", "atrial", "ventricular"],
    Respiratory: ["lung", "pulmonary", "asthma", "copd", "pneumonia", "bronchitis", "respiratory"],
    Infectious: ["infection", "sepsis", "bacterial", "viral", "fever", "covid", "influenza", "cellulitis"],
    Endocrine: ["diabetes", "thyroid", "adrenal", "pituitary", "metabolic", "glucose"],
    Neurological: ["stroke", "seizure", "dementia", "alzheimer", "parkinson", "neuropathy", "migraine", "headache"],
    Oncological: ["cancer", "tumor", "carcinoma", "malignant", "metastatic", "lymphoma", "leukemia"],
  },
  drug: {
    Antibiotics: ["antibiotic", "penicillin", "amoxicillin", "ciprofloxacin", "azithromycin", "cephalosporin", "vancomycin"],
    Cardiovascular: ["statin", "beta-blocker", "ace inhibitor", "warfarin", "aspirin", "lisinopril", "metoprolol", "atorvastatin"],
    "Pain Management": ["opioid", "morphine", "hydrocodone", "ibuprofen", "acetaminophen", "gabapentin", "tramadol"],
    Psychiatric: ["antidepressant", "ssri", "benzodiazepine", "sertraline", "fluoxetine", "lorazepam"],
    Endocrine: ["insulin", "metformin", "levothyroxine", "prednisone", "corticosteroid"],
  },
  measurement: {
    "Vital Signs": ["blood pressure", "heart rate", "temperature", "oxygen", "respiratory rate", "pulse", "bp"],
    "Lab Results": ["hemoglobin", "glucose", "creatinine", "potassium", "sodium", "cholesterol", "hba1c", "wbc", "platelet"],
    Imaging: ["x-ray", "ct scan", "mri", "ultrasound", "echo", "radiograph"],
  },
  procedure: {
    Surgical: ["surgery", "operation", "resection", "bypass", "transplant", "amputation", "laparoscopy"],
    Diagnostic: ["biopsy", "endoscopy", "colonoscopy", "catheterization", "angiography"],
    Therapeutic: ["dialysis", "transfusion", "chemotherapy", "radiation", "ventilation"],
  },
  observation: {
    "Social History": ["smoking", "alcohol", "drug use", "occupation", "exercise", "diet"],
    "Family History": ["family history", "hereditary", "genetic"],
    Symptoms: ["pain", "fatigue", "nausea", "dizziness", "shortness of breath", "cough"],
  },
};

function getSubcategory(fact: ClinicalFact): string {
  const domain = fact.domain.toLowerCase();
  const keywords = SUBCATEGORY_KEYWORDS[domain];
  if (!keywords) return "Other";

  const conceptLower = fact.concept_name.toLowerCase();

  for (const [subcategory, terms] of Object.entries(keywords)) {
    if (terms.some((term) => conceptLower.includes(term))) {
      return subcategory;
    }
  }

  return "Other";
}

function DomainIcon({ domain }: { domain: string }) {
  const config = DOMAIN_CONFIG[domain.toLowerCase()];
  return <span className="text-lg">{config?.icon || "📋"}</span>;
}

interface FactCardProps {
  fact: ClinicalFact;
  showDomain?: boolean;
}

function FactCard({ fact, showDomain = false }: FactCardProps) {
  return (
    <div className="flex items-center justify-between p-3 rounded-lg border bg-white dark:bg-zinc-900 hover:border-zinc-400 dark:hover:border-zinc-600 transition-colors">
      <div className="flex items-center gap-3 flex-1 min-w-0">
        {showDomain && <DomainIcon domain={fact.domain} />}
        <Badge className={ASSERTION_COLORS[fact.assertion] || "bg-gray-100"} variant="outline">
          {fact.assertion}
        </Badge>
        <div className="flex-1 min-w-0">
          <span className="font-medium text-sm truncate block">{fact.concept_name}</span>
          {fact.value && (
            <span className="text-xs text-zinc-500">
              {fact.value}{fact.unit ? ` ${fact.unit}` : ""}
            </span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3 text-xs text-zinc-500 flex-shrink-0">
        <span className="capitalize hidden sm:inline">{fact.temporality}</span>
        <span className={`font-medium ${fact.confidence >= 0.8 ? "text-green-600" : fact.confidence >= 0.5 ? "text-yellow-600" : "text-red-600"}`}>
          {(fact.confidence * 100).toFixed(0)}%
        </span>
        <code className="bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-[10px]">
          {fact.omop_concept_id}
        </code>
      </div>
    </div>
  );
}

export default function PatientFactsPage() {
  const params = useParams();
  const { isDemo, isLoading: isAuthLoading } = useAuth();
  const patientId = params.patientId as string;
  const [facts, setFacts] = useState<ClinicalFact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [domainFilter, setDomainFilter] = useState<string | undefined>();
  const [assertionFilter, setAssertionFilter] = useState<string | undefined>();
  const [expandedDomains, setExpandedDomains] = useState<Set<string>>(new Set());
  const [expandedSubcategories, setExpandedSubcategories] = useState<Set<string>>(new Set());
  const [dataMode, setDataMode] = useState<"live" | "simulation">("live");

  const fetchFacts = useCallback(async () => {
    // In demo mode, skip API calls and load demo data directly
    if (isDemo) {
      try {
        const { DEMO_CLINICAL_FACTS } = await import("@/lib/demo-data");
        const demoRaw = DEMO_CLINICAL_FACTS?.[patientId];
        if (demoRaw && demoRaw.length > 0) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const mapped: ClinicalFact[] = (demoRaw as any[]).map((f) => ({
            id: f.id,
            patient_id: f.patient_id,
            domain: (f.fact_type || "Observation").charAt(0).toUpperCase() + (f.fact_type || "observation").slice(1),
            omop_concept_id: Number(f.concept_id) || 0,
            concept_name: f.concept_name,
            assertion: f.assertion || "present",
            temporality: "current",
            experiencer: "patient",
            confidence: f.confidence || 0.9,
            value: f.value ?? null,
            unit: f.unit ?? null,
            start_date: null,
            end_date: null,
            created_at: new Date().toISOString(),
          }));
          setFacts(mapped);
          const domains = new Set(mapped.map((f) => f.domain.toLowerCase()));
          setExpandedDomains(domains);
        } else {
          setFacts([]);
        }
      } catch {
        setFacts([]);
      }
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const result = await getPatientFacts(patientId, {
        domain: domainFilter,
        assertion: assertionFilter,
      });
      setFacts(result);
      setError(null);
      // Expand all domains by default
      const domains = new Set(result.map((f) => f.domain.toLowerCase()));
      setExpandedDomains(domains);
    } catch (err) {
      console.error("Failed to fetch facts:", err);
      // Fall back to demo clinical facts
      try {
        const { DEMO_CLINICAL_FACTS } = await import("@/lib/demo-data");
        const demoRaw = DEMO_CLINICAL_FACTS?.[patientId];
        if (demoRaw && demoRaw.length > 0) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const mapped: ClinicalFact[] = (demoRaw as any[]).map((f) => ({
            id: f.id,
            patient_id: f.patient_id,
            domain: (f.fact_type || "Observation").charAt(0).toUpperCase() + (f.fact_type || "observation").slice(1),
            omop_concept_id: Number(f.concept_id) || 0,
            concept_name: f.concept_name,
            assertion: f.assertion || "present",
            temporality: "current",
            experiencer: "patient",
            confidence: f.confidence || 0.9,
            value: f.value ?? null,
            unit: f.unit ?? null,
            start_date: null,
            end_date: null,
            created_at: new Date().toISOString(),
          }));
          setFacts(mapped);
          const domains = new Set(mapped.map((f) => f.domain.toLowerCase()));
          setExpandedDomains(domains);
          setDataMode("simulation");
        } else {
          setError("No clinical facts found for this patient.");
          setFacts([]);
        }
      } catch {
        setError("No clinical facts found for this patient.");
        setFacts([]);
      }
    } finally {
      setIsLoading(false);
    }
  }, [patientId, domainFilter, assertionFilter, isDemo]);

  useEffect(() => {
    if (!patientId || isAuthLoading) return;
    if (isDemo) setDataMode("simulation");
    fetchFacts();
  }, [patientId, fetchFacts, isAuthLoading, isDemo]);

  // Filter facts by search
  const filteredFacts = useMemo(() => {
    if (!searchQuery.trim()) return facts;
    const query = searchQuery.toLowerCase();
    return facts.filter(
      (fact) =>
        fact.concept_name.toLowerCase().includes(query) ||
        fact.domain.toLowerCase().includes(query) ||
        fact.omop_concept_id?.toString().includes(query)
    );
  }, [facts, searchQuery]);

  // Group facts by domain
  const factsByDomain = useMemo(() => {
    return filteredFacts.reduce(
      (acc, fact) => {
        const domain = fact.domain.toLowerCase();
        if (!acc[domain]) acc[domain] = [];
        acc[domain].push(fact);
        return acc;
      },
      {} as Record<string, ClinicalFact[]>
    );
  }, [filteredFacts]);

  // Group facts by domain and subcategory
  const factsByDomainAndSubcategory = useMemo(() => {
    const result: Record<string, Record<string, ClinicalFact[]>> = {};

    for (const [domain, domainFacts] of Object.entries(factsByDomain)) {
      result[domain] = {};
      for (const fact of domainFacts) {
        const subcategory = getSubcategory(fact);
        if (!result[domain][subcategory]) {
          result[domain][subcategory] = [];
        }
        result[domain][subcategory].push(fact);
      }
    }

    return result;
  }, [factsByDomain]);

  // Toggle domain expansion
  const toggleDomain = (domain: string) => {
    const newExpanded = new Set(expandedDomains);
    if (newExpanded.has(domain)) {
      newExpanded.delete(domain);
    } else {
      newExpanded.add(domain);
    }
    setExpandedDomains(newExpanded);
  };

  // Toggle subcategory expansion
  const toggleSubcategory = (key: string) => {
    const newExpanded = new Set(expandedSubcategories);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedSubcategories(newExpanded);
  };

  // Stats
  const stats = useMemo(() => {
    const present = filteredFacts.filter((f) => f.assertion === "present").length;
    const absent = filteredFacts.filter((f) => f.assertion === "absent").length;
    const possible = filteredFacts.filter((f) => f.assertion === "possible").length;
    return { present, absent, possible, total: filteredFacts.length };
  }, [filteredFacts]);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/patients" className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
                &larr; Patients
              </Link>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                Patient {patientId} - Clinical Facts
              </h1>
            </div>
            <div className="flex gap-2">
              <Link href={`/patients/${patientId}/timeline`}>
                <Button variant="outline">Timeline</Button>
              </Link>
              <Link href={`/patients/${patientId}/graph`}>
                <Button variant="outline">Knowledge Graph</Button>
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {dataMode === "simulation" && (
          <div className="mb-6">
            <DataSourceModeBanner
              mode={dataMode}
              title="Clinical facts data source"
              description="Backend API is unavailable. Clinical facts show demonstration data."
              backendEndpoints={[`/api/v1/patients/${patientId}/facts`]}
            />
          </div>
        )}
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
          </div>
        ) : error && facts.length === 0 ? (
          <Card className="mx-auto max-w-2xl">
            <CardContent className="py-8 text-center">
              <p className="text-zinc-500">{error}</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-6">
            {/* Summary Cards */}
            <div className="grid gap-4 grid-cols-2 md:grid-cols-4 lg:grid-cols-6">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-zinc-500">Total Facts</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stats.total}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-zinc-500">Present</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-green-600">{stats.present}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-zinc-500">Absent</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-red-600">{stats.absent}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-zinc-500">Possible</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-yellow-600">{stats.possible}</div>
                </CardContent>
              </Card>
              {/* Domain quick counts */}
              {Object.entries(DOMAIN_CONFIG).slice(0, 2).map(([domain, config]) => (
                <Card key={domain} className="hidden lg:block">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-zinc-500 flex items-center gap-1">
                      <span>{config.icon}</span> {config.label}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{factsByDomain[domain]?.length || 0}</div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Search and Filters */}
            <Card>
              <CardContent className="py-4">
                <div className="flex flex-wrap gap-4 items-center">
                  {/* Search */}
                  <div className="flex-1 min-w-[200px] max-w-md">
                    <Input
                      placeholder="Search by concept name, domain, or OMOP ID..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                  </div>

                  {/* Domain quick filters */}
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant={!domainFilter ? "default" : "outline"}
                      size="sm"
                      onClick={() => setDomainFilter(undefined)}
                    >
                      All
                    </Button>
                    {Object.entries(DOMAIN_CONFIG).map(([domain, config]) => (
                      <Button
                        key={domain}
                        variant={domainFilter === domain ? "default" : "outline"}
                        size="sm"
                        onClick={() => setDomainFilter(domainFilter === domain ? undefined : domain)}
                        className="gap-1"
                      >
                        <span>{config.icon}</span>
                        <span className="hidden sm:inline">{config.label}</span>
                        {factsByDomain[domain]?.length > 0 && (
                          <Badge variant="secondary" className="ml-1 text-xs">
                            {factsByDomain[domain].length}
                          </Badge>
                        )}
                      </Button>
                    ))}
                  </div>

                  {/* Assertion filter */}
                  <div className="flex gap-1">
                    {["present", "absent", "possible"].map((assertion) => (
                      <Button
                        key={assertion}
                        variant={assertionFilter === assertion ? "default" : "outline"}
                        size="sm"
                        onClick={() => setAssertionFilter(assertionFilter === assertion ? undefined : assertion)}
                        className={assertionFilter === assertion ? "" : ASSERTION_COLORS[assertion]}
                      >
                        {assertion.charAt(0).toUpperCase() + assertion.slice(1)}
                      </Button>
                    ))}
                  </div>

                  {/* Clear filters */}
                  {(searchQuery || domainFilter || assertionFilter) && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setSearchQuery("");
                        setDomainFilter(undefined);
                        setAssertionFilter(undefined);
                      }}
                    >
                      Clear
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Main Content Tabs */}
            <Tabs defaultValue="categorized" className="w-full">
              <TabsList>
                <TabsTrigger value="categorized">Categorized View</TabsTrigger>
                <TabsTrigger value="table">Table View</TabsTrigger>
                <TabsTrigger value="timeline">By Date</TabsTrigger>
              </TabsList>

              {/* Categorized View */}
              <TabsContent value="categorized" className="space-y-4 mt-4">
                {Object.entries(factsByDomainAndSubcategory)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .filter(([domain]) => !domainFilter || domain === domainFilter)
                  .map(([domain, subcategories]) => {
                    const config = DOMAIN_CONFIG[domain] || { color: "bg-gray-100", icon: "📋", label: domain };
                    const totalCount = Object.values(subcategories).flat().length;

                    return (
                      <Card key={domain}>
                        <Collapsible
                          open={expandedDomains.has(domain)}
                          onOpenChange={() => toggleDomain(domain)}
                        >
                          <CollapsibleTrigger asChild>
                            <CardHeader className="cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors">
                              <div className="flex items-center justify-between">
                                <CardTitle className="text-lg flex items-center gap-3">
                                  <span className="text-2xl">{config.icon}</span>
                                  <span>{config.label}</span>
                                  <Badge variant="secondary">{totalCount}</Badge>
                                </CardTitle>
                                <div className="flex items-center gap-2">
                                  {/* Assertion summary badges */}
                                  {Object.values(subcategories).flat().filter((f) => f.assertion === "present").length > 0 && (
                                    <Badge className={ASSERTION_COLORS["present"]} variant="outline">
                                      {Object.values(subcategories).flat().filter((f) => f.assertion === "present").length} present
                                    </Badge>
                                  )}
                                  {Object.values(subcategories).flat().filter((f) => f.assertion === "absent").length > 0 && (
                                    <Badge className={ASSERTION_COLORS["absent"]} variant="outline">
                                      {Object.values(subcategories).flat().filter((f) => f.assertion === "absent").length} absent
                                    </Badge>
                                  )}
                                  <span className="text-zinc-400">{expandedDomains.has(domain) ? "▼" : "▶"}</span>
                                </div>
                              </div>
                            </CardHeader>
                          </CollapsibleTrigger>
                          <CollapsibleContent>
                            <CardContent className="pt-0 space-y-4">
                              {Object.entries(subcategories)
                                .sort(([a], [b]) => a === "Other" ? 1 : b === "Other" ? -1 : a.localeCompare(b))
                                .map(([subcategory, subFacts]) => {
                                  const subKey = `${domain}-${subcategory}`;
                                  const isExpanded = expandedSubcategories.has(subKey) || subFacts.length <= 3;

                                  return (
                                    <div key={subcategory} className="border rounded-lg">
                                      <button
                                        className="w-full px-4 py-2 flex items-center justify-between text-left hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
                                        onClick={() => toggleSubcategory(subKey)}
                                      >
                                        <span className="font-medium text-sm">
                                          {subcategory}
                                          <span className="text-zinc-400 ml-2">({subFacts.length})</span>
                                        </span>
                                        {subFacts.length > 3 && (
                                          <span className="text-zinc-400 text-xs">
                                            {isExpanded ? "Show less" : "Show all"}
                                          </span>
                                        )}
                                      </button>
                                      <div className="px-4 pb-3 space-y-2">
                                        {(isExpanded ? subFacts : subFacts.slice(0, 3)).map((fact) => (
                                          <FactCard key={fact.id} fact={fact} />
                                        ))}
                                        {!isExpanded && subFacts.length > 3 && (
                                          <button
                                            className="text-xs text-blue-600 hover:underline"
                                            onClick={() => toggleSubcategory(subKey)}
                                          >
                                            + {subFacts.length - 3} more
                                          </button>
                                        )}
                                      </div>
                                    </div>
                                  );
                                })}
                            </CardContent>
                          </CollapsibleContent>
                        </Collapsible>
                      </Card>
                    );
                  })}
                {filteredFacts.length === 0 && (
                  <Card>
                    <CardContent className="py-8 text-center text-zinc-500">
                      No facts match the current filters.
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              {/* Table View */}
              <TabsContent value="table" className="mt-4">
                <Card>
                  <CardHeader>
                    <CardTitle>All Clinical Facts</CardTitle>
                    <CardDescription>
                      {filteredFacts.length} clinical findings
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="rounded-lg border overflow-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-10"></TableHead>
                            <TableHead>Domain</TableHead>
                            <TableHead>Subcategory</TableHead>
                            <TableHead>Concept</TableHead>
                            <TableHead>OMOP ID</TableHead>
                            <TableHead>Assertion</TableHead>
                            <TableHead>Temporality</TableHead>
                            <TableHead>Confidence</TableHead>
                            <TableHead>Value</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {filteredFacts.map((fact) => (
                            <TableRow key={fact.id}>
                              <TableCell><DomainIcon domain={fact.domain} /></TableCell>
                              <TableCell>
                                <Badge className={DOMAIN_CONFIG[fact.domain.toLowerCase()]?.color || "bg-gray-100"}>
                                  {fact.domain}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-sm text-zinc-500">
                                {getSubcategory(fact)}
                              </TableCell>
                              <TableCell className="font-medium max-w-xs truncate">
                                {fact.concept_name}
                              </TableCell>
                              <TableCell className="font-mono text-xs">
                                {fact.omop_concept_id}
                              </TableCell>
                              <TableCell>
                                <Badge className={ASSERTION_COLORS[fact.assertion] || "bg-gray-100"}>
                                  {fact.assertion}
                                </Badge>
                              </TableCell>
                              <TableCell className="capitalize text-sm">{fact.temporality}</TableCell>
                              <TableCell>
                                <span className={`font-medium ${fact.confidence >= 0.8 ? "text-green-600" : fact.confidence >= 0.5 ? "text-yellow-600" : "text-red-600"}`}>
                                  {(fact.confidence * 100).toFixed(0)}%
                                </span>
                              </TableCell>
                              <TableCell className="text-sm">
                                {fact.value ? `${fact.value}${fact.unit ? ` ${fact.unit}` : ""}` : "-"}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                    {filteredFacts.length === 0 && (
                      <div className="text-center py-8 text-zinc-500">
                        No facts match the current filters.
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Timeline View */}
              <TabsContent value="timeline" className="mt-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Clinical Facts Timeline</CardTitle>
                    <CardDescription>
                      Facts grouped by date (most recent first)
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {filteredFacts.length > 0 ? (
                      <div className="space-y-6">
                        {/* Group by date */}
                        {Object.entries(
                          filteredFacts.reduce((acc, fact) => {
                            const date = fact.start_date || "Unknown Date";
                            if (!acc[date]) acc[date] = [];
                            acc[date].push(fact);
                            return acc;
                          }, {} as Record<string, ClinicalFact[]>)
                        )
                          .sort(([a], [b]) => (a === "Unknown Date" ? 1 : b === "Unknown Date" ? -1 : b.localeCompare(a)))
                          .map(([date, dateFacts]) => (
                            <div key={date} className="relative pl-8 border-l-2 border-zinc-200 dark:border-zinc-700">
                              <div className="absolute left-[-9px] top-0 w-4 h-4 rounded-full bg-blue-500 border-2 border-white dark:border-zinc-900" />
                              <div className="mb-2">
                                <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                                  {date === "Unknown Date" ? date : new Date(date).toLocaleDateString("en-US", {
                                    weekday: "long",
                                    year: "numeric",
                                    month: "long",
                                    day: "numeric",
                                  })}
                                </span>
                                <span className="text-sm text-zinc-500 ml-2">({dateFacts.length} facts)</span>
                              </div>
                              <div className="space-y-2">
                                {dateFacts.map((fact) => (
                                  <FactCard key={fact.id} fact={fact} showDomain />
                                ))}
                              </div>
                            </div>
                          ))}
                      </div>
                    ) : (
                      <div className="text-center py-8 text-zinc-500">
                        No facts match the current filters.
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        )}
      </main>
    </div>
  );
}
