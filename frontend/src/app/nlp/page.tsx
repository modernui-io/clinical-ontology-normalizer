"use client";

import { useState, useMemo } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Brain,
  FileText,
  Search,
  Pill,
  Stethoscope,
  FlaskConical,
  Activity,
  MapPin,
  Clock,
  Download,
  Copy,
  Check,
  Loader2,
  AlertCircle,
  CheckCircle,
  XCircle,
  Sparkles,
  BarChart3,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  nlpExtractEntities,
  type NLPExtractedEntity,
  type NLPExtractionResult,
  type NLPEntityType,
  type NLPAssertionStatus,
} from "@/lib/api";

// ============================================================================
// Types & Constants
// ============================================================================

const ENTITY_TYPE_CONFIG: Record<
  NLPEntityType,
  {
    label: string;
    icon: React.ReactNode;
    color: string;
    bgColor: string;
    borderColor: string;
  }
> = {
  diagnosis: {
    label: "Diagnoses",
    icon: <Stethoscope className="h-4 w-4" />,
    color: "text-blue-700",
    bgColor: "bg-blue-100",
    borderColor: "border-blue-300",
  },
  medication: {
    label: "Medications",
    icon: <Pill className="h-4 w-4" />,
    color: "text-green-700",
    bgColor: "bg-green-100",
    borderColor: "border-green-300",
  },
  procedure: {
    label: "Procedures",
    icon: <Activity className="h-4 w-4" />,
    color: "text-purple-700",
    bgColor: "bg-purple-100",
    borderColor: "border-purple-300",
  },
  lab_result: {
    label: "Lab Results",
    icon: <FlaskConical className="h-4 w-4" />,
    color: "text-amber-700",
    bgColor: "bg-amber-100",
    borderColor: "border-amber-300",
  },
  vital_sign: {
    label: "Vital Signs",
    icon: <Activity className="h-4 w-4" />,
    color: "text-red-700",
    bgColor: "bg-red-100",
    borderColor: "border-red-300",
  },
  anatomical_location: {
    label: "Anatomy",
    icon: <MapPin className="h-4 w-4" />,
    color: "text-cyan-700",
    bgColor: "bg-cyan-100",
    borderColor: "border-cyan-300",
  },
  temporal: {
    label: "Temporal",
    icon: <Clock className="h-4 w-4" />,
    color: "text-gray-700",
    bgColor: "bg-gray-100",
    borderColor: "border-gray-300",
  },
  symptom: {
    label: "Symptoms",
    icon: <AlertCircle className="h-4 w-4" />,
    color: "text-orange-700",
    bgColor: "bg-orange-100",
    borderColor: "border-orange-300",
  },
  allergy: {
    label: "Allergies",
    icon: <XCircle className="h-4 w-4" />,
    color: "text-pink-700",
    bgColor: "bg-pink-100",
    borderColor: "border-pink-300",
  },
};

const ASSERTION_BADGES: Record<
  NLPAssertionStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  present: { label: "Present", variant: "default" },
  absent: { label: "Absent", variant: "destructive" },
  possible: { label: "Possible", variant: "secondary" },
  conditional: { label: "Conditional", variant: "outline" },
  hypothetical: { label: "Hypothetical", variant: "outline" },
  family_history: { label: "Family Hx", variant: "outline" },
};

