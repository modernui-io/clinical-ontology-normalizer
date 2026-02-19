"use client";

import { useState, useMemo, useEffect } from "react";
import ReactMarkdown from "react-markdown";
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
import { Separator } from "@/components/ui/separator";
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
  ClipboardList,
  Network,
  ExternalLink,
  Send,
  MessageSquare,
  Lock,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import KnowledgeGraph from "@/components/KnowledgeGraph";
import { ConfidenceBadge } from "@/components/provenance/ConfidenceBadge";
import {
  DegradedBanner,
  EntityConfidenceBadge,
  isDegraded,
  isActionBlocked,
  type DegradedState,
} from "@/components/DegradedBanner";
import { RefusalCard } from "@/components/RefusalCard";
import { TransparencyHeader } from "@/components/TransparencyHeader";
import { GuidelineCitationCard, PolicyCitationCard } from "@/components/provenance/CitationCard";
import { ReasoningChain } from "@/components/provenance/ReasoningChain";
import type {
  GuidelineCitation,
  PolicyCitation,
  ReasoningStep,
} from "@/types/provenance";
import {
  nlpExtractEntities,
  nlpOntologyMap,
  nlpHybridAnalyze,
  type NLPExtractedEntity,
  type NLPExtractionResult,
  type NLPEntityType,
  type NLPAssertionStatus,
  type OntologyMapResponse,
  type HybridAnalyzeResponse,
  type AnalysisType,
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

const HYBRID_REASONER_MATRIX = [
  {
    path: "/api/v1/clinical-agent/query/{patient_id}",
    status: "canonical",
    note: "Graph-backed clinical reasoning for patient-scoped Q&A with provenance.",
  },
  {
    path: "/api/v1/clinical-agent/import",
    status: "canonical",
    note: "Canonical ingest and extraction entrypoint.",
  },
  {
    path: "/api/v1/clinical-agent/build-graph",
    status: "canonical",
    note: "Canonical graph construction endpoint for hybrid workflows.",
  },
  {
    path: "/api/v1/nlp/analyze",
    status: "compat mode",
    note: "Legacy text + hybrid analysis path used by this workbench compatibility mode.",
  },
  {
    path: "/api/v1/nlp/extract",
    status: "compat mode",
    note: "Legacy entity extraction route retained for older clients.",
  },
];

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

            {entity.normalized_codes && entity.normalized_codes.length > 0 && (
              <div className="flex flex-col gap-1">
                {entity.normalized_codes.map((code: { code: string; system?: string; display?: string }, idx: number) => (
                  <div key={idx} className="flex items-center gap-2 flex-wrap">
                    <code className="text-xs font-mono bg-muted px-1.5 py-0.5 rounded">
                      {code.code}
                    </code>
                    {code.system && (
                      <Badge variant="outline" className="text-xs">
                        {code.system}
                      </Badge>
                    )}
                    {code.display && (
                      <span className="text-xs text-muted-foreground truncate max-w-[200px]" title={code.display}>
                        {code.display}
                      </span>
                    )}
                  </div>
                ))}
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
                <EntityConfidenceBadge confidence={entity.confidence} />
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
  const affirmedCount = useMemo(() => {
    return result.entities.filter((e) => e.assertion === "present").length;
  }, [result.entities]);

  const negatedCount = useMemo(() => {
    return result.entities.filter((e) => e.assertion === "absent").length;
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
              <p className="text-2xl font-bold">{affirmedCount}</p>
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
              <p className="text-2xl font-bold">{negatedCount}</p>
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

// ============================================================================
// Hybrid Analyzer Components
// ============================================================================

const ANALYSIS_TYPE_CONFIG: Record<
  AnalysisType,
  { label: string; description: string }
> = {
  clinical_summary: {
    label: "Clinical Summary",
    description: "Overview of patient's clinical status",
  },
  risk_assessment: {
    label: "Risk Assessment",
    description: "Identify potential risks and concerns",
  },
  medication_review: {
    label: "Medication Review",
    description: "Analyze medications and interactions",
  },
  lab_interpretation: {
    label: "Lab Interpretation",
    description: "Interpret laboratory results",
  },
};

function OntologyStatsPanel({ result }: { result: OntologyMapResponse }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-md bg-green-100">
              <CheckCircle className="h-4 w-4 text-green-700" />
            </div>
            <div>
              <p className="text-2xl font-bold">{result.coverage_pct.toFixed(1)}%</p>
              <p className="text-xs text-muted-foreground">Token Coverage</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-md bg-blue-100">
              <Brain className="h-4 w-4 text-blue-700" />
            </div>
            <div>
              <p className="text-2xl font-bold">{result.entity_count}</p>
              <p className="text-xs text-muted-foreground">Entities Found</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-md bg-purple-100">
              <Activity className="h-4 w-4 text-purple-700" />
            </div>
            <div>
              <p className="text-2xl font-bold">{result.relationships.length}</p>
              <p className="text-xs text-muted-foreground">Relationships</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-md bg-amber-100">
              <Clock className="h-4 w-4 text-amber-700" />
            </div>
            <div>
              <p className="text-2xl font-bold">{result.processing_time_ms.toFixed(1)}ms</p>
              <p className="text-xs text-muted-foreground">Processing Time</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function HybridResultPanel({
  result,
  onBuildKnowledgeGraph,
  isBuildingGraph,
}: {
  result: HybridAnalyzeResponse;
  onBuildKnowledgeGraph?: () => void;
  isBuildingGraph?: boolean;
}) {
  const ctx = result.structured_context;

  return (
    <div className="space-y-4">
      {/* Stats Row */}
      <div className="grid gap-4 sm:grid-cols-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-md bg-green-100">
                <CheckCircle className="h-4 w-4 text-green-700" />
              </div>
              <div>
                <p className="text-lg font-bold">{ctx.coverage_pct.toFixed(1)}%</p>
                <p className="text-xs text-muted-foreground">Coverage</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-md bg-blue-100">
                <Brain className="h-4 w-4 text-blue-700" />
              </div>
              <div>
                <p className="text-lg font-bold">{ctx.entity_count}</p>
                <p className="text-xs text-muted-foreground">Entities</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-md bg-amber-100">
                <Clock className="h-4 w-4 text-amber-700" />
              </div>
              <div>
                <p className="text-lg font-bold">{result.extraction_time_ms.toFixed(1)}ms</p>
                <p className="text-xs text-muted-foreground">Extraction</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className={cn("p-2 rounded-md", result.llm_available ? "bg-green-100" : "bg-gray-100")}>
                <Sparkles className={cn("h-4 w-4", result.llm_available ? "text-green-700" : "text-gray-500")} />
              </div>
              <div>
                <p className="text-lg font-bold">{result.llm_available ? "Yes" : "No"}</p>
                <p className="text-xs text-muted-foreground">LLM Used</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* LLM Analysis */}
      {result.analysis && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Sparkles className="h-4 w-4" />
              {result.llm_available ? "LLM Analysis" : "Status"}
              {result.llm_model && (
                <Badge variant="outline" className="ml-2 text-xs">
                  {result.llm_model}
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[200px]">
              <div className="prose prose-sm max-w-none whitespace-pre-wrap">
                {result.analysis}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      )}

      {/* Clinical Summary - Human Readable */}
      {ctx.human_readable_summary && (
        <Card className="border-green-200 bg-green-50/30">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <ClipboardList className="h-4 w-4 text-green-700" />
              Clinical Summary
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[400px]">
              <div className="prose prose-sm max-w-none whitespace-pre-wrap text-gray-700">
                {ctx.human_readable_summary.split('\n').map((line, i) => {
                  if (line.startsWith('**') && line.endsWith('**')) {
                    return <p key={i} className="font-semibold text-gray-900 mt-3 first:mt-0">{line.replace(/\*\*/g, '')}</p>;
                  }
                  if (line.trim().startsWith('•')) {
                    return <p key={i} className="ml-2 text-sm">{line}</p>;
                  }
                  return line ? <p key={i} className="text-sm">{line}</p> : null;
                })}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      )}

      {/* Structured Context */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Structured Extraction
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[300px]">
            <div className="space-y-4">
              {/* Diagnoses */}
              {ctx.diagnoses.length > 0 && (
                <div>
                  <h4 className="font-medium text-sm text-blue-700 mb-2 flex items-center gap-2">
                    <Stethoscope className="h-4 w-4" />
                    Diagnoses ({ctx.diagnoses.length})
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {ctx.diagnoses.map((d, i) => (
                      <Badge
                        key={i}
                        variant={d.negated ? "destructive" : "default"}
                        className={cn("text-xs", d.negated && "line-through")}
                      >
                        {d.name}
                        {d.code && <span className="ml-1 opacity-70">({d.code})</span>}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Medications */}
              {ctx.medications.length > 0 && (
                <div>
                  <h4 className="font-medium text-sm text-green-700 mb-2 flex items-center gap-2">
                    <Pill className="h-4 w-4" />
                    Medications ({ctx.medications.length})
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {ctx.medications.map((m, i) => (
                      <Badge key={i} variant="outline" className="text-xs bg-green-50">
                        {m.name}
                        {m.dose && <span className="ml-1 opacity-70">{m.dose}</span>}
                        {m.frequency && <span className="ml-1 opacity-70">{m.frequency}</span>}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Labs */}
              {ctx.labs.length > 0 && (
                <div>
                  <h4 className="font-medium text-sm text-amber-700 mb-2 flex items-center gap-2">
                    <FlaskConical className="h-4 w-4" />
                    Labs ({ctx.labs.length})
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {ctx.labs.map((l, i) => (
                      <Badge
                        key={i}
                        variant="outline"
                        className={cn(
                          "text-xs",
                          l.flag === "high" && "bg-red-50 border-red-300",
                          l.flag === "low" && "bg-blue-50 border-blue-300",
                          !l.flag && "bg-amber-50"
                        )}
                      >
                        {l.name}: {l.value} {l.unit}
                        {l.flag && <span className="ml-1">({l.flag})</span>}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Vitals */}
              {ctx.vitals.length > 0 && (
                <div>
                  <h4 className="font-medium text-sm text-red-700 mb-2 flex items-center gap-2">
                    <Activity className="h-4 w-4" />
                    Vitals ({ctx.vitals.length})
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {ctx.vitals.map((v, i) => (
                      <Badge key={i} variant="outline" className="text-xs bg-red-50">
                        {v.name}: {v.value}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Symptoms */}
              {ctx.symptoms.length > 0 && (
                <div>
                  <h4 className="font-medium text-sm text-orange-700 mb-2 flex items-center gap-2">
                    <AlertCircle className="h-4 w-4" />
                    Symptoms ({ctx.symptoms.length})
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {ctx.symptoms.map((s, i) => (
                      <Badge
                        key={i}
                        variant={s.negated ? "destructive" : "outline"}
                        className={cn("text-xs", s.negated && "line-through", "bg-orange-50")}
                      >
                        {s.name}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Procedures */}
              {ctx.procedures.length > 0 && (
                <div>
                  <h4 className="font-medium text-sm text-purple-700 mb-2 flex items-center gap-2">
                    <Activity className="h-4 w-4" />
                    Procedures ({ctx.procedures.length})
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {ctx.procedures.map((p, i) => (
                      <Badge key={i} variant="outline" className="text-xs bg-purple-50">
                        {p.name}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Negated Findings */}
              {ctx.negated_findings.length > 0 && (
                <div>
                  <h4 className="font-medium text-sm text-gray-700 mb-2 flex items-center gap-2">
                    <XCircle className="h-4 w-4" />
                    Negated Findings ({ctx.negated_findings.length})
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {ctx.negated_findings.map((n, i) => (
                      <Badge key={i} variant="destructive" className="text-xs line-through">
                        {n}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Relationships */}
              {ctx.relationships.length > 0 && (
                <div>
                  <h4 className="font-medium text-sm text-cyan-700 mb-2">
                    Relationships ({ctx.relationships.length})
                  </h4>
                  <div className="space-y-1">
                    {ctx.relationships.slice(0, 10).map((r, i) => (
                      <div key={i} className="text-xs text-muted-foreground">
                        <span className="font-medium">{r.subject}</span>
                        <span className="mx-2">→</span>
                        <span className="text-cyan-600">{r.relation}</span>
                        <span className="mx-2">→</span>
                        <span className="font-medium">{r.object}</span>
                      </div>
                    ))}
                    {ctx.relationships.length > 10 && (
                      <p className="text-xs text-muted-foreground">
                        +{ctx.relationships.length - 10} more...
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Clinical Narrative — only show when there is actual content */}
      {result.narrative && result.narrative.extraction_confidence > 0 && (result.narrative.episodes?.length > 0 || result.narrative.admission_reason || result.narrative.hospital_course || result.narrative.discharge_plan) && (
        <Card className="border-purple-200 bg-purple-50/30">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <FileText className="h-4 w-4 text-purple-700" />
              Clinical Narrative
              <Badge variant="outline" className="ml-2 text-xs">
                {Math.round(result.narrative.extraction_confidence * 100)}% confident
              </Badge>
              {result.narrative.episodes && result.narrative.episodes.length > 0 && (
                <Badge variant="secondary" className="ml-1 text-xs">
                  {result.narrative.episodes.length} episode{result.narrative.episodes.length !== 1 ? 's' : ''}
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[500px]">
              <div className="space-y-6">
                {/* Multi-episode display */}
                {result.narrative.episodes && result.narrative.episodes.length > 0 ? (
                  result.narrative.episodes.map((episode, epIdx) => (
                    <div key={epIdx} className="space-y-3">
                      {/* Episode header */}
                      <div className="flex items-center gap-2 pb-1 border-b border-purple-200">
                        <Badge className="bg-purple-600 text-white text-xs">
                          Episode {epIdx + 1}
                        </Badge>
                        <span className="text-sm font-semibold text-purple-900">{episode.episode_label}</span>
                        {episode.episode_date && (
                          <span className="text-xs text-muted-foreground ml-auto">{episode.episode_date}</span>
                        )}
                      </div>

                      {/* Admission Reason */}
                      {episode.admission_reason && (
                        <div className="border-l-4 border-blue-400 pl-3">
                          <h4 className="font-medium text-sm text-blue-700 mb-2">Admission Reason</h4>
                          <p className="text-sm font-medium">{episode.admission_reason.primary_problem}</p>
                          {episode.admission_reason.contributing_factors && episode.admission_reason.contributing_factors.length > 0 && (
                            <div className="mt-2">
                              <span className="text-xs text-muted-foreground">Contributing factors: </span>
                              <span className="text-xs">{episode.admission_reason.contributing_factors.join(", ")}</span>
                            </div>
                          )}
                          {episode.admission_reason.presenting_symptoms && episode.admission_reason.presenting_symptoms.length > 0 && (
                            <div className="mt-1">
                              <span className="text-xs text-muted-foreground">Presenting symptoms: </span>
                              <span className="text-xs">{episode.admission_reason.presenting_symptoms.join(", ")}</span>
                            </div>
                          )}
                          {episode.admission_reason.admission_date && (
                            <p className="text-xs text-muted-foreground mt-1">Date: {episode.admission_reason.admission_date}</p>
                          )}
                        </div>
                      )}

                      {/* Hospital Course */}
                      {episode.hospital_course && (
                        <div className="border-l-4 border-amber-400 pl-3">
                          <h4 className="font-medium text-sm text-amber-700 mb-2">Hospital Course</h4>
                          <p className="text-sm">{episode.hospital_course.summary}</p>

                          {episode.hospital_course.key_events && episode.hospital_course.key_events.length > 0 && (
                            <div className="mt-3">
                              <p className="text-xs text-muted-foreground mb-1">Key Events:</p>
                              <div className="space-y-1 ml-2">
                                {episode.hospital_course.key_events.map((event: any, i: number) => (
                                  <div key={i} className="text-xs flex items-start gap-2">
                                    <span className="text-muted-foreground">{event.relative_day ? `Day ${event.relative_day}:` : "\u2022"}</span>
                                    <span>
                                      <Badge variant="outline" className="text-xs mr-1">{event.event_type}</Badge>
                                      {event.event_text}
                                      {event.severity && <span className="text-muted-foreground"> ({event.severity})</span>}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {episode.hospital_course.interventions && episode.hospital_course.interventions.length > 0 && (
                            <div className="mt-2">
                              <span className="text-xs text-muted-foreground">Interventions: </span>
                              <span className="text-xs">{episode.hospital_course.interventions.join(", ")}</span>
                            </div>
                          )}

                          {episode.hospital_course.complications && episode.hospital_course.complications.length > 0 && (
                            <div className="mt-1">
                              <span className="text-xs text-muted-foreground">Complications: </span>
                              <span className="text-xs text-red-600">{episode.hospital_course.complications.join(", ")}</span>
                            </div>
                          )}

                          {episode.hospital_course.response_to_treatment && (
                            <div className="mt-1">
                              <span className="text-xs text-muted-foreground">Response: </span>
                              <span className="text-xs">{episode.hospital_course.response_to_treatment}</span>
                            </div>
                          )}

                          {episode.hospital_course.length_of_stay_days && (
                            <p className="text-xs text-muted-foreground mt-1">Length of stay: {episode.hospital_course.length_of_stay_days} days</p>
                          )}
                        </div>
                      )}

                      {/* Discharge Plan */}
                      {episode.discharge_plan && (
                        <div className="border-l-4 border-green-400 pl-3">
                          <h4 className="font-medium text-sm text-green-700 mb-2">Discharge Plan</h4>
                          <p className="text-sm font-medium">Disposition: {episode.discharge_plan.disposition}</p>

                          {episode.discharge_plan.follow_up_appointments && episode.discharge_plan.follow_up_appointments.length > 0 && (
                            <div className="mt-2">
                              <span className="text-xs text-muted-foreground">Follow-up: </span>
                              <span className="text-xs">{episode.discharge_plan.follow_up_appointments.join(", ")}</span>
                            </div>
                          )}

                          {episode.discharge_plan.discharge_medications && episode.discharge_plan.discharge_medications.length > 0 && (
                            <div className="mt-1">
                              <span className="text-xs text-muted-foreground">Medications: </span>
                              <span className="text-xs">{episode.discharge_plan.discharge_medications.join(", ")}</span>
                            </div>
                          )}

                          {episode.discharge_plan.activity_restrictions && episode.discharge_plan.activity_restrictions.length > 0 && (
                            <div className="mt-1">
                              <span className="text-xs text-muted-foreground">Activity restrictions: </span>
                              <span className="text-xs">{episode.discharge_plan.activity_restrictions.join(", ")}</span>
                            </div>
                          )}

                          {episode.discharge_plan.return_precautions && episode.discharge_plan.return_precautions.length > 0 && (
                            <div className="mt-1">
                              <span className="text-xs text-muted-foreground">Return if: </span>
                              <span className="text-xs text-red-600">{episode.discharge_plan.return_precautions.join(", ")}</span>
                            </div>
                          )}

                          {episode.discharge_plan.discharge_date && (
                            <p className="text-xs text-muted-foreground mt-1">Date: {episode.discharge_plan.discharge_date}</p>
                          )}
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  /* Fallback: single narrative display for backward compatibility */
                  <div className="space-y-4">
                    {result.narrative.admission_reason && (
                      <div className="border-l-4 border-blue-400 pl-3">
                        <h4 className="font-medium text-sm text-blue-700 mb-2">Admission Reason</h4>
                        <p className="text-sm font-medium">{result.narrative.admission_reason.primary_problem}</p>
                        {result.narrative.admission_reason.contributing_factors.length > 0 && (
                          <div className="mt-2">
                            <span className="text-xs text-muted-foreground">Contributing factors: </span>
                            <span className="text-xs">{result.narrative.admission_reason.contributing_factors.join(", ")}</span>
                          </div>
                        )}
                        {result.narrative.admission_reason.presenting_symptoms.length > 0 && (
                          <div className="mt-1">
                            <span className="text-xs text-muted-foreground">Presenting symptoms: </span>
                            <span className="text-xs">{result.narrative.admission_reason.presenting_symptoms.join(", ")}</span>
                          </div>
                        )}
                        {result.narrative.admission_reason.admission_date && (
                          <p className="text-xs text-muted-foreground mt-1">Date: {result.narrative.admission_reason.admission_date}</p>
                        )}
                      </div>
                    )}

                    {result.narrative.hospital_course && (
                      <div className="border-l-4 border-amber-400 pl-3">
                        <h4 className="font-medium text-sm text-amber-700 mb-2">Hospital Course</h4>
                        <p className="text-sm">{result.narrative.hospital_course.summary}</p>

                        {result.narrative.hospital_course.key_events.length > 0 && (
                          <div className="mt-3">
                            <p className="text-xs text-muted-foreground mb-1">Key Events:</p>
                            <div className="space-y-1 ml-2">
                              {result.narrative.hospital_course.key_events.map((event, i) => (
                                <div key={i} className="text-xs flex items-start gap-2">
                                  <span className="text-muted-foreground">{event.relative_day ? `Day ${event.relative_day}:` : "\u2022"}</span>
                                  <span>
                                    <Badge variant="outline" className="text-xs mr-1">{event.event_type}</Badge>
                                    {event.event_text}
                                    {event.severity && <span className="text-muted-foreground"> ({event.severity})</span>}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {result.narrative.hospital_course.interventions.length > 0 && (
                          <div className="mt-2">
                            <span className="text-xs text-muted-foreground">Interventions: </span>
                            <span className="text-xs">{result.narrative.hospital_course.interventions.join(", ")}</span>
                          </div>
                        )}

                        {result.narrative.hospital_course.complications.length > 0 && (
                          <div className="mt-1">
                            <span className="text-xs text-muted-foreground">Complications: </span>
                            <span className="text-xs text-red-600">{result.narrative.hospital_course.complications.join(", ")}</span>
                          </div>
                        )}

                        {result.narrative.hospital_course.response_to_treatment && (
                          <div className="mt-1">
                            <span className="text-xs text-muted-foreground">Response: </span>
                            <span className="text-xs">{result.narrative.hospital_course.response_to_treatment}</span>
                          </div>
                        )}

                        {result.narrative.hospital_course.length_of_stay_days && (
                          <p className="text-xs text-muted-foreground mt-1">Length of stay: {result.narrative.hospital_course.length_of_stay_days} days</p>
                        )}
                      </div>
                    )}

                    {result.narrative.discharge_plan && (
                      <div className="border-l-4 border-green-400 pl-3">
                        <h4 className="font-medium text-sm text-green-700 mb-2">Discharge Plan</h4>
                        <p className="text-sm font-medium">Disposition: {result.narrative.discharge_plan.disposition}</p>

                        {result.narrative.discharge_plan.follow_up_appointments.length > 0 && (
                          <div className="mt-2">
                            <span className="text-xs text-muted-foreground">Follow-up: </span>
                            <span className="text-xs">{result.narrative.discharge_plan.follow_up_appointments.join(", ")}</span>
                          </div>
                        )}

                        {result.narrative.discharge_plan.discharge_medications.length > 0 && (
                          <div className="mt-1">
                            <span className="text-xs text-muted-foreground">Medications: </span>
                            <span className="text-xs">{result.narrative.discharge_plan.discharge_medications.join(", ")}</span>
                          </div>
                        )}

                        {result.narrative.discharge_plan.activity_restrictions.length > 0 && (
                          <div className="mt-1">
                            <span className="text-xs text-muted-foreground">Activity restrictions: </span>
                            <span className="text-xs">{result.narrative.discharge_plan.activity_restrictions.join(", ")}</span>
                          </div>
                        )}

                        {result.narrative.discharge_plan.return_precautions.length > 0 && (
                          <div className="mt-1">
                            <span className="text-xs text-muted-foreground">Return if: </span>
                            <span className="text-xs text-red-600">{result.narrative.discharge_plan.return_precautions.join(", ")}</span>
                          </div>
                        )}

                        {result.narrative.discharge_plan.discharge_date && (
                          <p className="text-xs text-muted-foreground mt-1">Date: {result.narrative.discharge_plan.discharge_date}</p>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      )}

      {/* Build Knowledge Graph Button */}
      {onBuildKnowledgeGraph && (
        <Card className="border-indigo-200 bg-indigo-50/30">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium">Build Knowledge Graph</p>
                <p className="text-xs text-muted-foreground">
                  Create a patient knowledge graph from the extracted entities for Q&A
                </p>
              </div>
              <Button
                onClick={onBuildKnowledgeGraph}
                disabled={isBuildingGraph || ctx.entity_count === 0}
                className="bg-gradient-to-r from-indigo-500 to-purple-500 hover:from-indigo-600 hover:to-purple-600"
              >
                {isBuildingGraph ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Building...
                  </>
                ) : (
                  <>
                    <Network className="h-4 w-4 mr-2" />
                    Build Graph
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ExportPanel({
  result,
  inputText,
  onBuildKnowledgeGraph,
  isBuildingGraph,
}: {
  result: NLPExtractionResult;
  inputText: string;
  onBuildKnowledgeGraph: () => void;
  isBuildingGraph: boolean;
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
          Export & Build
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
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

        <Separator />

        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Build a patient knowledge graph from the extracted entities
          </p>
          <Button
            onClick={onBuildKnowledgeGraph}
            disabled={isBuildingGraph || result.entities.length === 0}
            className="w-full bg-gradient-to-r from-indigo-500 to-purple-500 hover:from-indigo-600 hover:to-purple-600"
          >
            {isBuildingGraph ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Building Knowledge Graph...
              </>
            ) : (
              <>
                <Network className="h-4 w-4 mr-2" />
                Build Knowledge Graph
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Main Page
// ============================================================================

type WorkbenchMode = "extraction" | "hybrid" | "knowledge_graph" | "qa_agent";

// Knowledge Graph types
interface KGNode {
  id: string;
  node_type: string;
  label: string;
  omop_concept_id: number | null;
  properties: Record<string, unknown>;
  x?: number;
  y?: number;
}

interface KGEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: string;
  properties: Record<string, unknown>;
  // Temporal fields for the advanced KnowledgeGraph component
  temporality?: string | null;
  temporal_confidence?: number | null;
  event_date?: string | null;
}

interface KGSummary {
  patient_id: string;
  node_count: number;
  edge_count: number;
  conditions: string[];
  medications: string[];
  measurements: string[];
  procedures: string[];
  negated_conditions?: string[];
  extraction_method?: string;
}

interface QAMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  confidence?: number;
  entities_used?: string[];
  guideline_citations?: GuidelineCitation[];
  policy_citations?: PolicyCitation[];
  reasoning_chain?: ReasoningStep[];
  query_id?: string;
  sources?: string[];
  degraded?: DegradedState;
  // P1-018: Transparency header fields
  model_provider?: string | null;
  risk_tier?: string | null;
  processing_route?: string | null;
}

// P1-017: Pilot mode — lock UI to sanctioned extraction mode
const IS_PILOT_MODE = process.env.NEXT_PUBLIC_PILOT_MODE !== "false"; // default true

export default function NLPWorkbenchPage() {
  const router = useRouter();
  const [inputText, setInputText] = useState("");
  const [isExtracting, setIsExtracting] = useState(false);
  const [result, setResult] = useState<NLPExtractionResult | null>(null);
  const [selectedEntityTypes, setSelectedEntityTypes] = useState<Set<NLPEntityType>>(
    new Set(Object.keys(ENTITY_TYPE_CONFIG) as NLPEntityType[])
  );
  const [selectedEntity, setSelectedEntity] = useState<NLPExtractedEntity | null>(null);
  const [activeTab, setActiveTab] = useState("all");

  // Hybrid analyzer state
  const [workbenchMode, setWorkbenchMode] = useState<WorkbenchMode>("extraction");
  const [hybridResult, setHybridResult] = useState<HybridAnalyzeResponse | null>(null);
  const [ontologyResult, setOntologyResult] = useState<OntologyMapResponse | null>(null);
  const [analysisType, setAnalysisType] = useState<AnalysisType>("clinical_summary");
  const [useLLM, setUseLLM] = useState(true);
  const [extractNarrative, setExtractNarrative] = useState(true);
  const [useMLModels, setUseMLModels] = useState(false); // Ensemble NLP (ClinicalBERT + ModernBERT)
  const [selectedModelId, setSelectedModelId] = useState<string>("rule_based");
  const [availableModels, setAvailableModels] = useState<Array<{model_id: string; name: string; description: string; is_available: boolean}>>([]);
  const [isPreloading, setIsPreloading] = useState(false);
  const [modelPreloaded, setModelPreloaded] = useState(false);
  const [question, setQuestion] = useState("");

  // Fetch available models on mount
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await fetch("/api/nlp/models");
        if (response.ok) {
          const data = await response.json();
          setAvailableModels(data.models || []);
        }
      } catch (err) {
        console.error("Failed to fetch models:", err);
      }
    };
    fetchModels();
  }, []);

  // Knowledge graph state
  const [isBuildingGraph, setIsBuildingGraph] = useState(false);
  const [kgNodes, setKgNodes] = useState<KGNode[]>([]);
  const [kgEdges, setKgEdges] = useState<KGEdge[]>([]);
  const [kgSummary, setKgSummary] = useState<KGSummary | null>(null);
  const [kgPatientId, setKgPatientId] = useState<string>("");

  // Q&A Agent state
  const [qaMessages, setQaMessages] = useState<QAMessage[]>([]);
  const [qaInput, setQaInput] = useState("");
  const [isQuerying, setIsQuerying] = useState(false);

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
        use_ml_models: useMLModels,
        model_id: selectedModelId !== "rule_based" ? selectedModelId : undefined,
      });
      setResult(extractionResult);
      const modelName = availableModels.find(m => m.model_id === selectedModelId)?.name || selectedModelId;
      toast.success(
        `Extracted ${extractionResult.entities.length} entities using ${modelName} in ${extractionResult.processing_time_ms.toFixed(0)}ms`
      );
    } catch (error) {
      console.error("Extraction failed:", error);
      toast.error("Failed to extract entities. Please try again.");
    } finally {
      setIsExtracting(false);
    }
  };

  const handleHybridAnalyze = async () => {
    if (!inputText.trim()) {
      toast.error("Please enter clinical text to analyze");
      return;
    }

    setIsExtracting(true);
    setHybridResult(null);
    setOntologyResult(null);

    try {
      // First, get ontology mapping for detailed view
      const ontologyRes = await nlpOntologyMap({ text: inputText });
      setOntologyResult(ontologyRes);

      // Then get hybrid analysis
      const hybridRes = await nlpHybridAnalyze({
        text: inputText,
        analysis_type: analysisType,
        use_llm: useLLM,
        extract_narrative: extractNarrative,
      });
      setHybridResult(hybridRes);

      const llmStatus = hybridRes.llm_available ? "with LLM" : "extraction only";
      toast.success(
        `Analysis complete (${llmStatus}) in ${hybridRes.total_time_ms.toFixed(1)}ms`
      );
    } catch (error) {
      console.error("Analysis failed:", error);
      toast.error("Failed to analyze text. Please try again.");
    } finally {
      setIsExtracting(false);
    }
  };

  const handleLoadSample = (sampleText: string) => {
    // Normalize line endings to prevent offset drift in highlighting
    const normalizedText = sampleText.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    setInputText(normalizedText);
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

  const handleBuildKnowledgeGraph = async () => {
    if (!inputText.trim() || !result || result.entities.length === 0) {
      toast.error("No entities to build knowledge graph from");
      return;
    }

    setIsBuildingGraph(true);

    // Clear old KG data and Q&A history before building new one
    setKgNodes([]);
    setKgEdges([]);
    setKgSummary(null);
    setKgPatientId("");
    setQaMessages([]); // Clear Q&A history for new patient

    try {
      // Generate a patient ID based on timestamp if not extractable from text
      const patientIdMatch = inputText.match(/\b(?:MRN|Patient\s+ID)[:\s]+([A-Z0-9_]+)/i);
      const patientId = patientIdMatch ? patientIdMatch[1] : `NLP_${Date.now()}`;

      console.log("Building KG for patient:", patientId);
      console.log("Sending", result.entities.length, "entities to backend");

      // Map frontend entities to backend format
      // Map entity types from frontend format to backend expected format
      const entityTypeMap: Record<string, string> = {
        diagnosis: "CONDITION",
        medication: "DRUG",
        procedure: "PROCEDURE",
        lab_result: "MEASUREMENT",
        vital_sign: "MEASUREMENT",
        symptom: "CONDITION",
        anatomical_location: "OBSERVATION",
        temporal: "OBSERVATION",
        allergy: "CONDITION",
      };

      const entities = result.entities.map((e) => ({
        text: e.text,
        entity_type: entityTypeMap[e.entity_type] || "OBSERVATION",
        confidence: e.confidence,
        assertion: e.assertion === "present" ? "PRESENT" : e.assertion === "absent" ? "ABSENT" : "POSSIBLE",
        omop_concept_id: e.normalized_codes?.[0]?.code ? parseInt(e.normalized_codes[0].code) : null,
        note_id: "frontend_extraction",
        // Add document_date for temporal tracking (use current date as default)
        document_date: new Date().toISOString().split('T')[0],
      }));

      // Use the new /build-graph endpoint that accepts pre-extracted entities
      const response = await fetch("/api/clinical-agent/build-graph", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_id: patientId,
          entities: entities,
        }),
      });

      if (response.ok) {
        const buildResult = await response.json();
        console.log("Build graph result:", buildResult);

        // Store the summary from the build response
        if (buildResult.knowledge_graph) {
          setKgSummary(buildResult.knowledge_graph);
        }

        // Fetch the full graph data with nodes and edges
        const graphResponse = await fetch(`/api/clinical-agent/graph/${patientId}`);
        console.log("Graph response status:", graphResponse.status);

        if (graphResponse.ok) {
          const graphData = await graphResponse.json();
          console.log("Graph data:", graphData);
          setKgNodes(graphData.nodes || []);
          setKgEdges(graphData.edges || []);
          setKgPatientId(patientId);

          toast.success(
            `Knowledge graph built: ${buildResult.entities_processed} entities processed, ${graphData.nodes?.length || 0} unique nodes`
          );

          // Only switch to Knowledge Graph tab if we have data
          setWorkbenchMode("knowledge_graph");
        } else {
          const graphError = await graphResponse.text();
          console.error("Graph fetch failed:", graphError);
          toast.error(`Failed to load knowledge graph: ${graphResponse.status}`);
        }
      } else {
        const error = await response.text();
        console.error("Build graph failed:", error);
        toast.error("Failed to build knowledge graph. Check console for details.");
      }
    } catch (error) {
      console.error("Knowledge graph build error:", error);
      toast.error("Failed to build knowledge graph. Please try again.");
    } finally {
      setIsBuildingGraph(false);
    }
  };

  // Build knowledge graph from hybrid analyzer results
  const handleBuildKnowledgeGraphFromHybrid = async () => {
    if (!inputText.trim() || !hybridResult) {
      toast.error("No hybrid analysis results to build knowledge graph from");
      return;
    }

    const ctx = hybridResult.structured_context;

    // Convert structured context to entity format
    // Use current date for temporal tracking
    const documentDate = new Date().toISOString().split('T')[0];
    const entities: Array<{
      text: string;
      entity_type: string;
      confidence: number;
      assertion: string;
      omop_concept_id: number | null;
      note_id: string;
      document_date: string;
    }> = [];

    // Add diagnoses as CONDITIONS
    ctx.diagnoses.forEach((d) => {
      entities.push({
        text: d.name,
        entity_type: "CONDITION",
        confidence: 0.9,
        assertion: d.negated ? "ABSENT" : "PRESENT",
        omop_concept_id: d.code ? parseInt(d.code) || null : null,
        note_id: "hybrid_extraction",
        document_date: documentDate,
      });
    });

    // Add medications as DRUGs
    ctx.medications.forEach((m) => {
      const text = m.dose ? `${m.name} ${m.dose}` : m.name;
      entities.push({
        text,
        entity_type: "DRUG",
        confidence: 0.9,
        assertion: "PRESENT",
        omop_concept_id: null,
        note_id: "hybrid_extraction",
        document_date: documentDate,
      });
    });

    // Add labs as MEASUREMENTs
    ctx.labs.forEach((l) => {
      const text = l.value ? `${l.name}: ${l.value}${l.unit || ""}` : l.name;
      entities.push({
        text,
        entity_type: "MEASUREMENT",
        confidence: 0.9,
        assertion: "PRESENT",
        omop_concept_id: null,
        note_id: "hybrid_extraction",
        document_date: documentDate,
      });
    });

    // Add vitals as MEASUREMENTs
    ctx.vitals.forEach((v) => {
      const text = v.value ? `${v.name}: ${v.value}` : v.name;
      entities.push({
        text,
        entity_type: "MEASUREMENT",
        confidence: 0.9,
        assertion: "PRESENT",
        omop_concept_id: null,
        note_id: "hybrid_extraction",
        document_date: documentDate,
      });
    });

    // Add symptoms as CONDITIONs
    ctx.symptoms.forEach((s) => {
      entities.push({
        text: s.name,
        entity_type: "CONDITION",
        confidence: 0.85,
        assertion: s.negated ? "ABSENT" : "PRESENT",
        omop_concept_id: null,
        note_id: "hybrid_extraction",
        document_date: documentDate,
      });
    });

    // Add procedures as PROCEDUREs
    ctx.procedures.forEach((p) => {
      entities.push({
        text: p.name,
        entity_type: "PROCEDURE",
        confidence: 0.9,
        assertion: "PRESENT",
        omop_concept_id: null,
        note_id: "hybrid_extraction",
        document_date: documentDate,
      });
    });

    // Add findings as OBSERVATIONs
    ctx.findings.forEach((f) => {
      entities.push({
        text: f.name,
        entity_type: "OBSERVATION",
        confidence: 0.85,
        assertion: f.negated ? "ABSENT" : "PRESENT",
        omop_concept_id: null,
        note_id: "hybrid_extraction",
        document_date: documentDate,
      });
    });

    if (entities.length === 0) {
      toast.error("No entities found in hybrid analysis to build graph from");
      return;
    }

    setIsBuildingGraph(true);

    // Clear old KG data and Q&A history before building new one
    setKgNodes([]);
    setKgEdges([]);
    setKgSummary(null);
    setKgPatientId("");
    setQaMessages([]);

    try {
      // Generate a patient ID based on timestamp if not extractable from text
      const patientIdMatch = inputText.match(/\b(?:MRN|Patient\s+ID)[:\s]+([A-Z0-9_]+)/i);
      const patientId = patientIdMatch ? patientIdMatch[1] : `HYBRID_${Date.now()}`;

      console.log("Building KG from hybrid for patient:", patientId);
      console.log("Sending", entities.length, "entities to backend");

      // Use the /build-graph endpoint with both entities and raw text
      // Sending clinical_text lets the backend do additional extraction
      const response = await fetch("/api/clinical-agent/build-graph", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_id: patientId,
          entities: entities,
          clinical_text: inputText,
        }),
      });

      if (response.ok) {
        const buildResult = await response.json();
        console.log("Build graph result:", buildResult);

        if (buildResult.knowledge_graph) {
          setKgSummary(buildResult.knowledge_graph);
        }

        // Fetch the full graph data with nodes and edges
        const graphResponse = await fetch(`/api/clinical-agent/graph/${patientId}`);
        console.log("Graph response status:", graphResponse.status);

        if (graphResponse.ok) {
          const graphData = await graphResponse.json();
          console.log("Graph data:", graphData);
          setKgNodes(graphData.nodes || []);
          setKgEdges(graphData.edges || []);
          setKgPatientId(patientId);

          toast.success(
            `Knowledge graph built: ${buildResult.entities_processed} entities processed, ${graphData.nodes?.length || 0} unique nodes`
          );

          // Switch to Knowledge Graph tab
          setWorkbenchMode("knowledge_graph");
        } else {
          const graphError = await graphResponse.text();
          console.error("Graph fetch failed:", graphError);
          toast.error(`Failed to load knowledge graph: ${graphResponse.status}`);
        }
      } else {
        const error = await response.text();
        console.error("Build graph failed:", error);
        toast.error("Failed to build knowledge graph. Check console for details.");
      }
    } catch (error) {
      console.error("Knowledge graph build error:", error);
      toast.error("Failed to build knowledge graph. Please try again.");
    } finally {
      setIsBuildingGraph(false);
    }
  };

  // Handle Q&A query
  const handleQAQuery = async () => {
    if (!qaInput.trim() || !kgPatientId) {
      toast.error("Please enter a question");
      return;
    }

    const userMessage: QAMessage = {
      id: `msg_${Date.now()}`,
      role: "user",
      content: qaInput,
      timestamp: new Date(),
    };
    setQaMessages((prev) => [...prev, userMessage]);
    setQaInput("");
    setIsQuerying(true);

    try {
      const response = await fetch(`/api/clinical-agent/query/${kgPatientId}?provenance_depth=full`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: qaInput }),
      });

      if (response.ok) {
        const result = await response.json();

        // Build degraded state from response fields
        const degradedState: DegradedState = {
          declined: result.declined,
          decline_reason: result.decline_reason,
          escalation_path: result.escalation_path,
          confidence: result.confidence,
          dependency_state: result.dependency_state,
          provenance_complete: result.provenance_complete,
          action_gate: result.action_gate,
        };

        // P1-018: Derive transparency metadata from the response
        const modelProvider: string | null =
          result.model_provider || result.llm_model || (result.fallback_used ? "Fallback / Rule-based" : null);
        const riskTier: string | null =
          result.action_gate?.risk_tier || null;
        const processingRoute: string | null =
          result.processing_route ||
          (result.sources && result.sources.length > 0
            ? `hybrid: ${result.sources.join(" + ")}`
            : result.fallback_used
            ? "fallback"
            : null);

        const assistantMessage: QAMessage = {
          id: `msg_${Date.now()}_response`,
          role: "assistant",
          content: result.declined ? (result.decline_reason || "Response declined due to insufficient evidence.") : result.answer,
          timestamp: new Date(),
          confidence: result.confidence,
          entities_used: result.entities_found?.map((e: { text: string }) => e.text) || [],
          guideline_citations: result.guideline_citations || [],
          policy_citations: result.policy_citations || [],
          reasoning_chain: result.reasoning_chain || [],
          query_id: result.query_id,
          sources: result.sources || [],
          degraded: isDegraded(degradedState) ? degradedState : undefined,
          model_provider: modelProvider,
          risk_tier: riskTier,
          processing_route: processingRoute,
        };
        setQaMessages((prev) => [...prev, assistantMessage]);
      } else {
        toast.error("Failed to get answer. Please try again.");
      }
    } catch (error) {
      console.error("Q&A error:", error);
      toast.error("Failed to query. Please try again.");
    } finally {
      setIsQuerying(false);
    }
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
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">
                NLP Clinical Analysis Workbench
              </h1>
              {/* P1-017: Pilot Mode badge */}
              {IS_PILOT_MODE && (
                <Badge className="bg-indigo-600 text-white text-xs">
                  <Lock className="mr-1 h-3 w-3" />
                  Pilot Mode
                </Badge>
              )}
            </div>
            <p className="text-muted-foreground">
              {IS_PILOT_MODE
                ? "Standard Clinical Extraction — pilot-sanctioned mode"
                : "Extract entities and analyze clinical notes with AI"}
            </p>
          </div>
        </div>

        {/* Mode Toggle */}
        <TooltipProvider>
          <Tabs value={workbenchMode} onValueChange={(v) => {
            if (IS_PILOT_MODE && v !== "extraction") return;
            setWorkbenchMode(v as WorkbenchMode);
          }}>
            <TabsList>
              <TabsTrigger value="extraction" className="gap-2">
                <Search className="h-4 w-4" />
                {IS_PILOT_MODE ? "Standard Clinical Extraction" : "Entity Extraction"}
              </TabsTrigger>
              {IS_PILOT_MODE ? (
                <>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span>
                        <TabsTrigger value="hybrid" className="gap-2" disabled>
                          <Lock className="h-4 w-4" />
                          Hybrid Analyzer
                        </TabsTrigger>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>Contact admin to enable</TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span>
                        <TabsTrigger value="knowledge_graph" className="gap-2" disabled>
                          <Lock className="h-4 w-4" />
                          Knowledge Graph
                        </TabsTrigger>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>Contact admin to enable</TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span>
                        <TabsTrigger value="qa_agent" className="gap-2" disabled>
                          <Lock className="h-4 w-4" />
                          Q&A Agent
                        </TabsTrigger>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>Contact admin to enable</TooltipContent>
                  </Tooltip>
                </>
              ) : (
                <>
                  <TabsTrigger value="hybrid" className="gap-2">
                    <Sparkles className="h-4 w-4" />
                    Hybrid Analyzer
                  </TabsTrigger>
                  <TabsTrigger
                    value="knowledge_graph"
                    className="gap-2"
                    disabled={kgNodes.length === 0}
                  >
                    <Network className="h-4 w-4" />
                    Knowledge Graph
                    {kgNodes.length > 0 && (
                      <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                        {kgNodes.length}
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger
                    value="qa_agent"
                    className="gap-2"
                    disabled={kgNodes.length === 0}
                  >
                    <MessageSquare className="h-4 w-4" />
                    Q&A Agent
                  </TabsTrigger>
                </>
              )}
            </TabsList>
          </Tabs>
        </TooltipProvider>
      </div>

      {/* P0-020: Hybrid reasoner routing */}
      <div className="rounded-lg border border-sky-200 bg-sky-50 p-4 space-y-3">
        <p className="font-medium text-sky-900">Hybrid reasoner routing (production + compatibility)</p>
        <p className="text-sm text-sky-800">
          Pilot production paths are now under <code className="rounded bg-sky-100 px-1 py-0.5 font-mono text-xs">/api/v1/clinical-agent</code>.
          This workbench keeps compatibility with legacy NLP endpoints for continuity.
        </p>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {HYBRID_REASONER_MATRIX.map((route) => (
            <article
              key={route.path}
              className="rounded border border-white/80 bg-white/50 p-2"
            >
              <div className="flex items-center justify-between gap-2">
                <code className="text-[11px] text-slate-700">{route.path}</code>
                <span
                  className={`inline-flex rounded-full px-2 py-0.5 text-[10px] ${
                    route.status === "canonical"
                      ? "border border-emerald-200 bg-emerald-50 text-emerald-700"
                      : "border border-amber-200 bg-amber-50 text-amber-700"
                  }`}
                >
                  {route.status}
                </span>
              </div>
              <p className="mt-1 text-[11px] text-slate-600">{route.note}</p>
            </article>
          ))}
        </div>
      </div>

      {/* P0-020: Deprecation banner — canonical route is /clinical-agent */}
      <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 flex items-start gap-3">
        <AlertCircle className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
        <div className="text-sm">
          <p className="font-medium text-amber-800">
            These NLP endpoints are deprecated for pilot use.
          </p>
          <p className="text-amber-700 mt-1">
            The canonical ingestion-to-QA route is{" "}
            <code className="rounded bg-amber-100 px-1 py-0.5 font-mono text-xs">
              /api/v1/clinical-agent
            </code>
            . It provides bulk import, hybrid query, and graph RAG capabilities.
            Existing NLP endpoints remain available but will be sunset on 2026-06-30.
          </p>
        </div>
      </div>

      {/* Knowledge Graph View - Full Width with Advanced Component */}
      {workbenchMode === "knowledge_graph" && (
        <Card className="overflow-hidden">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Network className="h-5 w-5" />
                  Patient Knowledge Graph
                  {kgSummary && (
                    <Badge variant="secondary">
                      {kgSummary.node_count} nodes, {kgSummary.edge_count} edges
                    </Badge>
                  )}
                </CardTitle>
                <CardDescription>
                  Interactive D3.js visualization with filtering, multiple layouts, and provenance
                </CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setWorkbenchMode("qa_agent")}
              >
                <MessageSquare className="h-4 w-4 mr-2" />
                Ask Questions
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {/* Advanced KnowledgeGraph Component - Full featured visualization */}
            <div className="h-[700px]">
              <KnowledgeGraph
                nodes={kgNodes.map(n => ({
                  id: n.id,
                  patient_id: kgPatientId,
                  node_type: n.node_type,
                  label: n.label,
                  omop_concept_id: n.omop_concept_id,
                  properties: n.properties || {},
                  created_at: new Date().toISOString(),
                }))}
                edges={kgEdges.map(e => ({
                  id: e.id,
                  patient_id: kgPatientId,
                  source_node_id: e.source_node_id,
                  target_node_id: e.target_node_id,
                  edge_type: e.edge_type,
                  fact_id: null,
                  properties: e.properties || {},
                  event_date: e.event_date || null,
                  valid_from: null,
                  valid_to: null,
                  recorded_at: null,
                  source_document_date: null,
                  temporality: e.temporality || null,
                  temporal_order: null,
                  temporal_confidence: e.temporal_confidence || null,
                  created_at: new Date().toISOString(),
                }))}
                patientId={kgPatientId}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Q&A Agent View - Full Width */}
      {workbenchMode === "qa_agent" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              Clinical Q&A Agent
            </CardTitle>
            <CardDescription>
              Ask questions about the patient&apos;s clinical data and knowledge graph
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 lg:grid-cols-3">
              {/* Chat Area */}
              <div className="lg:col-span-2 space-y-4">
                <ScrollArea className="h-[400px] rounded-lg border p-4">
                  {qaMessages.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
                      <MessageSquare className="h-12 w-12 mb-4 opacity-50" />
                      <p>Ask a question about the patient&apos;s records</p>
                      <p className="text-sm mt-2">Try asking:</p>
                      <ul className="text-sm mt-2 space-y-1">
                        <li>&quot;What medications is the patient taking?&quot;</li>
                        <li>&quot;What are the patient&apos;s conditions?&quot;</li>
                        <li>&quot;Are there any drug interactions?&quot;</li>
                      </ul>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {qaMessages.map((msg) => (
                        <div
                          key={msg.id}
                          className={cn(
                            "flex",
                            msg.role === "user" ? "justify-end" : "justify-start"
                          )}
                        >
                          {msg.role === "user" ? (
                            <div className="max-w-[80%] rounded-lg px-4 py-2 bg-primary text-primary-foreground">
                              <p className="whitespace-pre-wrap">{msg.content}</p>
                            </div>
                          ) : (
                            <div className="max-w-[90%] space-y-3">
                              {/* P1-018: Transparency header above every response */}
                              <TransparencyHeader
                                modelProvider={msg.model_provider}
                                riskTier={msg.risk_tier}
                                processingRoute={msg.processing_route}
                              />

                              {/* P1-004: Refusal card for declined responses */}
                              {msg.degraded?.declined ? (
                                <RefusalCard state={msg.degraded} />
                              ) : msg.degraded ? (
                                <DegradedBanner state={msg.degraded} />
                              ) : null}

                              {/* Answer with confidence badge */}
                              <div className={cn(
                                "rounded-lg px-4 py-3 bg-muted",
                                msg.degraded?.declined && "opacity-75 select-none"
                              )}>
                                <div className="flex items-center gap-2 mb-2">
                                  {msg.confidence != null && (
                                    <ConfidenceBadge confidence={msg.confidence} />
                                  )}
                                  {msg.sources && msg.sources.length > 0 && (
                                    <Badge variant="secondary" className="text-xs">
                                      {msg.sources.length} sources
                                    </Badge>
                                  )}
                                  {msg.degraded?.declined && (
                                    <Badge variant="destructive" className="text-xs">
                                      Declined
                                    </Badge>
                                  )}
                                </div>
                                <div className="prose prose-sm dark:prose-invert max-w-none
                                  prose-headings:text-foreground prose-headings:font-semibold
                                  prose-h2:text-base prose-h2:mt-4 prose-h2:mb-2 prose-h2:border-b prose-h2:pb-1
                                  prose-h3:text-sm prose-h3:mt-3 prose-h3:mb-1
                                  prose-strong:text-foreground prose-strong:font-semibold
                                  prose-li:my-0.5 prose-ul:my-1 prose-ol:my-1
                                  prose-p:my-1.5 prose-p:leading-relaxed">
                                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                                </div>
                              </div>

                              {/* Guideline Citations */}
                              {msg.guideline_citations && msg.guideline_citations.length > 0 && (
                                <div className="space-y-2">
                                  <p className="text-xs font-medium text-muted-foreground px-1">
                                    Clinical Guidelines ({msg.guideline_citations.length})
                                  </p>
                                  {msg.guideline_citations.map((gc, idx) => (
                                    <GuidelineCitationCard key={idx} citation={gc} />
                                  ))}
                                </div>
                              )}

                              {/* Policy Citations */}
                              {msg.policy_citations && msg.policy_citations.length > 0 && (
                                <div className="space-y-2">
                                  <p className="text-xs font-medium text-muted-foreground px-1">
                                    Institutional Policies ({msg.policy_citations.length})
                                  </p>
                                  {msg.policy_citations.map((pc, idx) => (
                                    <PolicyCitationCard key={idx} citation={pc} />
                                  ))}
                                </div>
                              )}

                              {/* Reasoning Chain */}
                              {msg.reasoning_chain && msg.reasoning_chain.length > 0 && (
                                <ReasoningChain
                                  steps={msg.reasoning_chain}
                                  totalConfidence={msg.confidence}
                                />
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                      {isQuerying && (
                        <div className="flex justify-start">
                          <div className="bg-muted rounded-lg px-4 py-2">
                            <Loader2 className="h-4 w-4 animate-spin" />
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </ScrollArea>

                <div className="flex gap-2">
                  <Textarea
                    placeholder="Ask about medications, conditions, labs..."
                    value={qaInput}
                    onChange={(e) => setQaInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleQAQuery();
                      }
                    }}
                    className="min-h-[60px]"
                  />
                  <Button
                    onClick={handleQAQuery}
                    disabled={isQuerying || !qaInput.trim()}
                    className="px-6"
                  >
                    {isQuerying ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>

              {/* Patient Context Panel */}
              <div className="space-y-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Patient Overview</CardTitle>
                  </CardHeader>
                  <CardContent className="text-sm space-y-4">
                    <div>
                      <span className="text-muted-foreground">Patient ID:</span>{" "}
                      <span className="font-mono">{kgPatientId}</span>
                    </div>
                    {kgSummary && (
                      <>
                        {/* Active Conditions — clean numbered list */}
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <div className="h-2 w-2 rounded-full bg-blue-500" />
                            <span className="font-medium text-sm">Active Conditions</span>
                            <span className="text-xs text-muted-foreground">({kgSummary.conditions.length})</span>
                          </div>
                          <ul className="space-y-1 pl-4">
                            {kgSummary.conditions.map((c, i) => (
                              <li key={i} className="text-sm text-foreground flex items-start gap-2">
                                <span className="text-muted-foreground text-xs mt-0.5">{i + 1}.</span>
                                <span className="capitalize">{c.toLowerCase()}</span>
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* Ruled Out — compact strikethrough list */}
                        {kgSummary.negated_conditions && kgSummary.negated_conditions.length > 0 && (
                          <div>
                            <div className="flex items-center gap-2 mb-2">
                              <div className="h-2 w-2 rounded-full bg-gray-400" />
                              <span className="font-medium text-sm text-muted-foreground">Ruled Out</span>
                              <span className="text-xs text-muted-foreground">({kgSummary.negated_conditions.length})</span>
                            </div>
                            <div className="pl-4 flex flex-wrap gap-x-3 gap-y-1">
                              {kgSummary.negated_conditions.map((c, i) => (
                                <span key={i} className="text-xs text-gray-400 line-through capitalize">
                                  {c.replace("[RULED OUT] ", "").toLowerCase()}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Medications — clean list with pill icon */}
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <div className="h-2 w-2 rounded-full bg-green-500" />
                            <span className="font-medium text-sm">Medications</span>
                            <span className="text-xs text-muted-foreground">({kgSummary.medications.length})</span>
                          </div>
                          <ul className="space-y-1 pl-4">
                            {kgSummary.medications.map((m, i) => (
                              <li key={i} className="text-sm text-foreground flex items-start gap-2">
                                <span className="text-green-500 text-xs mt-0.5">Rx</span>
                                <span>{m}</span>
                              </li>
                            ))}
                          </ul>
                        </div>

                        {kgSummary.extraction_method && (
                          <div className="text-xs text-muted-foreground pt-2 border-t">
                            Extraction method: {kgSummary.extraction_method}
                          </div>
                        )}
                      </>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Quick Questions</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {[
                      "What medications is the patient taking?",
                      "What are the patient's active conditions?",
                      "Are there any drug interactions?",
                      "What are the recent lab results?",
                    ].map((q, i) => (
                      <Button
                        key={i}
                        variant="ghost"
                        size="sm"
                        className="w-full justify-start text-left h-auto py-2 px-3"
                        onClick={() => {
                          setQaInput(q);
                        }}
                      >
                        <Search className="h-3 w-3 mr-2 shrink-0" />
                        <span className="text-xs">{q}</span>
                      </Button>
                    ))}
                  </CardContent>
                </Card>

                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => setWorkbenchMode("knowledge_graph")}
                >
                  <Network className="h-4 w-4 mr-2" />
                  View Knowledge Graph
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Two-column layout for extraction and hybrid modes */}
      {(workbenchMode === "extraction" || workbenchMode === "hybrid") && (
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
                {workbenchMode === "extraction"
                  ? "Paste clinical notes, discharge summaries, or other medical text"
                  : "Analyze clinical text with deterministic extraction + optional LLM reasoning"
                }
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Extract Button - Prominent at top */}
              {workbenchMode === "extraction" && (
                <div className="flex flex-wrap items-center gap-4 p-3 bg-muted rounded-lg">
                  <Button
                    onClick={handleExtract}
                    disabled={isExtracting || !inputText.trim()}
                    size="lg"
                    className="flex-shrink-0"
                  >
                    {isExtracting ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        Extracting...
                      </>
                    ) : (
                      <>
                        <Search className="h-4 w-4 mr-2" />
                        Extract Entities
                      </>
                    )}
                  </Button>

                  {/* Model Selector */}
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Model:</span>
                    <Select value={selectedModelId} onValueChange={setSelectedModelId}>
                      <SelectTrigger className="w-[200px]">
                        <SelectValue placeholder="Select model..." />
                      </SelectTrigger>
                      <SelectContent>
                        {availableModels.map((model) => (
                          <SelectItem
                            key={model.model_id}
                            value={model.model_id}
                            disabled={!model.is_available}
                          >
                            {model.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Preload button for LLM */}
                  {selectedModelId === "llm_api" && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={isPreloading || modelPreloaded}
                      onClick={async () => {
                        setIsPreloading(true);
                        try {
                          const response = await fetch("/api/nlp/preload", { method: "POST" });
                          const data = await response.json();
                          if (data.status === "success") {
                            setModelPreloaded(true);
                            toast.success("Model loaded and ready!");
                          } else {
                            toast.error(data.message || "Preload failed");
                          }
                        } catch (err) {
                          toast.error("Failed to preload model");
                        } finally {
                          setIsPreloading(false);
                        }
                      }}
                    >
                      {isPreloading ? (
                        <>
                          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                          Loading...
                        </>
                      ) : modelPreloaded ? (
                        <>
                          <Check className="h-3 w-3 mr-1" />
                          Ready
                        </>
                      ) : (
                        "Preload Model"
                      )}
                    </Button>
                  )}

                  {/* Model description */}
                  <span className="text-xs text-muted-foreground">
                    {availableModels.find(m => m.model_id === selectedModelId)?.description || ""}
                  </span>
                </div>
              )}

              {/* Analyze Button + Options - Prominent at top for hybrid mode */}
              {workbenchMode === "hybrid" && (
                <div className="flex flex-wrap items-center gap-4 p-3 bg-muted rounded-lg">
                  <Button
                    onClick={handleHybridAnalyze}
                    disabled={isExtracting || !inputText.trim()}
                    size="lg"
                    className="flex-shrink-0"
                  >
                    {isExtracting ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        Analyzing...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4 mr-2" />
                        Analyze
                      </>
                    )}
                  </Button>

                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Type:</span>
                    <Select value={analysisType} onValueChange={(v) => setAnalysisType(v as AnalysisType)}>
                      <SelectTrigger className="w-[180px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(Object.keys(ANALYSIS_TYPE_CONFIG) as AnalysisType[]).map((type) => (
                          <SelectItem key={type} value={type}>
                            <div className="flex flex-col">
                              <span>{ANALYSIS_TYPE_CONFIG[type].label}</span>
                              <span className="text-xs text-muted-foreground">
                                {ANALYSIS_TYPE_CONFIG[type].description}
                              </span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="flex items-center gap-4">
                    <label className="flex items-center gap-1.5 text-sm text-muted-foreground cursor-pointer">
                      <input
                        type="checkbox"
                        checked={useLLM}
                        onChange={(e) => setUseLLM(e.target.checked)}
                        className="rounded"
                      />
                      LLM
                    </label>
                    <label className="flex items-center gap-1.5 text-sm text-muted-foreground cursor-pointer">
                      <input
                        type="checkbox"
                        checked={extractNarrative}
                        onChange={(e) => setExtractNarrative(e.target.checked)}
                        className="rounded"
                      />
                      Narrative
                    </label>
                  </div>
                </div>
              )}

              <Textarea
                placeholder="Enter clinical text here..."
                value={inputText}
                onChange={(e) => {
                  // Normalize line endings to prevent offset drift in highlighting
                  const normalizedText = e.target.value.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
                  setInputText(normalizedText);
                }}
                className="min-h-[250px] font-mono text-sm"
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

                {workbenchMode === "extraction" ? (
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="useMLModels"
                        checked={useMLModels}
                        onChange={(e) => setUseMLModels(e.target.checked)}
                        className="rounded"
                      />
                      <label htmlFor="useMLModels" className="text-sm whitespace-nowrap">
                        Use ML Models (Ensemble)
                      </label>
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
                          <Search className="h-4 w-4 mr-2" />
                          Extract Entities
                        </>
                      )}
                    </Button>
                  </div>
                ) : (
                  <Button
                    onClick={handleHybridAnalyze}
                    disabled={isExtracting || !inputText.trim()}
                  >
                    {isExtracting ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        Analyzing...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4 mr-2" />
                        Analyze
                      </>
                    )}
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Mode-specific options */}
          {workbenchMode === "extraction" ? (
            <>
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
              {result && (
                <ExportPanel
                  result={result}
                  inputText={inputText}
                  onBuildKnowledgeGraph={handleBuildKnowledgeGraph}
                  isBuildingGraph={isBuildingGraph}
                />
              )}
            </>
          ) : (
            <>
              {/* Analysis Options */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Analysis Options</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Analysis Type</label>
                    <Select value={analysisType} onValueChange={(v) => setAnalysisType(v as AnalysisType)}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(Object.keys(ANALYSIS_TYPE_CONFIG) as AnalysisType[]).map((type) => (
                          <SelectItem key={type} value={type}>
                            <div className="flex flex-col">
                              <span>{ANALYSIS_TYPE_CONFIG[type].label}</span>
                              <span className="text-xs text-muted-foreground">
                                {ANALYSIS_TYPE_CONFIG[type].description}
                              </span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="useLLM"
                      checked={useLLM}
                      onChange={(e) => setUseLLM(e.target.checked)}
                      className="rounded"
                    />
                    <label htmlFor="useLLM" className="text-sm">
                      Use LLM for reasoning (if available)
                    </label>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="extractNarrative"
                      checked={extractNarrative}
                      onChange={(e) => setExtractNarrative(e.target.checked)}
                      className="rounded"
                    />
                    <label htmlFor="extractNarrative" className="text-sm">
                      Extract Clinical Narrative (admission, course, discharge)
                    </label>
                  </div>

                  <div className="text-xs text-muted-foreground bg-muted p-3 rounded-md">
                    <strong>How it works:</strong> The hybrid analyzer first performs fast deterministic
                    extraction (~1ms), then optionally uses LLM reasoning grounded in the extracted data.
                    The LLM can only cite entities from the extraction, reducing hallucination risk.
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </div>

        {/* Results Panel */}
        <div className="space-y-4">
          {workbenchMode === "extraction" ? (
            // Entity Extraction Results
            result ? (
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
            )
          ) : (
            // Hybrid Analyzer Results
            hybridResult ? (
              <>
                {/* Ontology Stats if available */}
                {ontologyResult && <OntologyStatsPanel result={ontologyResult} />}

                {/* Hybrid Result Panel */}
                <HybridResultPanel
                  result={hybridResult}
                  onBuildKnowledgeGraph={handleBuildKnowledgeGraphFromHybrid}
                  isBuildingGraph={isBuildingGraph}
                />
              </>
            ) : (
              <Card>
                <CardContent className="py-16">
                  <div className="text-center space-y-4">
                    <div className="flex justify-center">
                      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-muted">
                        <Sparkles className="h-10 w-10 text-muted-foreground" />
                      </div>
                    </div>
                    <div>
                      <h3 className="text-lg font-medium">Hybrid Clinical Analyzer</h3>
                      <p className="text-muted-foreground max-w-md mx-auto">
                        Combines fast deterministic extraction (~1ms) with optional LLM reasoning
                        for grounded clinical analysis. The LLM can only cite entities from the
                        extraction, reducing hallucination risk.
                      </p>
                    </div>
                    <div className="flex flex-col items-center gap-2">
                      <p className="text-sm text-muted-foreground">Features:</p>
                      <div className="grid grid-cols-2 gap-2 text-sm text-left max-w-sm">
                        <div className="flex items-center gap-2">
                          <CheckCircle className="h-4 w-4 text-green-500" />
                          <span>100% token coverage</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Clock className="h-4 w-4 text-amber-500" />
                          <span>~1ms extraction</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Brain className="h-4 w-4 text-blue-500" />
                          <span>Grounded LLM</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Activity className="h-4 w-4 text-purple-500" />
                          <span>Multiple analysis types</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-col items-center gap-2 pt-4">
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
            )
          )}
        </div>
      </div>
      )}
    </div>
  );
}
