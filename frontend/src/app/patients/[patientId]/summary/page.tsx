"use client";

import { useCallback, useEffect, useState } from "react";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  FileText,
  Sparkles,
  Download,
  Copy,
  Loader2,
  CheckCircle,
  AlertCircle,
  Info,
  ChevronRight,
  User,
  Pill,
  Activity,
  Heart,
  ClipboardList,
  Beaker,
  Calendar,
  AlertTriangle,
  ExternalLink,
} from "lucide-react";
import {
  Patient,
  ClinicalFact,
  PatientSummaryResponse,
  PatientFactInput,
  FactCitation,
  getPatient,
  getPatientFacts,
  generatePatientSummary,
} from "@/lib/api";
import { ConfidenceBadge } from "@/components/provenance/ConfidenceBadge";
import { ConfidenceTrend } from "@/components/provenance/ConfidenceTrend";

// Domain icons and colors
const DOMAIN_CONFIG: Record<
  string,
  { icon: React.ComponentType<{ className?: string }>; color: string; label: string }
> = {
  condition: {
    icon: Heart,
    color: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    label: "Conditions",
  },
  drug: {
    icon: Pill,
    color: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    label: "Medications",
  },
  measurement: {
    icon: Beaker,
    color: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    label: "Labs",
  },
  procedure: {
    icon: Activity,
    color: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
    label: "Procedures",
  },
  observation: {
    icon: ClipboardList,
    color: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
    label: "Observations",
  },
};

const FOCUS_AREAS = [
  { id: "problems", label: "Active Problems", icon: Heart },
  { id: "meds", label: "Medications", icon: Pill },
  { id: "labs", label: "Recent Labs", icon: Beaker },
  { id: "visits", label: "Recent Visits", icon: Calendar },
  { id: "allergies", label: "Allergies", icon: AlertTriangle },
];

const CONFIDENCE_STYLES: Record<string, string> = {
  high: "text-green-600 dark:text-green-400",
  medium: "text-yellow-600 dark:text-yellow-400",
  low: "text-red-600 dark:text-red-400",
};

