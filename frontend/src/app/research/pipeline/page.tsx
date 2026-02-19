"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Workflow, ArrowRight, CheckCircle, Clock, AlertTriangle } from "lucide-react";
import {
  useExperiments,
  useRuns,
  useRunProgress,
  usePipelineTiming,
} from "@/hooks/api/useResearch";

const PIPELINE_STAGES = [
  { key: "nlp", label: "NLP Extraction", color: "bg-blue-500" },
  { key: "mapping", label: "OMOP Mapping", color: "bg-purple-500" },
  { key: "facts", label: "Fact Building", color: "bg-amber-500" },
  { key: "kg", label: "KG Construction", color: "bg-emerald-500" },
];

export default function PipelineMonitorPage() {
  const [experimentId, setExperimentId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const { data: experiments } = useExperiments();
  const { data: runs } = useRuns(experimentId || null);
  const { data: progress } = useRunProgress(selectedRunId);
  const { data: timing } = usePipelineTiming(selectedRunId);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Workflow className="h-6 w-6" />
            Pipeline Monitor
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time pipeline processing: NLP → OMOP → Facts → KG
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
                  <SelectItem key={exp.id} value={exp.id}>
                    {exp.name}
                  </SelectItem>
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

        {/* Pipeline Stage Visualization */}
        {selectedRunId && (
          <Card>
            <CardHeader>
              <CardTitle>Pipeline Stages</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                {PIPELINE_STAGES.map((stage, i) => (
                  <div key={stage.key} className="flex items-center gap-2">
                    <div className="flex flex-col items-center">
                      <div
                        className={`w-16 h-16 rounded-lg ${stage.color} flex items-center justify-center text-white`}
                      >
                        {progress?.status === "completed" ? (
                          <CheckCircle className="h-6 w-6" />
                        ) : progress?.status === "failed" ? (
                          <AlertTriangle className="h-6 w-6" />
                        ) : (
                          <Clock className="h-6 w-6" />
                        )}
                      </div>
                      <p className="text-xs font-medium mt-1">{stage.label}</p>
                    </div>
                    {i < PIPELINE_STAGES.length - 1 && (
                      <ArrowRight className="h-5 w-5 text-muted-foreground" />
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Progress */}
        {progress && (
          <Card>
            <CardHeader>
              <CardTitle>Run Progress</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Progress value={progress.progress_percent} />
              <div className="grid grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Status</p>
                  <p className="font-medium capitalize">{progress.status}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Documents</p>
                  <p className="font-medium">{progress.documents_total}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Progress</p>
                  <p className="font-medium">{progress.progress_percent}%</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Batch</p>
                  <p className="font-medium font-mono text-xs">
                    {progress.mimic_batch_id?.slice(0, 8) ?? "N/A"}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Timing Metrics */}
        {timing && timing.documents_timed > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Pipeline Timing</CardTitle>
              <CardDescription>Average processing time per document</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {[
                  { label: "NLP Extraction", value: timing.avg_nlp_ms, color: "bg-blue-500" },
                  { label: "OMOP Mapping", value: timing.avg_mapping_ms, color: "bg-purple-500" },
                  { label: "Fact Building", value: timing.avg_fact_building_ms, color: "bg-amber-500" },
                  { label: "KG Construction", value: timing.avg_kg_construction_ms, color: "bg-emerald-500" },
                ].map((item) => (
                  <div key={item.label} className="flex items-center gap-3">
                    <div className="w-32 text-sm">{item.label}</div>
                    <div className="flex-1">
                      <div className="h-6 bg-muted rounded overflow-hidden">
                        <div
                          className={`h-full ${item.color} rounded`}
                          style={{
                            width: `${Math.min((item.value / (timing.avg_total_ms || 1)) * 100, 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                    <div className="w-20 text-right text-sm font-mono">
                      {item.value.toFixed(1)}ms
                    </div>
                  </div>
                ))}
                <div className="flex items-center gap-3 border-t pt-3">
                  <div className="w-32 text-sm font-medium">Total</div>
                  <div className="flex-1" />
                  <div className="w-20 text-right text-sm font-mono font-medium">
                    {timing.avg_total_ms.toFixed(1)}ms
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="w-32 text-sm text-muted-foreground">P95</div>
                  <div className="flex-1" />
                  <div className="w-20 text-right text-sm font-mono text-muted-foreground">
                    {timing.p95_total_ms.toFixed(1)}ms
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  Based on {timing.documents_timed} documents
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
