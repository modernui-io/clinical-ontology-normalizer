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
import { Network, Circle, ArrowLeftRight, Users, Brain } from "lucide-react";
import { useExperiments, useRuns, useKGMetrics } from "@/hooks/api/useResearch";

export default function KGExplorerPage() {
  const [experimentId, setExperimentId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const { data: experiments } = useExperiments();
  const { data: runs } = useRuns(experimentId || null);
  const { data: kgMetrics } = useKGMetrics(selectedRunId);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Network className="h-6 w-6" />
            Research KG Explorer
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Knowledge graph metrics and structure for experiment runs
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

        {kgMetrics && (
          <>
            {/* KG Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2">
                    <Circle className="h-5 w-5 text-blue-500" />
                    <div>
                      <p className="text-2xl font-bold">{kgMetrics.total_nodes.toLocaleString()}</p>
                      <p className="text-sm text-muted-foreground">Nodes</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2">
                    <ArrowLeftRight className="h-5 w-5 text-purple-500" />
                    <div>
                      <p className="text-2xl font-bold">{kgMetrics.total_edges.toLocaleString()}</p>
                      <p className="text-sm text-muted-foreground">Edges</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2">
                    <Brain className="h-5 w-5 text-emerald-500" />
                    <div>
                      <p className="text-2xl font-bold">{kgMetrics.unique_concepts.toLocaleString()}</p>
                      <p className="text-sm text-muted-foreground">Unique Concepts</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2">
                    <Users className="h-5 w-5 text-amber-500" />
                    <div>
                      <p className="text-2xl font-bold">{kgMetrics.patient_count.toLocaleString()}</p>
                      <p className="text-sm text-muted-foreground">Patients</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <p className="text-2xl font-bold">{kgMetrics.avg_nodes_per_patient.toFixed(1)}</p>
                  <p className="text-sm text-muted-foreground">Avg Nodes/Patient</p>
                </CardContent>
              </Card>
            </div>

            {/* Graph Density */}
            <Card>
              <CardHeader>
                <CardTitle>Graph Density</CardTitle>
                <CardDescription>Relationship between nodes and edges</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">Edge/Node Ratio</p>
                    <p className="text-lg font-medium">
                      {kgMetrics.total_nodes > 0
                        ? (kgMetrics.total_edges / kgMetrics.total_nodes).toFixed(2)
                        : "N/A"}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Concept Reuse Rate</p>
                    <p className="text-lg font-medium">
                      {kgMetrics.unique_concepts > 0
                        ? (kgMetrics.total_nodes / kgMetrics.unique_concepts).toFixed(2)
                        : "N/A"}
                      x
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Edges per Patient</p>
                    <p className="text-lg font-medium">
                      {kgMetrics.patient_count > 0
                        ? (kgMetrics.total_edges / kgMetrics.patient_count).toFixed(1)
                        : "N/A"}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Graph Connectivity</p>
                    <p className="text-lg font-medium">
                      {kgMetrics.total_edges > 0 && kgMetrics.total_nodes > 0
                        ? ((kgMetrics.total_edges / (kgMetrics.total_nodes * (kgMetrics.total_nodes - 1) / 2)) * 100).toFixed(4)
                        : "N/A"}
                      %
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Distribution Tables */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.keys(kgMetrics.node_type_distribution).length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Node Type Distribution</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {Object.entries(kgMetrics.node_type_distribution)
                        .sort(([, a], [, b]) => b - a)
                        .map(([type, count]) => (
                          <div key={type} className="flex justify-between text-sm">
                            <span>{type}</span>
                            <span className="font-mono">{count.toLocaleString()}</span>
                          </div>
                        ))}
                    </div>
                  </CardContent>
                </Card>
              )}
              {Object.keys(kgMetrics.edge_type_distribution).length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Edge Type Distribution</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {Object.entries(kgMetrics.edge_type_distribution)
                        .sort(([, a], [, b]) => b - a)
                        .map(([type, count]) => (
                          <div key={type} className="flex justify-between text-sm">
                            <span>{type}</span>
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