const SAMPLE_NOTES = [
  {
    id: "hpi",
    title: "History of Present Illness",
    text: `HISTORY OF PRESENT ILLNESS:
The patient is a 65-year-old male with a history of type 2 diabetes mellitus, hypertension, and hyperlipidemia who presents with chest pain for the past 2 days. He describes the pain as pressure-like, substernal, radiating to the left arm, rated 7/10 in severity. The pain is worse with exertion and improved with rest. He denies shortness of breath, diaphoresis, or nausea. He has been taking metformin 1000mg twice daily, lisinopril 20mg daily, and atorvastatin 40mg daily. His last hemoglobin A1c was 7.2% three months ago.

PHYSICAL EXAMINATION:
Vital Signs: BP 148/92 mmHg, HR 88 bpm, RR 16, SpO2 98% on room air, Temp 98.6F
General: Alert and oriented, in no acute distress
Cardiovascular: Regular rate and rhythm, no murmurs, rubs, or gallops
Lungs: Clear to auscultation bilaterally

ASSESSMENT AND PLAN:
1. Acute coronary syndrome - rule out myocardial infarction. Will obtain serial troponins, EKG, and cardiology consult.
2. Type 2 diabetes mellitus - well controlled, continue current regimen
3. Hypertension - elevated today, likely secondary to pain. Monitor and adjust medications as needed.`,
  },
  {
    id: "discharge",
    title: "Discharge Summary",
    text: `DISCHARGE SUMMARY

DIAGNOSES:
1. Community-acquired pneumonia
2. Chronic obstructive pulmonary disease exacerbation
3. Type 2 diabetes mellitus
4. Essential hypertension

HOSPITAL COURSE:
The patient was admitted with productive cough, fever to 101.5F, and dyspnea. Chest X-ray showed right lower lobe infiltrate. Started on ceftriaxone 1g IV daily and azithromycin 500mg daily. Received albuterol and ipratropium nebulizers for COPD exacerbation. Blood glucose levels were managed with sliding scale insulin.

DISCHARGE MEDICATIONS:
1. Amoxicillin-clavulanate 875mg twice daily for 5 days
2. Prednisone taper: 40mg x 3 days, 20mg x 3 days, 10mg x 3 days
3. Albuterol inhaler 2 puffs every 4-6 hours as needed
4. Metformin 500mg twice daily
5. Amlodipine 5mg daily
6. Aspirin 81mg daily

FOLLOW-UP:
- Primary care physician in 1 week
- Pulmonology for spirometry in 4 weeks`,
  },
  {
    id: "procedure",
    title: "Procedure Note",
    text: `PROCEDURE NOTE

PROCEDURE: Colonoscopy with polypectomy

INDICATION: Screening colonoscopy in 55-year-old patient with family history of colon cancer

PREOPERATIVE DIAGNOSIS: Colon cancer screening
POSTOPERATIVE DIAGNOSIS: Colonic polyps

PROCEDURE DESCRIPTION:
After informed consent was obtained, the patient was placed in left lateral decubitus position. Propofol sedation was administered by anesthesia. The colonoscope was inserted and advanced to the cecum, confirmed by visualization of the appendiceal orifice and ileocecal valve.

Findings:
- Cecum: Normal
- Ascending colon: 8mm sessile polyp removed with snare polypectomy
- Transverse colon: Two 5mm polyps removed with cold snare technique
- Descending colon: Normal
- Sigmoid colon: 12mm pedunculated polyp removed with hot snare
- Rectum: Internal hemorrhoids noted

ESTIMATED BLOOD LOSS: Minimal
COMPLICATIONS: None

PATHOLOGY: Pending

RECOMMENDATIONS:
1. Clear liquid diet today, regular diet tomorrow
2. No aspirin or NSAIDs for 1 week
3. Follow-up pending pathology results`,
  },
];

// ============================================================================
// Utility Functions
// ============================================================================

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) return "text-green-600";
  if (confidence >= 0.6) return "text-amber-600";
  return "text-red-600";
}

function getConfidenceBg(confidence: number): string {
  if (confidence >= 0.8) return "bg-green-500";
  if (confidence >= 0.6) return "bg-amber-500";
  return "bg-red-500";
}

// ============================================================================
// Components
// ============================================================================

