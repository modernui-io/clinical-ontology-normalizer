"use client";

/**
 * MatchExplanation - Per-match explainability panel (VP-Product-2).
 *
 * Displays per-criterion evidence summaries for a patient-trial pair.
 * Each criterion shows pass/fail status with expandable evidence details,
 * source document links, and confidence explanations.
 *
 * Color coding:
 *   Green  - PASS (criterion satisfied)
 *   Red    - FAIL (exclusion triggered) / NOT_MET
 *   Yellow - UNKNOWN (insufficient data) / POSSIBLE_MATCH
 */

import { useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  HelpCircle,
  ChevronDown,
  ChevronRight,
  FileText,
  ShieldAlert,
  RefreshCw,
} from "lucide-react";
import { useMatchExplanation } from "@/hooks/api";
import { ConfidenceBadge } from "@/components/provenance/ConfidenceBadge";
import type { CriterionResultDetail } from "@/lib/api";

interface MatchExplanationProps {
  trialId: string;
  patientId: string;
  onClose?: () => void;
}

const statusConfig: Record<
  string,
  {
    icon: typeof CheckCircle2;
    color: string;
    bgColor: string;
    borderColor: string;
    label: string;
  }
> = {
  PASS: {
    icon: CheckCircle2,
    color: "text-green-600 dark:text-green-400",
    bgColor: "bg-green-50 dark:bg-green-950",
    borderColor: "border-green-200 dark:border-green-800",
    label: "Pass",
  },
  FAIL: {
    icon: XCircle,
    color: "text-red-600 dark:text-red-400",
    bgColor: "bg-red-50 dark:bg-red-950",
    borderColor: "border-red-200 dark:border-red-800",
    label: "Fail",
  },
  NOT_MET: {
    icon: XCircle,
    color: "text-red-600 dark:text-red-400",
    bgColor: "bg-red-50 dark:bg-red-950",
    borderColor: "border-red-200 dark:border-red-800",
    label: "Not Met",
  },
  UNKNOWN: {
    icon: HelpCircle,
    color: "text-yellow-600 dark:text-yellow-400",
    bgColor: "bg-yellow-50 dark:bg-yellow-950",
    borderColor: "border-yellow-200 dark:border-yellow-800",
    label: "Unknown",
  },
  POSSIBLE_MATCH: {
    icon: AlertCircle,
    color: "text-yellow-600 dark:text-yellow-400",
    bgColor: "bg-yellow-50 dark:bg-yellow-950",
    borderColor: "border-yellow-200 dark:border-yellow-800",
    label: "Possible",
  },
};

function getStatusConfig(status: string) {
  return (
    statusConfig[status] ?? {
      icon: HelpCircle,
      color: "text-gray-600",
      bgColor: "bg-gray-50",
      borderColor: "border-gray-200",
      label: status,
    }
  );
}

