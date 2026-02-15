"use client";

import { Badge } from "@/components/ui/badge";
import {
  Info,
  ShieldCheck,
  Cpu,
  Route,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// TransparencyHeader - displays model provider, risk tier, and processing
// route above every clinical response
// ---------------------------------------------------------------------------

interface TransparencyHeaderProps {
  /** Model provider label, e.g. "OpenAI GPT-4" or "Local Model" */
  modelProvider?: string | null;
  /** Risk tier from action_gate, e.g. "recommendation", "observation" */
  riskTier?: string | null;
  /** Processing route, e.g. "hybrid: KG + RAG + LLM" */
  processingRoute?: string | null;
  className?: string;
}

const RISK_TIER_STYLES: Record<string, string> = {
  observation: "bg-green-100 text-green-800 border-green-300 dark:bg-green-900/30 dark:text-green-300 dark:border-green-700",
  informational: "bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700",
  recommendation: "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700",
  action: "bg-red-100 text-red-800 border-red-300 dark:bg-red-900/30 dark:text-red-300 dark:border-red-700",
};

export function TransparencyHeader({
  modelProvider,
  riskTier,
  processingRoute,
  className,
}: TransparencyHeaderProps) {
  // Only render if at least one field is present
  if (!modelProvider && !riskTier && !processingRoute) return null;

  const tierStyle = riskTier
    ? RISK_TIER_STYLES[riskTier.toLowerCase()] || RISK_TIER_STYLES.informational
    : null;

  return (
    <div
      className={cn(
        "flex items-center gap-3 flex-wrap rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400",
        className
      )}
    >
      <Info className="h-3.5 w-3.5 shrink-0 opacity-60" />

      {modelProvider && (
        <span className="inline-flex items-center gap-1">
          <Cpu className="h-3 w-3 opacity-60" />
          <span className="font-medium">{modelProvider}</span>
        </span>
      )}

      {riskTier && tierStyle && (
        <Badge variant="outline" className={cn("text-xs font-medium", tierStyle)}>
          <ShieldCheck className="mr-1 h-3 w-3" />
          {riskTier}
        </Badge>
      )}

      {processingRoute && (
        <span className="inline-flex items-center gap-1">
          <Route className="h-3 w-3 opacity-60" />
          <span>{processingRoute}</span>
        </span>
      )}
    </div>
  );
}