function HighlightedText({
  text,
  entities,
  selectedEntityTypes,
  onEntityClick,
}: {
  text: string;
  entities: NLPExtractedEntity[];
  selectedEntityTypes: Set<NLPEntityType>;
  onEntityClick: (entity: NLPExtractedEntity) => void;
}) {
  // Sort entities by start position
  const sortedEntities = useMemo(() => {
    return [...entities]
      .filter((e) => selectedEntityTypes.has(e.entity_type))
      .sort((a, b) => a.span.start - b.span.start);
  }, [entities, selectedEntityTypes]);

  // Build highlighted segments
  const segments = useMemo(() => {
    const result: Array<{
      text: string;
      entity?: NLPExtractedEntity;
      isHighlighted: boolean;
    }> = [];

    let lastIndex = 0;

    for (const entity of sortedEntities) {
      // Add text before this entity
      if (entity.span.start > lastIndex) {
        result.push({
          text: text.slice(lastIndex, entity.span.start),
          isHighlighted: false,
        });
      }

      // Add the entity
      if (entity.span.start >= lastIndex) {
        result.push({
          text: text.slice(entity.span.start, entity.span.end),
          entity,
          isHighlighted: true,
        });
        lastIndex = entity.span.end;
      }
    }

    // Add remaining text
    if (lastIndex < text.length) {
      result.push({
        text: text.slice(lastIndex),
        isHighlighted: false,
      });
    }

    return result;
  }, [text, sortedEntities]);

  return (
    <div className="font-mono text-sm leading-relaxed whitespace-pre-wrap">
      {segments.map((segment, idx) => {
        if (!segment.isHighlighted || !segment.entity) {
          return <span key={idx}>{segment.text}</span>;
        }

        const config = ENTITY_TYPE_CONFIG[segment.entity.entity_type];
        return (
          <span
            key={idx}
            className={cn(
              "cursor-pointer rounded px-1 py-0.5 transition-all hover:ring-2 hover:ring-offset-1",
              config.bgColor,
              config.color,
              segment.entity.assertion === "absent" && "line-through opacity-70"
            )}
            onClick={() => onEntityClick(segment.entity!)}
            title={`${segment.entity.normalized_text || segment.entity.text} (${config.label})`}
          >
            {segment.text}
          </span>
        );
      })}
    </div>
  );
}

