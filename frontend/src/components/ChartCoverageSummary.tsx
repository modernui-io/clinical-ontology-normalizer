"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  AlertTriangle,
  BarChart3,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChartCoverageData {
  overall_score: number;
  dimensions: Record<string, number>;
  missing_categories: string[];
  category_counts: Record<string, number>;
}

interface ChartCoverageSummaryProps {
  data: ChartCoverageData | null;
  isLoading?: boolean;
  className?: string;
}

// ---------------------------------------------------------------------------
// Dimension labels for display
// ---------------------------------------------------------------------------

const DIMENSION_LABELS: Record<string, string> = {
  conditions: "Conditions",
  medications: "Medications",
  labs: "Lab Results",
  procedures: "Procedures",
  demographics: "Demographics",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ChartCoverageSummary({
  data,
  isLoading = false,
  className,
}: ChartCoverageSummaryProps) {
  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <BarChart3 className="h-5 w-5 text-muted-foreground" />
            Chart Coverage
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Loading coverage data...</p>
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <BarChart3 className="h-5 w-5 text-muted-foreground" />
            Chart Coverage
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No coverage data available. Submit patient data to see chart completeness.
          </p>
        </CardContent>
      </Card>
    );
  }

  const pct = Math.round(data.overall_score * 100);

  // Split dimensions into known (score > 0) and unknown (score === 0)
  const known: Array<{ key: string; label: string; score: number; count: number }> = [];
  const unknown: Array<{ key: string; label: string }> = [];

  for (const [dim, score] of Object.entries(data.dimensions)) {
    const label = DIMENSION_LABELS[dim] || dim;
    const count = data.category_counts[dim] || 0;
    if (score > 0) {
      known.push({ key: dim, label, score, count });
    } else {
      unknown.push({ key: dim, label });
    }
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <BarChart3 className="h-5 w-5 text-blue-500" />
            Chart Coverage
          </CardTitle>
          <Badge
            variant="outline"
            className={cn(
              "text-xs font-medium",
              pct >= 80
                ? "border-green-400 text-green-700 dark:border-green-600 dark:text-green-300"
                : pct >= 50
                  ? "border-amber-400 text-amber-700 dark:border-amber-600 dark:text-amber-300"
                  : "border-red-400 text-red-700 dark:border-red-600 dark:text-red-300"
            )}
          >
            {pct}% complete
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Completeness bar */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Overall Completeness</span>
            <span>{pct}%</span>
          </div>
          <div className="h-2 w-full rounded-full bg-muted">
            <div
              className={cn(
                "h-2 rounded-full transition-all",
                pct >= 80
                  ? "bg-green-500"
                  : pct >= 50
                    ? "bg-amber-500"
                    : "bg-red-500"
              )}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        {/* Two-column layout */}
        <div className="grid grid-cols-2 gap-4">
          {/* Known column */}
          <div className="space-y-2">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
              <span className="text-sm font-medium text-green-800 dark:text-green-200">
                Known
              </span>
            </div>
            {known.length === 0 ? (
              <p className="text-xs text-muted-foreground pl-5">No data available</p>
            ) : (
              <ul className="space-y-1 pl-5">
                {known.map((item) => (
                  <li key={item.key} className="text-sm text-green-700 dark:text-green-300">
                    {item.count} {item.label.toLowerCase()}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Unknown/Missing column */}
          <div className="space-y-2">
            <div className="flex items-center gap-1.5">
              <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
              <span className="text-sm font-medium text-amber-800 dark:text-amber-200">
                Unknown / Missing
              </span>
            </div>
            {unknown.length === 0 ? (
              <p className="text-xs text-muted-foreground pl-5">All categories present</p>
            ) : (
              <ul className="space-y-1 pl-5">
                {unknown.map((item) => (
                  <li key={item.key} className="text-sm text-amber-700 dark:text-amber-300">
                    No {item.label.toLowerCase()}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
