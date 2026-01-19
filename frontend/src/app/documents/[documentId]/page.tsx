"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  getDocument,
  getDocumentMentions,
  previewExtraction,
  getPatientFacts,
  Document,
  ClinicalFact,
} from "@/lib/api";
import {
  MentionHighlighter,
  MentionLegend,
  MentionDetail,
} from "@/components/MentionHighlighter";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-yellow-500",
  processing: "bg-blue-500",
  completed: "bg-green-500",
  failed: "bg-red-500",
};

const DOMAIN_COLORS: Record<string, string> = {
  Condition: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-200",
  Drug: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-200",
  Measurement: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-200",
  Procedure: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-200",
  Observation: "bg-gray-100 text-gray-800 dark:bg-gray-700/30 dark:text-gray-200",
};

interface MentionSpan {
  text: string;
  start_offset: number;
  end_offset: number;
  assertion: string;
  temporality: string;
  confidence: number;
  section: string | null;
  domain?: string | null;
}

export default function DocumentViewerPage() {
  const params = useParams();
  const documentId = params.documentId as string;
  const [document, setDocument] = useState<Document | null>(null);
  const [mentions, setMentions] = useState<MentionSpan[]>([]);
  const [clinicalFacts, setClinicalFacts] = useState<ClinicalFact[]>([]);
  const [selectedMention, setSelectedMention] = useState<MentionSpan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoadingMentions, setIsLoadingMentions] = useState(false);
  const [extractionTime, setExtractionTime] = useState<number | null>(null);

  // Filter states
  const [mentionTypeFilter, setMentionTypeFilter] = useState<string>("all");
  const [mentionSearchQuery, setMentionSearchQuery] = useState("");
  const [factDomainFilter, setFactDomainFilter] = useState<string>("all");

  useEffect(() => {
    if (!documentId) return;

    const fetchDocument = async () => {
      try {
        const doc = await getDocument(documentId);
        setDocument(doc);
        setError(null);

        // If document is completed, fetch stored mentions
        if (doc.status === "completed") {
          try {
            const dbMentions = await getDocumentMentions(documentId);
            const mentionSpans: MentionSpan[] = dbMentions.map((m) => ({
              text: m.text,
              start_offset: m.start_offset,
              end_offset: m.end_offset,
              assertion: m.assertion,
              temporality: m.temporality,
              confidence: m.confidence,
              section: m.section,
              domain: null,
            }));
            setMentions(mentionSpans);
          } catch {
            // No mentions yet, that's ok
          }

          // Also fetch clinical facts for this patient
          try {
            const facts = await getPatientFacts(doc.patient_id);
            setClinicalFacts(facts);
          } catch {
            // No facts yet, that's ok
          }
        }
      } catch (err) {
        console.error("Failed to fetch document:", err);
        setError("Failed to fetch document. Is the backend running?");
      }
    };

    fetchDocument();
  }, [documentId]);

  const handlePreviewExtraction = useCallback(async () => {
    if (!document) return;

    setIsLoadingMentions(true);
    setSelectedMention(null);
    try {
      const result = await previewExtraction(document.text, document.note_type);
      const mentionSpans: MentionSpan[] = result.mentions.map((m) => ({
        text: m.text,
        start_offset: m.start_offset,
        end_offset: m.end_offset,
        assertion: m.assertion,
        temporality: m.temporality,
        confidence: m.confidence,
        section: m.section,
        domain: m.domain,
      }));
      setMentions(mentionSpans);
      setExtractionTime(result.extraction_time_ms);
    } catch (err) {
      console.error("Failed to preview extraction:", err);
      toast.error("Failed to extract mentions");
    } finally {
      setIsLoadingMentions(false);
    }
  }, [document]);

  const handleMentionClick = useCallback((mention: MentionSpan) => {
    setSelectedMention(mention);
  }, []);

  // Filtered mentions
  const filteredMentions = useMemo(() => {
    return mentions.filter((m) => {
      const matchesType = mentionTypeFilter === "all" || m.domain === mentionTypeFilter;
      const matchesSearch = !mentionSearchQuery ||
        m.text.toLowerCase().includes(mentionSearchQuery.toLowerCase());
      return matchesType && matchesSearch;
    });
  }, [mentions, mentionTypeFilter, mentionSearchQuery]);

  // Group mentions by domain for summary
  const mentionsByDomain = useMemo(() => {
    return mentions.reduce(
      (acc, m) => {
        const domain = m.domain || "Unknown";
        acc[domain] = (acc[domain] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>
    );
  }, [mentions]);

  // Group clinical facts by domain
  const factsByDomain = useMemo(() => {
    return clinicalFacts.reduce(
      (acc, fact) => {
        if (!acc[fact.domain]) {
          acc[fact.domain] = [];
        }
        acc[fact.domain].push(fact);
        return acc;
      },
      {} as Record<string, ClinicalFact[]>
    );
  }, [clinicalFacts]);

  // Filtered facts
  const filteredFacts = useMemo(() => {
    if (factDomainFilter === "all") return clinicalFacts;
    return clinicalFacts.filter((f) => f.domain === factDomainFilter);
  }, [clinicalFacts, factDomainFilter]);

  // Export functions
  const exportToJSON = useCallback(() => {
    const exportData = {
      document: {
        id: document?.id,
        patient_id: document?.patient_id,
        note_type: document?.note_type,
        status: document?.status,
        created_at: document?.created_at,
      },
      mentions: mentions,
      clinical_facts: clinicalFacts,
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement("a");
    a.href = url;
    a.download = `document-${documentId}-export.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Exported to JSON");
  }, [document, mentions, clinicalFacts, documentId]);

  const exportToFHIR = useCallback(() => {
    // Create a simplified FHIR Bundle structure
    const fhirBundle = {
      resourceType: "Bundle",
      type: "collection",
      entry: [
        {
          resource: {
            resourceType: "DocumentReference",
            id: document?.id,
            status: "current",
            subject: {
              reference: `Patient/${document?.patient_id}`,
            },
            type: {
              text: document?.note_type,
            },
            date: document?.created_at,
            content: [
              {
                attachment: {
                  contentType: "text/plain",
                  data: btoa(document?.text || ""),
                },
              },
            ],
          },
        },
        ...clinicalFacts.map((fact) => ({
          resource: {
            resourceType: fact.domain === "Condition" ? "Condition" :
                          fact.domain === "Drug" ? "MedicationStatement" :
                          fact.domain === "Procedure" ? "Procedure" : "Observation",
            id: fact.id,
            subject: {
              reference: `Patient/${fact.patient_id}`,
            },
            code: {
              coding: [
                {
                  system: "http://snomed.info/sct",
                  code: fact.omop_concept_id?.toString(),
                  display: fact.concept_name,
                },
              ],
            },
            status: fact.assertion === "present" ? "active" :
                    fact.assertion === "absent" ? "refuted" : "unconfirmed",
          },
        })),
      ],
    };

    const blob = new Blob([JSON.stringify(fhirBundle, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement("a");
    a.href = url;
    a.download = `document-${documentId}-fhir.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Exported to FHIR R4 format");
  }, [document, clinicalFacts, documentId]);

  const exportToOMOP = useCallback(() => {
    // Create OMOP CDM-style export
    const omopData = {
      note: {
        note_id: document?.id,
        person_id: document?.patient_id,
        note_type_concept_id: 44814637, // Clinical note
        note_text: document?.text,
        note_date: document?.created_at?.split("T")[0],
      },
      condition_occurrence: clinicalFacts
        .filter((f) => f.domain === "Condition")
        .map((f) => ({
          condition_occurrence_id: f.id,
          person_id: f.patient_id,
          condition_concept_id: f.omop_concept_id,
          condition_source_value: f.concept_name,
          condition_start_date: f.start_date,
        })),
      drug_exposure: clinicalFacts
        .filter((f) => f.domain === "Drug")
        .map((f) => ({
          drug_exposure_id: f.id,
          person_id: f.patient_id,
          drug_concept_id: f.omop_concept_id,
          drug_source_value: f.concept_name,
          drug_exposure_start_date: f.start_date,
        })),
      procedure_occurrence: clinicalFacts
        .filter((f) => f.domain === "Procedure")
        .map((f) => ({
          procedure_occurrence_id: f.id,
          person_id: f.patient_id,
          procedure_concept_id: f.omop_concept_id,
          procedure_source_value: f.concept_name,
          procedure_date: f.start_date,
        })),
      measurement: clinicalFacts
        .filter((f) => f.domain === "Measurement")
        .map((f) => ({
          measurement_id: f.id,
          person_id: f.patient_id,
          measurement_concept_id: f.omop_concept_id,
          measurement_source_value: f.concept_name,
          measurement_date: f.start_date,
          value_source_value: f.value,
          unit_source_value: f.unit,
        })),
    };

    const blob = new Blob([JSON.stringify(omopData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement("a");
    a.href = url;
    a.download = `document-${documentId}-omop.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Exported to OMOP CDM format");
  }, [document, clinicalFacts, documentId]);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <Link href="/documents" className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
              &larr; Documents
            </Link>
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
              Document Viewer
            </h1>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {error ? (
          <Card className="mx-auto max-w-4xl">
            <CardContent className="py-8">
              <div className="rounded-lg bg-red-50 p-4 text-red-800 dark:bg-red-900/20 dark:text-red-200">
                {error}
              </div>
            </CardContent>
          </Card>
        ) : document ? (
          <div className="mx-auto max-w-6xl space-y-6">
            {/* Document Header */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>{document.note_type}</CardTitle>
                    <CardDescription>
                      Patient: {document.patient_id} | Document ID: {document.id}
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={STATUS_COLORS[document.status] || "bg-gray-500"}>
                      {document.status.toUpperCase()}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
            </Card>

            {/* Main Tabs */}
            <Tabs defaultValue="text" className="w-full">
              <TabsList className="grid w-full grid-cols-5">
                <TabsTrigger value="text">Text View</TabsTrigger>
                <TabsTrigger value="mentions">
                  Mentions {mentions.length > 0 && `(${mentions.length})`}
                </TabsTrigger>
                <TabsTrigger value="facts">
                  Clinical Facts {clinicalFacts.length > 0 && `(${clinicalFacts.length})`}
                </TabsTrigger>
                <TabsTrigger value="graph">Knowledge Graph</TabsTrigger>
                <TabsTrigger value="export">Export</TabsTrigger>
              </TabsList>

              {/* Text View Tab */}
              <TabsContent value="text">
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>Clinical Note</CardTitle>
                        <CardDescription>
                          {mentions.length > 0
                            ? `${mentions.length} mentions highlighted`
                            : "Click 'Extract Mentions' to highlight clinical terms"}
                        </CardDescription>
                      </div>
                      <div className="flex items-center gap-2">
                        {extractionTime !== null && (
                          <span className="text-sm text-zinc-500">
                            {extractionTime.toFixed(1)}ms
                          </span>
                        )}
                        <Button
                          onClick={handlePreviewExtraction}
                          disabled={isLoadingMentions}
                          size="sm"
                        >
                          {isLoadingMentions ? (
                            <>
                              <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900" />
                              Extracting...
                            </>
                          ) : (
                            "Extract Mentions"
                          )}
                        </Button>
                      </div>
                    </div>
                    {mentions.length > 0 && <MentionLegend className="mt-4" />}
                  </CardHeader>
                  <CardContent>
                    <MentionHighlighter
                      text={document.text}
                      mentions={mentions}
                      onMentionClick={handleMentionClick}
                      selectedMention={selectedMention}
                    />
                  </CardContent>
                </Card>

                {selectedMention && (
                  <Card className="mt-4">
                    <CardHeader>
                      <CardTitle className="text-lg">Mention Details</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <MentionDetail mention={selectedMention} />
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              {/* Mentions Tab */}
              <TabsContent value="mentions">
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>Extracted Mentions</CardTitle>
                        <CardDescription>
                          {mentions.length > 0
                            ? `${filteredMentions.length} of ${mentions.length} clinical terms`
                            : "No mentions extracted yet"}
                        </CardDescription>
                      </div>
                      {mentions.length === 0 && (
                        <Button onClick={handlePreviewExtraction} disabled={isLoadingMentions}>
                          Extract Now
                        </Button>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    {mentions.length > 0 ? (
                      <div className="space-y-4">
                        {/* Filters */}
                        <div className="flex flex-wrap items-center gap-4">
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-zinc-500">Filter by type:</span>
                            <select
                              className="rounded-md border px-2 py-1 text-sm"
                              value={mentionTypeFilter}
                              onChange={(e) => setMentionTypeFilter(e.target.value)}
                            >
                              <option value="all">All Types</option>
                              {Object.keys(mentionsByDomain).map((domain) => (
                                <option key={domain} value={domain}>
                                  {domain} ({mentionsByDomain[domain]})
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-zinc-500">Search:</span>
                            <Input
                              placeholder="Search mentions..."
                              className="h-8 w-48"
                              value={mentionSearchQuery}
                              onChange={(e) => setMentionSearchQuery(e.target.value)}
                            />
                          </div>
                        </div>

                        {/* Summary badges */}
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(mentionsByDomain)
                            .sort(([, a], [, b]) => b - a)
                            .map(([domain, count]) => (
                              <Badge
                                key={domain}
                                variant="outline"
                                className={`cursor-pointer ${mentionTypeFilter === domain ? "ring-2 ring-blue-500" : ""}`}
                                onClick={() => setMentionTypeFilter(mentionTypeFilter === domain ? "all" : domain)}
                              >
                                {domain}: {count}
                              </Badge>
                            ))}
                        </div>

                        {/* Mentions table */}
                        <div className="rounded-lg border">
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead>Text</TableHead>
                                <TableHead>Domain</TableHead>
                                <TableHead>Assertion</TableHead>
                                <TableHead>Temporality</TableHead>
                                <TableHead>Section</TableHead>
                                <TableHead className="text-right">Confidence</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {filteredMentions.map((m, i) => (
                                <TableRow
                                  key={i}
                                  className="cursor-pointer"
                                  onClick={() => setSelectedMention(m)}
                                >
                                  <TableCell className="font-medium">{m.text}</TableCell>
                                  <TableCell>
                                    <Badge
                                      variant="outline"
                                      className={DOMAIN_COLORS[m.domain || "Observation"] || DOMAIN_COLORS.Observation}
                                    >
                                      {m.domain || "Unknown"}
                                    </Badge>
                                  </TableCell>
                                  <TableCell className="capitalize">{m.assertion}</TableCell>
                                  <TableCell className="capitalize">{m.temporality}</TableCell>
                                  <TableCell className="text-zinc-500">
                                    {m.section || "-"}
                                  </TableCell>
                                  <TableCell className="text-right">
                                    {(m.confidence * 100).toFixed(0)}%
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-8 text-zinc-500">
                        <p>Click &quot;Extract Now&quot; to run NLP extraction.</p>
                        <p className="text-sm mt-2">
                          This will identify clinical terms in the document.
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Clinical Facts Tab */}
              <TabsContent value="facts">
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>Clinical Facts</CardTitle>
                        <CardDescription>
                          {clinicalFacts.length > 0
                            ? `${filteredFacts.length} of ${clinicalFacts.length} clinical facts grouped by domain`
                            : "No clinical facts extracted yet"}
                        </CardDescription>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-zinc-500">Filter:</span>
                        <select
                          className="rounded-md border px-2 py-1 text-sm"
                          value={factDomainFilter}
                          onChange={(e) => setFactDomainFilter(e.target.value)}
                        >
                          <option value="all">All Domains</option>
                          {Object.keys(factsByDomain).map((domain) => (
                            <option key={domain} value={domain}>
                              {domain} ({factsByDomain[domain].length})
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {clinicalFacts.length > 0 ? (
                      <div className="space-y-6">
                        {/* Domain Cards */}
                        {Object.entries(factsByDomain)
                          .filter(([domain]) => factDomainFilter === "all" || domain === factDomainFilter)
                          .map(([domain, facts]) => (
                            <div key={domain} className="rounded-lg border">
                              <div className={`px-4 py-2 font-medium ${DOMAIN_COLORS[domain] || "bg-gray-100"}`}>
                                {domain} ({facts.length})
                              </div>
                              <Table>
                                <TableHeader>
                                  <TableRow>
                                    <TableHead>Concept</TableHead>
                                    <TableHead>OMOP ID</TableHead>
                                    <TableHead>Assertion</TableHead>
                                    <TableHead>Value</TableHead>
                                    <TableHead className="text-right">Confidence</TableHead>
                                  </TableRow>
                                </TableHeader>
                                <TableBody>
                                  {facts.map((fact) => (
                                    <TableRow key={fact.id}>
                                      <TableCell className="font-medium">
                                        {fact.concept_name}
                                      </TableCell>
                                      <TableCell className="font-mono text-xs">
                                        {fact.omop_concept_id}
                                      </TableCell>
                                      <TableCell>
                                        <Badge
                                          variant={fact.assertion === "present" ? "default" : "outline"}
                                          className={
                                            fact.assertion === "absent"
                                              ? "bg-red-100 text-red-800"
                                              : fact.assertion === "possible"
                                              ? "bg-yellow-100 text-yellow-800"
                                              : ""
                                          }
                                        >
                                          {fact.assertion}
                                        </Badge>
                                      </TableCell>
                                      <TableCell>
                                        {fact.value ? (
                                          <span>
                                            {fact.value}
                                            {fact.unit && ` ${fact.unit}`}
                                          </span>
                                        ) : (
                                          "-"
                                        )}
                                      </TableCell>
                                      <TableCell className="text-right">
                                        {(fact.confidence * 100).toFixed(0)}%
                                      </TableCell>
                                    </TableRow>
                                  ))}
                                </TableBody>
                              </Table>
                            </div>
                          ))}
                      </div>
                    ) : (
                      <div className="text-center py-8 text-zinc-500">
                        <p>No clinical facts available for this document.</p>
                        <p className="text-sm mt-2">
                          Facts are created after the document is processed.
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Knowledge Graph Tab */}
              <TabsContent value="graph">
                <Card>
                  <CardHeader>
                    <CardTitle>Knowledge Graph</CardTitle>
                    <CardDescription>
                      Visual representation of clinical entities and relationships
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                      <div className="mb-4 rounded-full bg-zinc-100 p-4 dark:bg-zinc-800">
                        <svg
                          className="h-12 w-12 text-zinc-400"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M13 10V3L4 14h7v7l9-11h-7z"
                          />
                        </svg>
                      </div>
                      <h3 className="text-lg font-medium">View Patient Knowledge Graph</h3>
                      <p className="mt-2 max-w-md text-sm text-zinc-500">
                        Explore the complete knowledge graph for this patient, including all
                        clinical entities, relationships, and temporal connections.
                      </p>
                      <Link href={`/patients/${document.patient_id}/graph`}>
                        <Button className="mt-4">
                          Open Patient Graph
                        </Button>
                      </Link>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Export Tab */}
              <TabsContent value="export">
                <Card>
                  <CardHeader>
                    <CardTitle>Export Options</CardTitle>
                    <CardDescription>
                      Export document data in various healthcare interoperability formats
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-4 md:grid-cols-3">
                      {/* JSON Export */}
                      <div className="rounded-lg border p-4">
                        <h3 className="font-medium">JSON Export</h3>
                        <p className="mt-1 text-sm text-zinc-500">
                          Raw JSON with document, mentions, and clinical facts
                        </p>
                        <Button
                          variant="outline"
                          className="mt-4 w-full"
                          onClick={exportToJSON}
                        >
                          Export JSON
                        </Button>
                      </div>

                      {/* FHIR Export */}
                      <div className="rounded-lg border p-4">
                        <h3 className="font-medium">FHIR R4 Bundle</h3>
                        <p className="mt-1 text-sm text-zinc-500">
                          HL7 FHIR R4 compliant bundle with resources
                        </p>
                        <Button
                          variant="outline"
                          className="mt-4 w-full"
                          onClick={exportToFHIR}
                        >
                          Export FHIR
                        </Button>
                      </div>

                      {/* OMOP Export */}
                      <div className="rounded-lg border p-4">
                        <h3 className="font-medium">OMOP CDM</h3>
                        <p className="mt-1 text-sm text-zinc-500">
                          OHDSI OMOP Common Data Model format
                        </p>
                        <Button
                          variant="outline"
                          className="mt-4 w-full"
                          onClick={exportToOMOP}
                        >
                          Export OMOP
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>

            {/* Document Metadata Card */}
            <Card>
              <CardHeader>
                <CardTitle>Document Metadata</CardTitle>
              </CardHeader>
              <CardContent>
                <dl className="grid grid-cols-2 gap-4 md:grid-cols-3">
                  <div>
                    <dt className="text-sm font-medium text-zinc-500">Patient ID</dt>
                    <dd className="text-lg">{document.patient_id}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-zinc-500">Note Type</dt>
                    <dd className="text-lg">{document.note_type}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-zinc-500">Status</dt>
                    <dd className="text-lg">{document.status}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-zinc-500">Created</dt>
                    <dd className="text-lg">
                      {new Date(document.created_at).toLocaleString()}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-zinc-500">Processed</dt>
                    <dd className="text-lg">
                      {document.processed_at
                        ? new Date(document.processed_at).toLocaleString()
                        : "Not yet"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-zinc-500">Job ID</dt>
                    <dd className="font-mono text-xs">{document.job_id}</dd>
                  </div>
                </dl>
              </CardContent>
            </Card>

            {/* Action Buttons */}
            <div className="flex gap-4">
              <Link href={`/patients/${document.patient_id}/graph`}>
                <Button>View Patient Graph</Button>
              </Link>
              <Link href={`/jobs/${document.job_id}`}>
                <Button variant="outline">View Job Status</Button>
              </Link>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
          </div>
        )}
      </main>
    </div>
  );
}