function EntityCard({
  entity,
  isSelected,
  onClick,
}: {
  entity: NLPExtractedEntity;
  isSelected: boolean;
  onClick: () => void;
}) {
  const config = ENTITY_TYPE_CONFIG[entity.entity_type];
  const assertionInfo = ASSERTION_BADGES[entity.assertion];
  const [copied, setCopied] = useState(false);
  const bestCode = entity.normalized_codes?.[0];

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    const copyText = bestCode?.code
      ? `${bestCode.code} - ${entity.normalized_text || entity.text}`
      : entity.text;
    navigator.clipboard.writeText(copyText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success("Copied to clipboard");
  };

  return (
    <Card
      className={cn(
        "cursor-pointer transition-all hover:shadow-md",
        isSelected && "ring-2 ring-primary",
        config.borderColor,
        "border-l-4"
      )}
      onClick={onClick}
    >
      <CardContent className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0 space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={cn("flex items-center gap-1", config.color)}>
                {config.icon}
              </span>
              <span className="font-medium text-sm truncate">{entity.text}</span>
              {assertionInfo && (
                <Badge variant={assertionInfo.variant} className="text-xs">
                  {assertionInfo.label}
                </Badge>
              )}
            </div>

            {entity.normalized_text && entity.normalized_text !== entity.text && (
              <p className="text-xs text-muted-foreground">
                Normalized: {entity.normalized_text}
              </p>
            )}

            {bestCode?.code && (
              <div className="flex items-center gap-2">
                <code className="text-xs font-mono bg-muted px-1.5 py-0.5 rounded">
                  {bestCode.code}
                </code>
                {bestCode.system && (
                  <Badge variant="outline" className="text-xs">
                    {bestCode.system}
                  </Badge>
                )}
              </div>
            )}

            {entity.section && (
              <p className="text-xs text-muted-foreground">
                Section: {entity.section}
              </p>
            )}

            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-muted-foreground">Confidence:</span>
              <div className="flex items-center gap-1">
                <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className={cn("h-full rounded-full", getConfidenceBg(entity.confidence))}
                    style={{ width: `${entity.confidence * 100}%` }}
                  />
                </div>
                <span className={cn("text-xs font-medium", getConfidenceColor(entity.confidence))}>
                  {Math.round(entity.confidence * 100)}%
                </span>
              </div>
            </div>
          </div>

          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 shrink-0"
            onClick={handleCopy}
          >
            {copied ? (
              <Check className="h-3 w-3 text-green-500" />
            ) : (
              <Copy className="h-3 w-3" />
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function EntityTypeFilter({
  selectedTypes,
  onToggle,
  entityCounts,
}: {
  selectedTypes: Set<NLPEntityType>;
  onToggle: (type: NLPEntityType) => void;
  entityCounts: Record<NLPEntityType, number>;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {(Object.keys(ENTITY_TYPE_CONFIG) as NLPEntityType[]).map((type) => {
        const config = ENTITY_TYPE_CONFIG[type];
        const count = entityCounts[type] || 0;
        const isSelected = selectedTypes.has(type);

        return (
          <Badge
            key={type}
            variant={isSelected ? "default" : "outline"}
            className={cn(
              "cursor-pointer transition-all gap-1",
              isSelected && config.bgColor,
              isSelected && config.color
            )}
            onClick={() => onToggle(type)}
          >
            {config.icon}
            {config.label}
            {count > 0 && (
              <span className="ml-1 text-xs opacity-70">({count})</span>
            )}
          </Badge>
        );
      })}
    </div>
  );
}

function StatsPanel({ result }: { result: NLPExtractionResult }) {
  const assertionCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    result.entities.forEach((e) => {
      counts[e.assertion] = (counts[e.assertion] || 0) + 1;
    });
    return counts;
  }, [result.entities]);

  const avgConfidence = useMemo(() => {
    if (result.entities.length === 0) return 0;
    const sum = result.entities.reduce((acc, e) => acc + e.confidence, 0);
    return sum / result.entities.length;
  }, [result.entities]);

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-md bg-blue-100">
              <Brain className="h-4 w-4 text-blue-700" />
            </div>
            <div>
              <p className="text-2xl font-bold">{result.entities.length}</p>
              <p className="text-xs text-muted-foreground">Total Entities</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-md bg-green-100">
              <CheckCircle className="h-4 w-4 text-green-700" />
            </div>
            <div>
              <p className="text-2xl font-bold">{assertionCounts.affirmed || 0}</p>
              <p className="text-xs text-muted-foreground">Affirmed</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-md bg-red-100">
              <XCircle className="h-4 w-4 text-red-700" />
            </div>
            <div>
              <p className="text-2xl font-bold">{assertionCounts.negated || 0}</p>
              <p className="text-xs text-muted-foreground">Negated</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-md bg-purple-100">
              <BarChart3 className="h-4 w-4 text-purple-700" />
            </div>
            <div>
              <p className="text-2xl font-bold">{Math.round(avgConfidence * 100)}%</p>
              <p className="text-xs text-muted-foreground">Avg Confidence</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function ExportPanel({
  result,
  inputText,
}: {
  result: NLPExtractionResult;
  inputText: string;
}) {
  const [exporting, setExporting] = useState(false);

  const exportAsJSON = () => {
    setExporting(true);
    try {
      const exportData = {
        text: inputText,
        extraction_result: result,
        exported_at: new Date().toISOString(),
      };
      const blob = new Blob([JSON.stringify(exportData, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `nlp-extraction-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Exported as JSON");
    } finally {
      setExporting(false);
    }
  };

  const exportAsFHIR = () => {
    setExporting(true);
    try {
      // Convert to FHIR-like format
      const fhirBundle = {
        resourceType: "Bundle",
        type: "collection",
        timestamp: new Date().toISOString(),
        entry: result.entities.map((entity, idx) => {
          const resource: Record<string, unknown> = {
            resourceType: entity.entity_type === "diagnosis" ? "Condition" :
                         entity.entity_type === "medication" ? "MedicationStatement" :
                         entity.entity_type === "procedure" ? "Procedure" :
                         entity.entity_type === "lab_result" ? "Observation" :
                         entity.entity_type === "vital_sign" ? "Observation" : "Basic",
            id: `entity-${idx}`,
            text: {
              status: "generated",
              div: `<div>${entity.text}</div>`,
            },
          };

          const bestNormalizedCode = entity.normalized_codes?.[0];
          if (bestNormalizedCode?.code) {
            resource.code = {
              coding: [
                {
                  system: bestNormalizedCode.system === "SNOMED-CT" ? "http://snomed.info/sct" :
                         bestNormalizedCode.system === "RxNorm" ? "http://www.nlm.nih.gov/research/umls/rxnorm" :
                         bestNormalizedCode.system === "LOINC" ? "http://loinc.org" :
                         bestNormalizedCode.system === "ICD-10-CM" ? "http://hl7.org/fhir/sid/icd-10-cm" :
                         "http://example.org/codes",
                  code: bestNormalizedCode.code,
                  display: entity.normalized_text || entity.text,
                },
              ],
              text: entity.text,
            };
          }

          return {
            resource,
          };
        }),
      };

      const blob = new Blob([JSON.stringify(fhirBundle, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `nlp-fhir-bundle-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Exported as FHIR Bundle");
    } finally {
      setExporting(false);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <Download className="h-4 w-4" />
          Export Results
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={exportAsJSON}
            disabled={exporting}
          >
            {exporting ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <FileText className="h-4 w-4 mr-2" />
            )}
            Export JSON
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={exportAsFHIR}
            disabled={exporting}
          >
            {exporting ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <FileText className="h-4 w-4 mr-2" />
            )}
            Export FHIR
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Main Page
// ============================================================================

export default function NLPWorkbenchPage() {
  const [inputText, setInputText] = useState("");
  const [isExtracting, setIsExtracting] = useState(false);
  const [result, setResult] = useState<NLPExtractionResult | null>(null);
  const [selectedEntityTypes, setSelectedEntityTypes] = useState<Set<NLPEntityType>>(
    new Set(Object.keys(ENTITY_TYPE_CONFIG) as NLPEntityType[])
  );
  const [selectedEntity, setSelectedEntity] = useState<NLPExtractedEntity | null>(null);
  const [activeTab, setActiveTab] = useState("all");

  // Calculate entity counts
  const entityCounts = useMemo(() => {
    const counts: Record<NLPEntityType, number> = {
      diagnosis: 0,
      medication: 0,
      procedure: 0,
      lab_result: 0,
      vital_sign: 0,
      anatomical_location: 0,
      temporal: 0,
      symptom: 0,
      allergy: 0,
    };
    if (result) {
      result.entities.forEach((e) => {
        counts[e.entity_type]++;
      });
    }
    return counts;
  }, [result]);

  // Filter entities by selected types and active tab
  const filteredEntities = useMemo(() => {
    if (!result) return [];
    return result.entities.filter((e) => {
      if (!selectedEntityTypes.has(e.entity_type)) return false;
      if (activeTab === "all") return true;
      return e.entity_type === activeTab;
    });
  }, [result, selectedEntityTypes, activeTab]);

  const handleExtract = async () => {
    if (!inputText.trim()) {
      toast.error("Please enter clinical text to analyze");
      return;
    }

    setIsExtracting(true);
    setResult(null);
    setSelectedEntity(null);

    try {
      const extractionResult = await nlpExtractEntities({
        text: inputText,
        detect_negation: true,
        detect_sections: true,
        normalize_entities: true,
        entity_types: Array.from(selectedEntityTypes),
      });
      setResult(extractionResult);
      toast.success(
        `Extracted ${extractionResult.entities.length} entities in ${extractionResult.processing_time_ms}ms`
      );
    } catch (error) {
      console.error("Extraction failed:", error);
      toast.error("Failed to extract entities. Please try again.");
    } finally {
      setIsExtracting(false);
    }
  };

  const handleLoadSample = (sampleText: string) => {
    setInputText(sampleText);
    setResult(null);
    setSelectedEntity(null);
  };

  const handleToggleEntityType = (type: NLPEntityType) => {
    setSelectedEntityTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  const handleSelectAllTypes = () => {
    setSelectedEntityTypes(new Set(Object.keys(ENTITY_TYPE_CONFIG) as NLPEntityType[]));
  };

  const handleClearTypes = () => {
    setSelectedEntityTypes(new Set());
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Brain className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              NLP Entity Extraction Workbench
            </h1>
            <p className="text-muted-foreground">
              Extract and normalize clinical entities from unstructured text
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Input Panel */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Clinical Text Input
              </CardTitle>
              <CardDescription>
                Paste clinical notes, discharge summaries, or other medical text
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                placeholder="Enter clinical text here..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                className="min-h-[300px] font-mono text-sm"
              />

              <div className="flex items-center justify-between">
                <div className="flex gap-2">
                  <Select onValueChange={(id) => {
                    const sample = SAMPLE_NOTES.find((s) => s.id === id);
                    if (sample) handleLoadSample(sample.text);
                  }}>
                    <SelectTrigger className="w-[200px]">
                      <SelectValue placeholder="Load sample note..." />
                    </SelectTrigger>
                    <SelectContent>
                      {SAMPLE_NOTES.map((sample) => (
                        <SelectItem key={sample.id} value={sample.id}>
                          {sample.title}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <Button
                  onClick={handleExtract}
                  disabled={isExtracting || !inputText.trim()}
                >
                  {isExtracting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Extracting...
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4 mr-2" />
                      Extract Entities
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Entity Type Filter */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">Entity Type Filter</CardTitle>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={handleSelectAllTypes}>
                    Select All
                  </Button>
                  <Button variant="ghost" size="sm" onClick={handleClearTypes}>
                    Clear
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <EntityTypeFilter
                selectedTypes={selectedEntityTypes}
                onToggle={handleToggleEntityType}
                entityCounts={entityCounts}
              />
            </CardContent>
          </Card>

          {/* Export Panel */}
          {result && <ExportPanel result={result} inputText={inputText} />}
        </div>

        {/* Results Panel */}
        <div className="space-y-4">
          {result ? (
            <>
              {/* Stats */}
              <StatsPanel result={result} />

              {/* Highlighted Text */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Search className="h-4 w-4" />
                    Annotated Text
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-[250px] rounded-md border p-4">
                    <HighlightedText
                      text={inputText}
                      entities={result.entities}
                      selectedEntityTypes={selectedEntityTypes}
                      onEntityClick={setSelectedEntity}
                    />
                  </ScrollArea>
                </CardContent>
              </Card>

              {/* Entity List with Tabs */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Activity className="h-4 w-4" />
                    Extracted Entities ({filteredEntities.length})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Tabs value={activeTab} onValueChange={setActiveTab}>
                    <TabsList className="flex flex-wrap h-auto gap-1 mb-4">
                      <TabsTrigger value="all" className="text-xs">
                        All ({result.entities.length})
                      </TabsTrigger>
                      {(Object.keys(ENTITY_TYPE_CONFIG) as NLPEntityType[]).map((type) => {
                        const count = entityCounts[type];
                        if (count === 0) return null;
                        const config = ENTITY_TYPE_CONFIG[type];
                        return (
                          <TabsTrigger key={type} value={type} className="text-xs gap-1">
                            {config.icon}
                            {config.label} ({count})
                          </TabsTrigger>
                        );
                      })}
                    </TabsList>

                    <ScrollArea className="h-[400px]">
                      <div className="space-y-2 pr-4">
                        {filteredEntities.length === 0 ? (
                          <div className="text-center py-8 text-muted-foreground">
                            <AlertCircle className="h-8 w-8 mx-auto mb-2 opacity-50" />
                            <p>No entities found for selected filters</p>
                          </div>
                        ) : (
                          filteredEntities.map((entity, idx) => (
                            <EntityCard
                              key={`${entity.text}-${entity.span.start}-${idx}`}
                              entity={entity}
                              isSelected={selectedEntity === entity}
                              onClick={() => setSelectedEntity(entity)}
                            />
                          ))
                        )}
                      </div>
                    </ScrollArea>
                  </Tabs>
                </CardContent>
              </Card>
            </>
          ) : (
            <Card>
              <CardContent className="py-16">
                <div className="text-center space-y-4">
                  <div className="flex justify-center">
                    <div className="flex h-20 w-20 items-center justify-center rounded-full bg-muted">
                      <Brain className="h-10 w-10 text-muted-foreground" />
                    </div>
                  </div>
                  <div>
                    <h3 className="text-lg font-medium">Ready to Extract</h3>
                    <p className="text-muted-foreground max-w-md mx-auto">
                      Enter clinical text or load a sample note, then click
                      &quot;Extract Entities&quot; to identify diagnoses, medications,
                      procedures, and more.
                    </p>
                  </div>
                  <div className="flex flex-col items-center gap-2">
                    <p className="text-sm text-muted-foreground">Try a sample:</p>
                    <div className="flex gap-2">
                      {SAMPLE_NOTES.map((sample) => (
                        <Button
                          key={sample.id}
                          variant="outline"
                          size="sm"
                          onClick={() => handleLoadSample(sample.text)}
                        >
                          {sample.title}
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
