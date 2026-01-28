"use client";

import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { ConfidenceBreakdown } from "@/types/provenance";

interface ConfidenceBadgeProps {
  confidence: number;
  breakdown?: ConfidenceBreakdown;
  size?: "sm" | "md";
}

function getConfidenceConfig(confidence: number) {
  if (confidence >= 0.8) {
    return {
      color: "bg-green-100 text-green-800 border-green-300 dark:bg-green-900/30 dark:text-green-300 dark:border-green-700",
      label: "High",
    };
  }
  if (confidence >= 0.6) {
    return {
      color: "bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-900/30 dark:text-yellow-300 dark:border-yellow-700",
      label: "Medium",
    };
  }
  return {
    color: "bg-red-100 text-red-800 border-red-300 dark:bg-red-900/30 dark:text-red-300 dark:border-red-700",
    label: "Low",
  };
}

export function ConfidenceBadge({ confidence, breakdown, size = "sm" }: ConfidenceBadgeProps) {
  const config = getConfidenceConfig(confidence);
  const pct = Math.round(confidence * 100);
  const textSize = size === "sm" ? "text-xs" : "text-sm";

  const badge = (
    <Badge variant="outline" className={`${config.color} ${textSize} font-medium cursor-default`}>
      {pct}% {config.label}
    </Badge>
  );

  if (!breakdown) return badge;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>{badge}</TooltipTrigger>
        <TooltipContent className="w-64 p-3">
          <div className="space-y-1.5 text-xs">
            <p className="font-semibold text-sm">Confidence Breakdown</p>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Overall</span>
              <span className="font-mono">{Math.round(breakdown.overall * 100)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Knowledge Graph</span>
              <span className="font-mono">+{Math.round(breakdown.kg_contribution * 100)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">RAG Search</span>
              <span className="font-mono">+{Math.round(breakdown.rag_contribution * 100)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">LLM Reasoning</span>
              <span className="font-mono">+{Math.round(breakdown.llm_contribution * 100)}%</span>
            </div>
            {breakdown.guideline_boost > 0 && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Guideline Match</span>
                <span className="font-mono">+{Math.round(breakdown.guideline_boost * 100)}%</span>
              </div>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
