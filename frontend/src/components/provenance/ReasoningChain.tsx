"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Search,
  BookOpen,
  Brain,
  ClipboardCheck,
  Shield,
  ChevronDown,
  ChevronRight,
  Clock,
  TrendingUp,
} from "lucide-react";
import type { ReasoningStep } from "@/types/provenance";

const STEP_CONFIG: Record<
  string,
  {
    icon: React.ComponentType<{ className?: string }>;
    color: string;
    bgColor: string;
    label: string;
  }
> = {
  kg_retrieval: {
    icon: Search,
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-100 dark:bg-blue-900/30",
    label: "Knowledge Graph",
  },
  rag_search: {
    icon: BookOpen,
    color: "text-green-600 dark:text-green-400",
    bgColor: "bg-green-100 dark:bg-green-900/30",
    label: "RAG Search",
  },
  llm_inference: {
    icon: Brain,
    color: "text-purple-600 dark:text-purple-400",
    bgColor: "bg-purple-100 dark:bg-purple-900/30",
    label: "LLM Reasoning",
  },
  guideline_match: {
    icon: ClipboardCheck,
    color: "text-amber-600 dark:text-amber-400",
    bgColor: "bg-amber-100 dark:bg-amber-900/30",
    label: "Guideline Match",
  },
  policy_check: {
    icon: Shield,
    color: "text-indigo-600 dark:text-indigo-400",
    bgColor: "bg-indigo-100 dark:bg-indigo-900/30",
    label: "Policy Check",
  },
};

interface ReasoningChainProps {
  steps: ReasoningStep[];
  totalDurationMs?: number;
  totalConfidence?: number;
}

function StepItem({ step, isLast }: { step: ReasoningStep; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const config = STEP_CONFIG[step.type] || STEP_CONFIG.llm_inference;
  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: step.step * 0.1, duration: 0.3 }}
      className="relative flex gap-3"
    >
      {/* Timeline connector */}
      <div className="flex flex-col items-center">
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${config.bgColor}`}
        >
          <Icon className={`h-4 w-4 ${config.color}`} />
        </div>
        {!isLast && (
          <div className="w-px flex-1 bg-border mt-1" />
        )}
      </div>

      {/* Step content */}
      <div className={`flex-1 ${isLast ? "" : "pb-4"}`}>
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 text-left w-full group"
        >
          <span className="text-sm font-medium">{config.label}</span>
          <Badge variant="outline" className="text-xs">
            Step {step.step}
          </Badge>
          <div className="flex items-center gap-1 ml-auto text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            {step.duration_ms.toFixed(0)}ms
          </div>
          {step.confidence_contribution != null && step.confidence_contribution > 0 && (
            <div className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
              <TrendingUp className="h-3 w-3" />
              +{Math.round(step.confidence_contribution * 100)}%
            </div>
          )}
          {expanded ? (
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3 w-3 text-muted-foreground" />
          )}
        </button>

        <p className="text-xs text-muted-foreground mt-0.5">{step.summary}</p>

        <AnimatePresence>
          {expanded && step.details && Object.keys(step.details).length > 0 && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="mt-2 rounded-md bg-muted/50 p-2 text-xs space-y-1">
                {Object.entries(step.details).map(([key, value]) => (
                  <div key={key} className="flex justify-between gap-2">
                    <span className="text-muted-foreground capitalize">
                      {key.replace(/_/g, " ")}
                    </span>
                    <span className="font-mono text-right truncate max-w-[200px]">
                      {typeof value === "object"
                        ? JSON.stringify(value)
                        : String(value)}
                    </span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

export function ReasoningChain({
  steps,
  totalDurationMs,
  totalConfidence,
}: ReasoningChainProps) {
  const [isCollapsed, setIsCollapsed] = useState(true);
  const sortedSteps = [...steps].sort((a, b) => a.step - b.step);

  return (
    <Card>
      <CardHeader className="py-3 px-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Brain className="h-4 w-4 text-purple-500" />
            Reasoning Chain
            <Badge variant="secondary" className="text-xs">
              {steps.length} steps
            </Badge>
          </CardTitle>
          <div className="flex items-center gap-2">
            {totalDurationMs != null && (
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {(totalDurationMs / 1000).toFixed(1)}s
              </span>
            )}
            {totalConfidence != null && (
              <Badge variant="outline" className="text-xs">
                {Math.round(totalConfidence * 100)}% confidence
              </Badge>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2"
              onClick={() => setIsCollapsed(!isCollapsed)}
            >
              {isCollapsed ? "Expand" : "Collapse"}
            </Button>
          </div>
        </div>
      </CardHeader>
      <AnimatePresence>
        {!isCollapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <CardContent className="pt-0 pb-3 px-4">
              <div className="space-y-0">
                {sortedSteps.map((step, idx) => (
                  <StepItem
                    key={step.step}
                    step={step}
                    isLast={idx === sortedSteps.length - 1}
                  />
                ))}
              </div>
            </CardContent>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}
