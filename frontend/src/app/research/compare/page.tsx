"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { GitBranch, BarChart3, ArrowUpDown } from "lucide-react";
import { toast } from "sonner";
import {
  useExperiments,
  useRuns,
  useCompareRuns,
} from "@/hooks/api/useResearch";
import type { ResearchComparisonResponse } from "@/lib/api";

export default function ComparePage() {
  const [experimentId, setExperimentId] = useState("");
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [comparison, setComparison] = useState<ResearchComparisonResponse | null>(null);

  const { data: experiments } = useExperiments();
  const { data: runs } = useRuns(experimentId || null);
  const compareMutation = useCompareRuns({
    onSuccess: (data) => setComparison(data),
    onError: () => toast.error("Failed to compare runs"),
  });

  function toggleRunId(runId: string) {
    setSelectedRunIds((prev) =>
      prev.includes(runId) ? prev.filter((id) => id !== runId) : [...prev, runId]
    );
  }

  function handleCompare() {
    if (selectedRunIds.length < 2) {
      toast.error("Select at least 2 runs to compare");
      return;
    }
    compareMutation.mutate({ run_ids: selectedRunIds });
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <GitBranch className="h-6 w-6" />
            Compare Runs
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Side-by-side comparison of experiment runs with delta columns
          </p>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 space-y-6">
        {/* Experiment Selection */}
        <Card>
          <CardHeader>
            <CardTitle>Select Runs to Compare</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Experiment</Label>
              <Select value={experimentId} onValueChange={(v) => { setExperimentId(v); setSelectedRunIds([]); setComparison(null); }}>
                <SelectTrigger>
                  <SelectValue placeholder="Select experiment..." />
                </SelectTrigger>
                <SelectContent>
                  {experiments?.experiments.map((exp) => (
                    <SelectItem key={exp.id} value={exp.id}>{exp.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {runs?.runs && runs.runs.length > 0 && (
              <div className="space-y-2">
                <Label>Runs (select 2+)</Label>
                {runs.runs.map((run) => (
                  <div key={run.id} className="flex items-center gap-2">
                    <Checkbox
                      checked={selectedRunIds.includes(run.id)}
                      onCheckedChange={() => toggleRunId(run.id)}
                    />
                    <span className="text-sm">
                      <span className="font-mono">{run.id.slice(0, 8)}...</span>{" "}
                      <span className="text-muted-foreground">
                        ({run.status}) - {run.metric_count} metrics -{" "}
                        {new Date(run.created_at).toLocaleDateString()}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            )}

            <Button
              onClick={handleCompare}
              disabled={selectedRunIds.length < 2 || compareMutation.isPending}
            >
              {compareMutation.isPending ? "Comparing..." : (
                <>
                  <ArrowUpDown className="h-4 w-4 mr-1" />
                  Compare {selectedRunIds.length} Runs
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Comparison Table */}
        {comparison && comparison.runs.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                Comparison Results
              </CardTitle>
              <CardDescription>
                {comparison.metric_names.length} metrics across {comparison.runs.length} runs
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 pr-4 sticky left-0 bg-white dark:bg-zinc-950">
                        Metric
                      </th>
                      {comparison.runs.map((run) => (
                        <th key={run.run_id} className="text-right py-2 px-3">
                          <div className="font-medium">{run.experiment_name}</div>
                          <div className="font-mono text-xs text-muted-foreground">
                            {run.run_id.slice(0, 8)}
                          </div>
                        </th>
                      ))}
                      {comparison.runs.length === 2 && (
                        <th className="text-right py-2 px-3">Delta</th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.metric_names.map((metricName) => {
                      const values = comparison.runs.map(
                        (r) => r.metrics[metricName]
                      );
                      const delta =
                        comparison.runs.length === 2 && values[0] != null && values[1] != null
                          ? values[1] - values[0]
                          : null;

                      return (
                        <tr key={metricName} className="border-b last:border-0">
                          <td className="py-2 pr-4 font-mono text-xs sticky left-0 bg-white dark:bg-zinc-950">
                            {metricName}
                          </td>
                          {values.map((val, i) => (
                            <td key={i} className="text-right py-2 px-3 font-mono">
                              {val != null ? val.toFixed(2) : "--"}
                            </td>
                          ))}
                          {delta !== null && (
                            <td
                              className={`text-right py-2 px-3 font-mono font-medium ${
                                delta > 0
                                  ? "text-emerald-600"
                                  : delta < 0
                                    ? "text-red-600"
                                    : ""
                              }`}
                            >
                              {delta > 0 ? "+" : ""}
                              {delta.toFixed(2)}
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
