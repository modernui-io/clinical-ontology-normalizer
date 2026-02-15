"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  ChevronDown,
  FileText,
  Network,
  ShieldCheck,
  ArrowRight,
  ExternalLink,
} from "lucide-react";

// ---------------------------------------------------------------------------
// P3-003: Provenance drilldown panel for fast clinician review
// ---------------------------------------------------------------------------

/** A single source document referenced in the provenance chain. */
export interface ProvenanceSource {
  documentId: string;
  noteType?: string;
  noteDate?: string;
  textLength?: number;
  /** URL or path to open the original note viewer */
  viewerHref?: string;
}

/** A single component of the confidence breakdown. */
export interface ConfidenceSegment {
  label: string;
  value: number;
  color: string;
}

/** A single node in the KG path. */
export interface KGPathNode {
  id: string;
  label: string;
  nodeType: string;
}

/** A single edge in the KG path. */
export interface KGPathEdge {
  edgeType: string;
}

/** A step in the KG path: node -> edge -> node -> ... */
export interface KGPathStep {
  source: KGPathNode;
  edge: KGPathEdge;
  target: KGPathNode;
}

export interface ProvenanceDrilldownProps {
  /** Unique query ID for this provenance chain */
  queryId: string;
  /** Human-readable answer text */
  answer?: string;
  /** Source documents in the evidence chain */
  sources: ProvenanceSource[];
  /** Confidence breakdown segments (should sum to ~1.0) */
  confidenceBreakdown: ConfidenceSegment[];
  /** Overall confidence (0-1) */
  overallConfidence: number;
  /** KG path steps (source -> edge -> target) */
  kgPath?: KGPathStep[];
  /** Whether to start expanded */
  defaultOpen?: boolean;
  className?: string;
}

function ConfidenceBar({ segments }: { segments: ConfidenceSegment[] }) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  if (total === 0) return null;

  return (
    <div className="space-y-1.5">
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted">
        {segments.map((segment, i) => {
          const widthPct = (segment.value / Math.max(total, 1)) * 100;
          return (
            <div
              key={i}
              className="h-full transition-all"
              style={{
                width: `${widthPct}%`,
                backgroundColor: segment.color,
              }}
              title={`${segment.label}: ${(segment.value * 100).toFixed(0)}%`}
            />
          );
        })}
      </div>
      <div className="flex flex-wrap gap-3">
        {segments.map((segment, i) => (
          <span key={i} className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: segment.color }}
            />
            {segment.label} ({(segment.value * 100).toFixed(0)}%)
          </span>
        ))}
      </div>
    </div>
  );
}

function KGPathDisplay({ steps }: { steps: KGPathStep[] }) {
  if (steps.length === 0) return null;

  return (
    <div className="space-y-2">
      <h4 className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        <Network className="h-3.5 w-3.5" />
        Knowledge Graph Path
      </h4>
      <div className="flex flex-wrap items-center gap-1">
        {steps.map((step, i) => (
          <div key={i} className="flex items-center gap-1">
            {i > 0 && <ArrowRight className="h-3 w-3 text-muted-foreground/50" />}
            <Badge variant="outline" className="text-xs font-normal">
              {step.source.label}
              <span className="ml-1 opacity-50">({step.source.nodeType})</span>
            </Badge>
            <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
              {step.edge.edgeType}
            </span>
            <ArrowRight className="h-3 w-3 text-muted-foreground/50" />
            <Badge variant="outline" className="text-xs font-normal">
              {step.target.label}
              <span className="ml-1 opacity-50">({step.target.nodeType})</span>
            </Badge>
          </div>
        ))}
      </div>
    </div>
  );
}

function confidenceLevel(value: number): { label: string; className: string } {
  if (value >= 0.8) return { label: "High", className: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" };
  if (value >= 0.5) return { label: "Medium", className: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" };
  return { label: "Low", className: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" };
}

export function ProvenanceDrilldown({
  queryId,
  answer,
  sources,
  confidenceBreakdown,
  overallConfidence,
  kgPath,
  defaultOpen = false,
  className,
}: ProvenanceDrilldownProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const level = confidenceLevel(overallConfidence);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div
        className={cn(
          "rounded-lg border border-slate-200 bg-slate-50/50 dark:border-slate-700 dark:bg-slate-900/50",
          className
        )}
      >
        <CollapsibleTrigger asChild>
          <button
            className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm transition-colors hover:bg-accent/50"
          >
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">Evidence &amp; Provenance</span>
              <Badge variant="outline" className={cn("text-xs", level.className)}>
                {level.label} ({(overallConfidence * 100).toFixed(0)}%)
              </Badge>
              <span className="text-xs text-muted-foreground">
                {sources.length} source{sources.length !== 1 ? "s" : ""}
              </span>
            </div>
            <ChevronDown
              className={cn(
                "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
                isOpen && "rotate-180"
              )}
            />
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="space-y-4 border-t px-4 py-4">
            {/* Confidence breakdown */}
            <div className="space-y-1.5">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Confidence Breakdown
              </h4>
              <ConfidenceBar segments={confidenceBreakdown} />
            </div>

            {/* Source documents */}
            <div className="space-y-2">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <FileText className="h-3.5 w-3.5" />
                Source Documents
              </h4>
              {sources.length === 0 ? (
                <p className="text-xs text-muted-foreground">No source documents recorded.</p>
              ) : (
                <div className="space-y-1.5">
                  {sources.map((source) => (
                    <div
                      key={source.documentId}
                      className="flex items-center justify-between rounded-md border bg-background px-3 py-2"
                    >
                      <div className="flex items-center gap-2 text-xs">
                        <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="font-mono">{source.documentId}</span>
                        {source.noteType && (
                          <Badge variant="secondary" className="text-[10px]">
                            {source.noteType}
                          </Badge>
                        )}
                        {source.noteDate && (
                          <span className="text-muted-foreground">{source.noteDate}</span>
                        )}
                      </div>
                      {source.viewerHref && (
                        <Button variant="ghost" size="sm" className="h-6 gap-1 px-2 text-xs" asChild>
                          <a href={source.viewerHref}>
                            View Original Note
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* KG path */}
            {kgPath && kgPath.length > 0 && <KGPathDisplay steps={kgPath} />}

            {/* Query ID footer */}
            <div className="pt-1 text-[10px] text-muted-foreground/60">
              Query ID: {queryId}
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
