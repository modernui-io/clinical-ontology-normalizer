"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
import { Database, Upload, Play, CheckCircle } from "lucide-react";
import { toast } from "sonner";
import { useExperiments, useCreateRun, useRunProgress } from "@/hooks/api/useResearch";

export default function ResearchIngestPage() {
  const [experimentId, setExperimentId] = useState("");
  const [csvPath, setCsvPath] = useState("/data/mimic-iv/discharge.csv");
  const [maxRows, setMaxRows] = useState<string>("500");
  const [chunkSize, setChunkSize] = useState<string>("100");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  const { data: experiments } = useExperiments();
  const { data: progress } = useRunProgress(activeRunId);

  const createRunMutation = useCreateRun({
    onSuccess: (run) => {
      setActiveRunId(run.id);
      toast.success(`Run started: ${run.id.slice(0, 8)}...`);
    },
    onError: () => toast.error("Failed to start run"),
  });

  function handleStartRun() {
    if (!experimentId) {
      toast.error("Select an experiment first");
      return;
    }
    createRunMutation.mutate({
      experiment_id: experimentId,
      mimic_csv_path: csvPath || undefined,
      max_rows: maxRows ? parseInt(maxRows) : undefined,
      chunk_size: chunkSize ? parseInt(chunkSize) : 100,
    });
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Database className="h-6 w-6" />
            Research Data Ingestion
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Import MIMIC-IV data with experiment tagging for reproducible runs
          </p>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="mx-auto max-w-3xl space-y-6">
          {/* Experiment Selection */}
          <Card>
            <CardHeader>
              <CardTitle>Select Experiment</CardTitle>
              <CardDescription>
                Choose the experiment this data import will be associated with
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Select value={experimentId} onValueChange={setExperimentId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose an experiment..." />
                </SelectTrigger>
                <SelectContent>
                  {experiments?.experiments.map((exp) => (
                    <SelectItem key={exp.id} value={exp.id}>
                      {exp.name} ({exp.status})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          {/* Import Configuration */}
          <Card>
            <CardHeader>
              <CardTitle>MIMIC-IV Import Configuration</CardTitle>
              <CardDescription>
                Configure the data source and processing parameters
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Server CSV Path</Label>
                <Input
                  value={csvPath}
                  onChange={(e) => setCsvPath(e.target.value)}
                  placeholder="/data/mimic-iv/discharge.csv"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Path on the server to the MIMIC-IV-Note CSV file
                </p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Max Rows</Label>
                  <Input
                    type="number"
                    value={maxRows}
                    onChange={(e) => setMaxRows(e.target.value)}
                    placeholder="No limit"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Leave empty for all rows
                  </p>
                </div>
                <div>
                  <Label>Chunk Size</Label>
                  <Input
                    type="number"
                    value={chunkSize}
                    onChange={(e) => setChunkSize(e.target.value)}
                    placeholder="100"
                  />
                </div>
              </div>
              <Button
                onClick={handleStartRun}
                disabled={!experimentId || createRunMutation.isPending}
                className="w-full"
              >
                {createRunMutation.isPending ? (
                  "Starting..."
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" /> Start Research Run
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Progress */}
          {activeRunId && progress && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {progress.status === "completed" ? (
                    <CheckCircle className="h-5 w-5 text-emerald-500" />
                  ) : (
                    <Upload className="h-5 w-5 text-blue-500 animate-pulse" />
                  )}
                  Run Progress
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Progress value={progress.progress_percent} />
                <div className="grid grid-cols-3 gap-4 text-sm">
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
                </div>
                {progress.mimic_progress && (
                  <div className="text-xs text-muted-foreground bg-muted/50 p-2 rounded">
                    <p>
                      Processed: {progress.mimic_progress.processed ?? "?"} |{" "}
                      Created: {progress.mimic_progress.created ?? "?"} |{" "}
                      Skipped: {progress.mimic_progress.skipped ?? "?"} |{" "}
                      Failed: {progress.mimic_progress.failed ?? "?"}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}