function CriterionRow({ criterion }: { criterion: CriterionResultDetail }) {
  const [expanded, setExpanded] = useState(false);
  const config = getStatusConfig(criterion.status);
  const StatusIcon = config.icon;

  return (
    <div
      className={`rounded-lg border ${config.borderColor} ${config.bgColor} transition-all`}
    >
      {/* Header row -- always visible */}
      <button
        type="button"
        className="flex w-full items-center gap-3 p-3 text-left hover:opacity-80"
        onClick={() => setExpanded(!expanded)}
      >
        <StatusIcon className={`h-5 w-5 flex-shrink-0 ${config.color}`} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm">{criterion.criterion_name}</span>
            <Badge variant="outline" className="text-xs capitalize">
              {criterion.criterion_type}
            </Badge>
            <Badge
              variant="outline"
              className={`text-xs ${config.color} border-current`}
            >
              {config.label}
            </Badge>
            {criterion.safety_block && (
              <Badge variant="destructive" className="text-xs">
                <ShieldAlert className="h-3 w-3 mr-1" />
                Safety Block
              </Badge>
            )}
          </div>
          {criterion.evidence_summary && (
            <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
              {criterion.evidence_summary}
            </p>
          )}
        </div>

        <ConfidenceBadge confidence={criterion.confidence} />

        {expanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        )}
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="border-t px-3 pb-3 pt-2 space-y-3">
          {/* Evidence Summary */}
          {criterion.evidence_summary && (
            <div>
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                Evidence Summary
              </h4>
              <p className="text-sm">{criterion.evidence_summary}</p>
            </div>
          )}

          {/* Confidence Explanation */}
          {criterion.confidence_explanation && (
            <div>
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                Confidence
              </h4>
              <p className="text-sm">{criterion.confidence_explanation}</p>
            </div>
          )}

          {/* Source Documents */}
          {criterion.source_documents.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                Source Documents
              </h4>
              <div className="flex flex-wrap gap-2">
                {criterion.source_documents.map((docId) => (
                  <Link
                    key={docId}
                    href={`/documents/${docId}`}
                    className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 underline"
                  >
                    <FileText className="h-3 w-3" />
                    {docId.substring(0, 8)}...
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Evidence Fact IDs */}
          {criterion.evidence_fact_ids.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                Clinical Facts ({criterion.evidence_fact_ids.length})
              </h4>
              <div className="flex flex-wrap gap-1">
                {criterion.evidence_fact_ids.slice(0, 5).map((factId) => (
                  <Badge key={factId} variant="outline" className="text-xs font-mono">
                    {factId.substring(0, 8)}...
                  </Badge>
                ))}
                {criterion.evidence_fact_ids.length > 5 && (
                  <Badge variant="outline" className="text-xs">
                    +{criterion.evidence_fact_ids.length - 5} more
                  </Badge>
                )}
              </div>
            </div>
          )}

          {/* Missing Domain info for UNKNOWN */}
          {criterion.missing_domain && (
            <div className="rounded border border-yellow-300 bg-yellow-50 p-2 dark:border-yellow-700 dark:bg-yellow-950">
              <p className="text-xs text-yellow-800 dark:text-yellow-200">
                Missing data domain: <strong>{criterion.missing_domain}</strong>
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function MatchExplanation({
  trialId,
  patientId,
  onClose,
}: MatchExplanationProps) {
  const { data: eligibility, isLoading, error } = useMatchExplanation(
    trialId,
    patientId
  );

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <RefreshCw className="h-5 w-5 animate-spin mx-auto text-muted-foreground" />
          <p className="text-sm text-muted-foreground mt-2">
            Loading match explanation...
          </p>
        </CardContent>
      </Card>
    );
  }

  if (error || !eligibility) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <AlertCircle className="h-5 w-5 mx-auto text-red-500" />
          <p className="text-sm text-muted-foreground mt-2">
            Failed to load match explanation
          </p>
        </CardContent>
      </Card>
    );
  }

  const inclusionCriteria = eligibility.criteria_details.filter(
    (c) => c.status !== "FAIL" || !c.safety_block
  );
  const exclusionCriteria = eligibility.criteria_details.filter(
    (c) => c.status === "FAIL" || c.safety_block
  );

  // Actually separate by whether criteria are exclusion (FAIL status) or inclusion
  const passedCriteria = eligibility.criteria_details.filter(
    (c) => c.status === "PASS"
  );
  const failedCriteria = eligibility.criteria_details.filter(
    (c) => c.status === "FAIL" || c.status === "NOT_MET"
  );
  const unknownCriteria = eligibility.criteria_details.filter(
    (c) => c.status === "UNKNOWN" || c.status === "POSSIBLE_MATCH"
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg">Match Explanation</CardTitle>
            <CardDescription>
              Patient <span className="font-mono">{patientId}</span>
              {" -- "}
              {eligibility.eligible ? (
                <span className="text-green-600 font-medium">Eligible</span>
              ) : (
                <span className="text-red-600 font-medium">Not Eligible</span>
              )}
              {" -- "}
              Match Score: {(eligibility.match_score * 100).toFixed(0)}%
            </CardDescription>
          </div>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="text-muted-foreground hover:text-foreground text-sm"
            >
              Close
            </button>
          )}
        </div>

        {/* Safety block warning */}
        {eligibility.safety_blocked && (
          <div className="flex items-start gap-2 mt-3 rounded-lg border border-red-300 bg-red-50 p-3 dark:border-red-700 dark:bg-red-950">
            <ShieldAlert className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-red-800 dark:text-red-200">
                Safety Block Active
              </p>
              <p className="text-xs text-red-700 dark:text-red-300 mt-0.5">
                {eligibility.safety_blocked_reasons.join("; ")}
              </p>
            </div>
          </div>
        )}

        {/* Data completeness indicator */}
        {eligibility.data_completeness && (
          <div className="mt-3 flex items-center gap-3">
            <span className="text-xs text-muted-foreground">Data Completeness:</span>
            <div className="flex items-center gap-2">
              <div className="h-2 w-24 rounded-full bg-gray-200 dark:bg-gray-700">
                <div
                  className={`h-full rounded-full transition-all ${
                    eligibility.data_completeness.overall_completeness >= 0.8
                      ? "bg-green-500"
                      : eligibility.data_completeness.overall_completeness >= 0.5
                      ? "bg-yellow-500"
                      : "bg-red-500"
                  }`}
                  style={{
                    width: `${(eligibility.data_completeness.overall_completeness * 100).toFixed(0)}%`,
                  }}
                />
              </div>
              <span className="text-xs font-medium">
                {(eligibility.data_completeness.overall_completeness * 100).toFixed(0)}%
              </span>
              <span className="text-xs text-muted-foreground">
                ({eligibility.data_completeness.evaluable_criteria}/{eligibility.data_completeness.total_criteria} criteria evaluable)
              </span>
            </div>
          </div>
        )}

        {/* Summary counts */}
        <div className="flex gap-4 mt-3">
          <div className="flex items-center gap-1.5">
            <CheckCircle2 className="h-4 w-4 text-green-500" />
            <span className="text-sm font-medium">{passedCriteria.length} passed</span>
          </div>
          <div className="flex items-center gap-1.5">
            <XCircle className="h-4 w-4 text-red-500" />
            <span className="text-sm font-medium">{failedCriteria.length} failed</span>
          </div>
          <div className="flex items-center gap-1.5">
            <HelpCircle className="h-4 w-4 text-yellow-500" />
            <span className="text-sm font-medium">{unknownCriteria.length} unknown</span>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-2">
        {eligibility.criteria_details.map((criterion, idx) => (
          <CriterionRow key={`${criterion.criterion_name}-${idx}`} criterion={criterion} />
        ))}

        {eligibility.criteria_details.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-4">
            No criteria details available
          </p>
        )}
      </CardContent>
    </Card>
  );
}
