"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FileCheck, Download, Copy, Table } from "lucide-react";
import { toast } from "sonner";
import {
  useExperiments,
  useRuns,
  useExportMetrics,
} from "@/hooks/api/useResearch";
import type { ResearchExportResponse } from "@/lib/api";

export default function PaperFiguresPage() {
  const [experimentId, setExperimentId] = useState("");
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [format, setFormat] = useState<"csv" | "json" | "latex">("latex");
  const [exportResult, setExportResult] = useState<ResearchExportResponse | null>(null);

  const { data: experiments } = useExperiments();
  const { data: runs } = useRuns(experimentId || null);
  const exportMutation = useExportMetrics({
    onSuccess: (data) => {
      setExportResult(data);
      toast.success(`Exported as ${data.format}`);
    },
    onError: () => toast.error("Failed to export"),
  });

  function toggleRunId(runId: string) {
    setSelectedRunIds((prev) =>
      prev.includes(runId) ? prev.filter((id) => id !== runId) : [...prev, runId]
    );
  }

  function handleExport() {
    if (selectedRunIds.length === 0) {
      toast.error("Select at least 1 run");
      return;
    }
    exportMutation.mutate({ run_ids: selectedRunIds, format });
  }

  function handleCopy() {
    if (exportResult?.content) {
      navigator.clipboard.writeText(exportResult.content);
      toast.success("Copied to clipboard");
    }
  }

  function handleDownload() {
    if (!exportResult) return;
    const blob = new Blob([exportResult.content], { type: exportResult.mime_type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = exportResult.filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FileCheck className="h-6 w-6" />
            Paper Figures & Tables
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Export metrics as LaTeX tables, CSV, or JSON for the NeurIPS paper
          </p>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 space-y-6">
        {/* Export Configuration */}
        <Card>
          <CardHeader>
            <CardTitle>Export Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Experiment</Label>
              <Select value={experimentId} onValueChange={(v) => { setExperimentId(v); setSelectedRunIds([]); setExportResult(null); }}>
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
                <Label>Runs</Label>
                {runs.runs
                  .filter((r) => r.status === "completed")
                  .map((run) => (
                    <div key={run.id} className="flex items-center gap-2">
                      <Checkbox
                        checked={selectedRunIds.includes(run.id)}
                        onCheckedChange={() => toggleRunId(run.id)}
                      />
                      <span className="text-sm">
                        <span className="font-mono">{run.id.slice(0, 8)}...</span>{" "}
                        ({run.metric_count} metrics)
                      </span>
                    </div>
                  ))}
              </div>
            )}

            <div>
              <Label>Export Format</Label>
              <Select value={format} onValueChange={(v) => setFormat(v as "csv" | "json" | "latex")}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="latex">LaTeX Table</SelectItem>
                  <SelectItem value="csv">CSV</SelectItem>
                  <SelectItem value="json">JSON</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Button
              onClick={handleExport}
              disabled={selectedRunIds.length === 0 || exportMutation.isPending}
            >
              {exportMutation.isPending ? "Exporting..." : (
                <>
                  <Table className="h-4 w-4 mr-1" /> Generate Export
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Export Result */}
        {exportResult && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>
                    {exportResult.filename}
                  </CardTitle>
                  <CardDescription>
                    Format: {exportResult.format} | Type: {exportResult.mime_type}
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleCopy}>
                    <Copy className="h-4 w-4 mr-1" /> Copy
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleDownload}>
                    <Download className="h-4 w-4 mr-1" /> Download
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Textarea
                readOnly
                value={exportResult.content}
                className="font-mono text-xs min-h-[300px]"
              />
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