export default function PatientSummaryPage() {
  const params = useParams();
  const patientId = params.patientId as string;

  // State
  const [patient, setPatient] = useState<Patient | null>(null);
  const [facts, setFacts] = useState<ClinicalFact[]>([]);
  const [summary, setSummary] = useState<PatientSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Focus area selection
  const [selectedFocusAreas, setSelectedFocusAreas] = useState<string[]>([
    "problems",
    "meds",
    "labs",
  ]);

  // Highlighted citation
  const [highlightedCitation, setHighlightedCitation] = useState<string | null>(null);

  // Confidence trend data (accumulated from summaries)
  const [confidenceTrend, setConfidenceTrend] = useState<
    Array<{ timestamp: string; confidence: number; queryText?: string }>
  >([]);

  // Load patient data
  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [patientData, factsData] = await Promise.all([
        getPatient(patientId),
        getPatientFacts(patientId, { limit: 200 }),
      ]);
      setPatient(patientData);
      setFacts(factsData);
      setError(null);
    } catch (err) {
      console.error("Failed to load patient data:", err);
      setError("Failed to load patient information.");
    } finally {
      setIsLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Group facts by domain
  const factsByDomain = facts.reduce(
    (acc, fact) => {
      if (!acc[fact.domain]) acc[fact.domain] = [];
      acc[fact.domain].push(fact);
      return acc;
    },
    {} as Record<string, ClinicalFact[]>
  );

  // Convert clinical facts to API format
  const convertFactsToInput = (facts: ClinicalFact[]): PatientFactInput[] => {
    return facts.map((f) => ({
      fact_id: f.id,
      fact_type: mapDomainToFactType(f.domain),
      description: f.concept_name,
      code: f.omop_concept_id?.toString(),
      code_system: "OMOP",
      value: f.value || undefined,
      unit: f.unit || undefined,
      date: f.start_date || undefined,
      status: f.assertion === "present" ? "active" : f.assertion,
      source_document_id: undefined,
      confidence: f.confidence,
    }));
  };

  // Map domain to fact type
  const mapDomainToFactType = (domain: string): string => {
    const mapping: Record<string, string> = {
      condition: "problem",
      drug: "medication",
      measurement: "lab",
      observation: "vital",
      procedure: "encounter",
    };
    return mapping[domain] || domain;
  };

  // Handle summary generation
  const handleGenerateSummary = async () => {
    setIsGenerating(true);
    setError(null);
    setSummary(null);

    try {
      // Convert facts to input format
      const factInputs = convertFactsToInput(facts);

      const result = await generatePatientSummary({
        patient_id: patientId,
        facts: factInputs,
        focus_areas: selectedFocusAreas,
        include_citations: true,
      });

      setSummary(result);

      // Track confidence trend
      setConfidenceTrend((prev) => [
        ...prev,
        {
          timestamp: new Date().toISOString(),
          confidence:
            result.confidence === "high"
              ? 0.9
              : result.confidence === "medium"
                ? 0.7
                : 0.4,
          queryText: selectedFocusAreas.join(", "),
        },
      ]);
    } catch (err) {
      console.error("Summary generation failed:", err);
      setError("Failed to generate summary. Please try again.");
    } finally {
      setIsGenerating(false);
    }
  };

  // Toggle focus area
  const toggleFocusArea = (area: string) => {
    setSelectedFocusAreas((prev) =>
      prev.includes(area) ? prev.filter((a) => a !== area) : [...prev, area]
    );
  };

  // Copy summary to clipboard
  const handleCopy = async () => {
    if (summary) {
      await navigator.clipboard.writeText(summary.content);
      setSuccessMessage("Copied to clipboard!");
      setTimeout(() => setSuccessMessage(null), 2000);
    }
  };

  // Download summary as text
  const handleDownload = () => {
    if (summary) {
      const blob = new Blob([summary.content], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `patient_${patientId}_summary_${new Date().toISOString().split("T")[0]}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setSuccessMessage("Downloaded!");
      setTimeout(() => setSuccessMessage(null), 2000);
    }
  };

  // Find fact by ID
  const findFactById = (factId: string): ClinicalFact | undefined => {
    return facts.find((f) => f.id === factId);
  };

  // Highlight citation in summary
  const renderSummaryWithCitations = () => {
    if (!summary) return null;

    let content = summary.content;

    // Create a map of citations for highlighting
    const citationMap = new Map<string, FactCitation>();
    summary.citations.forEach((c) => {
      citationMap.set(c.text_span, c);
    });

    // Simple highlighting by wrapping cited text in spans
    // In a real implementation, you'd want more sophisticated text matching
    return (
      <div className="prose prose-sm dark:prose-invert max-w-none">
        <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
          {content}
        </pre>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href={`/patients/${patientId}/facts`}
                className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
              >
                &larr; Patient Facts
              </Link>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                Patient Summary
              </h1>
              {patient && (
                <Badge variant="outline" className="text-sm">
                  {patient.external_id}
                </Badge>
              )}
            </div>
            <div className="flex gap-2">
              <Link href={`/patients/${patientId}/graph`}>
                <Button variant="outline">
                  <ExternalLink className="mr-2 h-4 w-4" />
                  Knowledge Graph
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
          </div>
        ) : error && !patient ? (
          <Card className="mx-auto max-w-2xl">
            <CardContent className="py-8 text-center">
              <AlertCircle className="mx-auto h-12 w-12 text-red-400" />
              <p className="mt-2 text-zinc-500">{error}</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-6 lg:grid-cols-3">
            {/* Left Panel - Patient Info & Focus Areas */}
            <div className="space-y-6">
              {/* Patient Overview */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <User className="h-5 w-5" />
                    Patient Overview
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-xs text-zinc-500">Patient ID</div>
                      <div className="font-medium">{patient?.external_id}</div>
                    </div>
                    <div>
                      <div className="text-xs text-zinc-500">Total Facts</div>
                      <div className="font-medium">{facts.length}</div>
                    </div>
                  </div>

                  {/* Facts by Domain */}
                  <Separator />
                  <div className="space-y-2">
                    <div className="text-sm font-medium">Clinical Data</div>
                    {Object.entries(factsByDomain).map(([domain, domainFacts]) => {
                      const config = DOMAIN_CONFIG[domain];
                      if (!config) return null;
                      const Icon = config.icon;
                      return (
                        <div
                          key={domain}
                          className="flex items-center justify-between text-sm"
                        >
                          <div className="flex items-center gap-2">
                            <Icon className="h-4 w-4 text-zinc-400" />
                            <span>{config.label}</span>
                          </div>
                          <Badge variant="secondary" className="text-xs">
                            {domainFacts.length}
                          </Badge>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* Focus Area Selection */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Focus Areas</CardTitle>
                  <CardDescription>
                    Select areas to emphasize in the summary
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {FOCUS_AREAS.map((area) => {
                      const Icon = area.icon;
                      return (
                        <div
                          key={area.id}
                          className="flex items-center space-x-2"
                        >
                          <Checkbox
                            id={area.id}
                            checked={selectedFocusAreas.includes(area.id)}
                            onCheckedChange={() => toggleFocusArea(area.id)}
                          />
                          <Label
                            htmlFor={area.id}
                            className="flex items-center gap-2 cursor-pointer"
                          >
                            <Icon className="h-4 w-4 text-zinc-400" />
                            {area.label}
                          </Label>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* Generate Button */}
              <Button
                className="w-full"
                size="lg"
                onClick={handleGenerateSummary}
                disabled={isGenerating || facts.length === 0}
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-2 h-4 w-4" />
                    Generate Summary
                  </>
                )}
              </Button>

              {/* Citation Panel */}
              {summary && summary.citations.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Info className="h-4 w-4" />
                      Citations ({summary.citations.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[200px]">
                      <div className="space-y-2">
                        {summary.citations.map((citation, idx) => {
                          const fact = findFactById(citation.fact_id);
                          return (
                            <TooltipProvider key={idx}>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <div
                                    className={`cursor-pointer rounded border p-2 text-xs transition-colors hover:bg-zinc-100 dark:hover:bg-zinc-800 ${
                                      highlightedCitation === citation.fact_id
                                        ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                                        : ""
                                    }`}
                                    onMouseEnter={() =>
                                      setHighlightedCitation(citation.fact_id)
                                    }
                                    onMouseLeave={() => setHighlightedCitation(null)}
                                  >
                                    <div className="font-medium truncate">
                                      {citation.text_span}
                                    </div>
                                    <div className="text-zinc-500 truncate">
                                      {citation.source_description}
                                    </div>
                                  </div>
                                </TooltipTrigger>
                                <TooltipContent side="right" className="max-w-xs">
                                  {fact ? (
                                    <div>
                                      <div className="font-medium">{fact.concept_name}</div>
                                      <div className="text-xs text-zinc-400">
                                        {fact.domain} | {fact.assertion}
                                      </div>
                                      {fact.value && (
                                        <div className="text-xs">
                                          Value: {fact.value} {fact.unit}
                                        </div>
                                      )}
                                    </div>
                                  ) : (
                                    <div>Source fact not found</div>
                                  )}
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          );
                        })}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              )}

              {/* Confidence Trend */}
              {confidenceTrend.length > 1 && (
                <ConfidenceTrend data={confidenceTrend} patientId={patientId} />
              )}
            </div>

            {/* Main Panel - Generated Summary */}
            <div className="lg:col-span-2 space-y-6">
              {/* Messages */}
              {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950">
                  <div className="flex items-center gap-2 text-red-800 dark:text-red-200">
                    <AlertCircle className="h-4 w-4" />
                    {error}
                  </div>
                </div>
              )}

              {successMessage && (
                <div className="rounded-lg border border-green-200 bg-green-50 p-3 dark:border-green-900 dark:bg-green-950">
                  <div className="flex items-center gap-2 text-green-800 dark:text-green-200">
                    <CheckCircle className="h-4 w-4" />
                    {successMessage}
                  </div>
                </div>
              )}

              {/* Summary Card */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <FileText className="h-5 w-5" />
                      Patient Summary
                    </CardTitle>
                    {summary && (
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={handleCopy}>
                          <Copy className="h-4 w-4" />
                        </Button>
                        <Button variant="outline" size="sm" onClick={handleDownload}>
                          <Download className="h-4 w-4" />
                        </Button>
                      </div>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  {summary ? (
                    <div className="space-y-4">
                      {/* Summary Metadata */}
                      <div className="flex flex-wrap gap-2 items-center">
                        <Badge variant="outline">
                          {summary.fact_count} facts processed
                        </Badge>
                        <ConfidenceBadge
                          confidence={
                            summary.confidence === "high"
                              ? 0.9
                              : summary.confidence === "medium"
                                ? 0.7
                                : 0.4
                          }
                        />
                        <Badge variant="outline">
                          {summary.token_usage.toLocaleString()} tokens
                        </Badge>
                        <Badge variant="outline">
                          ${summary.cost_usd.toFixed(4)}
                        </Badge>
                      </div>

                      {/* Focus Areas Used */}
                      {summary.focus_areas.length > 0 && (
                        <div className="flex items-center gap-2 text-sm text-zinc-500">
                          <span>Focus:</span>
                          {summary.focus_areas.map((area) => (
                            <Badge key={area} variant="secondary" className="text-xs">
                              {area}
                            </Badge>
                          ))}
                        </div>
                      )}

                      {/* Summary Content */}
                      <Separator />
                      <div className="rounded-lg border bg-white p-4 dark:bg-zinc-950">
                        {renderSummaryWithCitations()}
                      </div>

                      {/* Section Tabs (if sections available) */}
                      {Object.keys(summary.sections).length > 0 && (
                        <>
                          <Separator />
                          <div className="space-y-4">
                            <div className="text-sm font-medium">Summary Sections</div>
                            {Object.entries(summary.sections).map(([key, content]) => (
                              <div key={key} className="rounded-lg border p-3">
                                <div className="text-xs font-medium uppercase text-zinc-500 mb-2">
                                  {key.replace(/_/g, " ")}
                                </div>
                                <pre className="whitespace-pre-wrap text-sm">
                                  {content}
                                </pre>
                              </div>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  ) : (
                    <div className="py-16 text-center">
                      <FileText className="mx-auto h-16 w-16 text-zinc-200 dark:text-zinc-800" />
                      <p className="mt-4 text-zinc-500">
                        {facts.length === 0
                          ? "No clinical facts available for this patient."
                          : "Select focus areas and click Generate Summary to create a patient summary."}
                      </p>
                      {facts.length > 0 && (
                        <p className="mt-2 text-sm text-zinc-400">
                          {facts.length} clinical facts will be analyzed.
                        </p>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Recent Facts Preview */}
              {!summary && facts.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Clinical Facts Preview</CardTitle>
                    <CardDescription>
                      Recent facts that will be included in the summary
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[300px]">
                      <div className="space-y-2">
                        {facts.slice(0, 20).map((fact) => {
                          const domainConfig = DOMAIN_CONFIG[fact.domain];
                          return (
                            <div
                              key={fact.id}
                              className="flex items-start gap-3 rounded border p-2 text-sm"
                            >
                              {domainConfig && (
                                <Badge className={`${domainConfig.color} shrink-0`}>
                                  {domainConfig.label}
                                </Badge>
                              )}
                              <div className="flex-1 min-w-0">
                                <div className="font-medium truncate">
                                  {fact.concept_name}
                                </div>
                                <div className="text-xs text-zinc-500">
                                  {fact.assertion} | {fact.temporality}
                                  {fact.value && ` | ${fact.value}${fact.unit ? ` ${fact.unit}` : ""}`}
                                </div>
                              </div>
                              <div className="text-xs text-zinc-400">
                                {(fact.confidence * 100).toFixed(0)}%
                              </div>
                            </div>
                          );
                        })}
                        {facts.length > 20 && (
                          <div className="text-center text-sm text-zinc-500 py-2">
                            + {facts.length - 20} more facts
                          </div>
                        )}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
