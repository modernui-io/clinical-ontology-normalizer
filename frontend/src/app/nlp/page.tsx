"use client";

import { useState, useMemo, useEffect } from "react";
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
} from "lucide-react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import KnowledgeGraph from "@/components/KnowledgeGraph";
import { ConfidenceBadge } from "@/components/provenance/ConfidenceBadge";
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
}

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
  const [useMLModels, setUseMLModels] = useState(false); // Ensemble NLP (ClinicalBERT + ModernBERT)
  const [question, setQuestion] = useState("");

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
    const entities: Array<{
      text: string;
      entity_type: string;
      confidence: number;
      assertion: string;
      omop_concept_id: number | null;
      note_id: string;
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

      // Use the /build-graph endpoint
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
        const assistantMessage: QAMessage = {
          id: `msg_${Date.now()}_response`,
          role: "assistant",
          content: result.answer,
          timestamp: new Date(),
          confidence: result.confidence,
          entities_used: result.entities_found?.map((e: { text: string }) => e.text) || [],
          guideline_citations: result.guideline_citations || [],
          policy_citations: result.policy_citations || [],
          reasoning_chain: result.reasoning_chain || [],
          query_id: result.query_id,
          sources: result.sources || [],
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
            <h1 className="text-2xl font-bold tracking-tight">
              NLP Clinical Analysis Workbench
            </h1>
            <p className="text-muted-foreground">
              Extract entities and analyze clinical notes with AI
            </p>
          </div>
        </div>

        {/* Mode Toggle */}
        <Tabs value={workbenchMode} onValueChange={(v) => setWorkbenchMode(v as WorkbenchMode)}>
          <TabsList>
            <TabsTrigger value="extraction" className="gap-2">
              <Search className="h-4 w-4" />
              Entity Extraction
            </TabsTrigger>
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
          </TabsList>
        </Tabs>
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
                              {/* Answer with confidence badge */}
                              <div className="rounded-lg px-4 py-3 bg-muted">
                                <div className="flex items-center gap-2 mb-2">
                                  {msg.confidence != null && (
                                    <ConfidenceBadge confidence={msg.confidence} />
                                  )}
                                  {msg.sources && msg.sources.length > 0 && (
                                    <Badge variant="secondary" className="text-xs">
                                      {msg.sources.length} sources
                                    </Badge>
                                  )}
                                </div>
                                <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
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
                  <CardContent className="text-sm space-y-3">
                    <div>
                      <span className="text-muted-foreground">Patient ID:</span>{" "}
                      <span className="font-mono">{kgPatientId}</span>
                    </div>
                    {kgSummary && (
                      <>
                        <div>
                          <span className="text-muted-foreground block mb-1">Conditions:</span>
                          <div className="flex flex-wrap gap-1">
                            {kgSummary.conditions.map((c, i) => (
                              <Badge key={i} variant="destructive" className="text-xs">
                                {c}
                              </Badge>
                            ))}
                          </div>
                        </div>
                        <div>
                          <span className="text-muted-foreground block mb-1">Medications:</span>
                          <div className="flex flex-wrap gap-1">
                            {kgSummary.medications.map((m, i) => (
                              <Badge key={i} className="bg-blue-500 text-xs">
                                {m}
                              </Badge>
                            ))}
                          </div>
                        </div>
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
                <div className="flex items-center gap-4 p-3 bg-muted rounded-lg">
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
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="useMLModelsTop"
                      checked={useMLModels}
                      onChange={(e) => setUseMLModels(e.target.checked)}
                      className="rounded"
                    />
                    <label htmlFor="useMLModelsTop" className="text-sm">
                      Use ML Models (Ensemble NLP)
                    </label>
                  </div>
                </div>
              )}

              <Textarea
                placeholder="Enter clinical text here..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
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

