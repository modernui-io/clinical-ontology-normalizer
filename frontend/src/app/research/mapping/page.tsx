"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Shuffle, CheckCircle, XCircle, BarChart3 } from "lucide-react";
import { useExperiments, useRuns, useMappingQuality } from "@/hooks/api/useResearch";

export default function MappingQualityPage() {
  const [experimentId, setExperimentId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const { data: experiments } = useExperiments();
  const { data: runs } = useRuns(experimentId || null);
  const { data: mapping } = useMappingQuality(selectedRunId);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Shuffle className="h-6 w-6" />
            OMOP Mapping Quality
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Coverage, confidence, unmapped terms, and domain breakdown
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

        {mapping && (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-6">
                  <p className="text-2xl font-bold">{mapping.total_mentions.toLocaleString()}</p>
                  <p className="text-sm text-muted-foreground">Total Mentions</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-5 w-5 text-emerald-500" />
                    <div>
                      <p className="text-2xl font-bold">{mapping.mapped_count.toLocaleString()}</p>
                      <p className="text-sm text-muted-foreground">Mapped</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2">
                    <XCircle className="h-5 w-5 text-red-500" />
                    <div>
                      <p className="text-2xl font-bold">{mapping.unmapped_count.toLocaleString()}</p>
                      <p className="text-sm text-muted-foreground">Unmapped</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <p className="text-2xl font-bold">{mapping.avg_confidence.toFixed(3)}</p>
                  <p className="text-sm text-muted-foreground">Avg Confidence</p>
                </CardContent>
              </Card>
            </div>

            {/* Overall Coverage */}
            <Card>
              <CardHeader>
                <CardTitle>Overall Mapping Coverage</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Coverage</span>
                    <span className="font-medium">{mapping.coverage_percent.toFixed(1)}%</span>
                  </div>
                  <Progress value={mapping.coverage_percent} />
                </div>
              </CardContent>
            </Card>

            {/* Domain Coverage */}
            {Object.keys(mapping.domain_coverage).length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5" />
                    Coverage by Domain
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {Object.entries(mapping.domain_coverage)
                      .sort(([, a], [, b]) => b - a)
                      .map(([domain, coverage]) => (
                        <div key={domain} className="space-y-1">
                          <div className="flex justify-between text-sm">
                            <span>{domain}</span>
                            <span className="font-mono">{coverage.toFixed(1)}%</span>
                          </div>
                          <Progress
                            value={coverage}
                            className="h-2"
                          />
                        </div>
                      ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Top Unmapped Terms */}
            {mapping.top_unmapped.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Top Unmapped Terms</CardTitle>
                  <CardDescription>Most frequent mentions without OMOP concept mappings</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2">#</th>
                          <th className="text-left py-2">Term</th>
                          <th className="text-right py-2">Count</th>
                        </tr>
                      </thead>
                      <tbody>
                        {mapping.top_unmapped.map((item, i) => (
                          <tr key={item.term} className="border-b last:border-0">
                            <td className="py-2 text-muted-foreground">{i + 1}</td>
                            <td className="py-2 font-mono">{item.term}</td>
                            <td className="py-2 text-right">{item.count.toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </main>
    </div>
  );
}
