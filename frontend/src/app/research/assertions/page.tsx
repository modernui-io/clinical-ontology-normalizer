"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Shield, BarChart3 } from "lucide-react";
import { useExperiments, useRuns, useAssertionAnalytics } from "@/hooks/api/useResearch";

export default function AssertionsPage() {
  const [experimentId, setExperimentId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const { data: experiments } = useExperiments();
  const { data: runs } = useRuns(experimentId || null);
  const { data: analytics } = useAssertionAnalytics(selectedRunId);

  const maxCount = analytics
    ? Math.max(...Object.values(analytics.assertion_counts), 1)
    : 1;

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Shield className="h-6 w-6" />
            Assertion Analytics
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Assertion type distribution: present, negated, uncertain, hypothetical
          </p>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 space-y-6">
        {/* Selection */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label>Experiment</Label>
            <Select value={experimentId} onValueChange={(v) => { setExperimentId(v); setSelectedRunId(null); }}>
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
          <div>
            <Label>Run</Label>
            <Select value={selectedRunId ?? ""} onValueChange={setSelectedRunId}>
              <SelectTrigger>
                <SelectValue placeholder="Select run..." />
              </SelectTrigger>
              <SelectContent>
                {runs?.runs.map((run) => (
                  <SelectItem key={run.id} value={run.id}>
                    {run.id.slice(0, 8)}... ({run.status})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {analytics && (
          <>
            {/* Summary */}
            <Card>
              <CardHeader>
                <CardTitle>Total Mentions: {analytics.total_mentions.toLocaleString()}</CardTitle>
              </CardHeader>
            </Card>

            {/* Assertion Type Bar Chart */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5" />
                  Assertion Type Distribution
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(analytics.assertion_counts)
                    .sort(([, a], [, b]) => b - a)
                    .map(([type, count]) => {
                      const colors: Record<string, string> = {
                        present: "bg-emerald-500",
                        negated: "bg-red-500",
                        uncertain: "bg-amber-500",
                        hypothetical: "bg-blue-500",
                        conditional: "bg-purple-500",
                      };
                      return (
                        <div key={type} className="flex items-center gap-3">
                          <div className="w-28 text-sm capitalize">{type}</div>
                          <div className="flex-1">
                            <div className="h-8 bg-muted rounded overflow-hidden">
                              <div
                                className={`h-full ${colors[type] ?? "bg-zinc-500"} rounded flex items-center px-2`}
                                style={{ width: `${(count / maxCount) * 100}%` }}
                              >
                                <span className="text-xs text-white font-medium">
                                  {count.toLocaleString()}
                                </span>
                              </div>
                            </div>
                          </div>
                          <div className="w-16 text-right text-sm text-muted-foreground">
                            {((count / analytics.total_mentions) * 100).toFixed(1)}%
                          </div>
                        </div>
                      );
                    })}
                </div>
              </CardContent>
            </Card>

            {/* Cross-tabulation by Domain */}
            {Object.keys(analytics.assertion_by_domain).length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Assertions by Clinical Domain</CardTitle>
                  <CardDescription>Cross-tabulation of assertion types across OMOP domains</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2 pr-4">Domain</th>
                          {Object.keys(analytics.assertion_counts).map((type) => (
                            <th key={type} className="text-right py-2 px-2 capitalize">
                              {type}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(analytics.assertion_by_domain).map(
                          ([domain, counts]) => (
                            <tr key={domain} className="border-b last:border-0">
                              <td className="py-2 pr-4 font-medium">{domain}</td>
                              {Object.keys(analytics.assertion_counts).map((type) => (
                                <td key={type} className="text-right py-2 px-2">
                                  {counts[type]?.toLocaleString() ?? 0}
                                </td>
                              ))}
                            </tr>
                          )
                        )}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Temporality & Experiencer */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.keys(analytics.temporality_counts).length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Temporality Distribution</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {Object.entries(analytics.temporality_counts).map(([type, count]) => (
                        <div key={type} className="flex justify-between text-sm">
                          <span className="capitalize">{type}</span>
                          <span className="font-mono">{count.toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
              {Object.keys(analytics.experiencer_counts).length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Experiencer Distribution</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {Object.entries(analytics.experiencer_counts).map(([type, count]) => (
                        <div key={type} className="flex justify-between text-sm">
                          <span className="capitalize">{type}</span>
                          <span className="font-mono">{count.toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
