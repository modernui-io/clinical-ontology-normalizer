"use client";

import { useState } from "react";
import { ArrowDown, Check, Copy, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { BacklogSummary } from "@/lib/readinessEvidence.server";

type BundleMode = "overview" | "scenario";

interface EvidenceBundleButtonProps {
  snapshot: BacklogSummary;
  label: string;
  evidenceAnchorHint: string;
  scenarioId: string;
  mode?: BundleMode;
}

function buildBundlePayload(snapshot: BacklogSummary, scenarioId: string, evidenceAnchorHint: string, mode: BundleMode): string {
  const openP0 = snapshot.openTopLevel.filter((task) => task.priority === "P0");
  const openP0Subtasks = snapshot.openSubtasks.filter((task) => task.id.startsWith("P0-"));

  const payload = {
    generated_at_utc: new Date().toISOString(),
    source: {
      file: snapshot.sourceFile,
      source_updated_at: snapshot.sourceUpdatedAt,
      parser_generated_at: snapshot.generatedAt,
    },
    evidence_package: {
      run_mode: mode,
      scenario_id: scenarioId,
      evidence_hint: evidenceAnchorHint,
      backlog_health: {
        open_top_level: snapshot.counts.openTopLevelByPriority,
        open_subtasks: snapshot.counts.openAll.P0 + snapshot.counts.openAll.P1 + snapshot.counts.openAll.P2 + snapshot.counts.openAll.P3 + snapshot.counts.openAll.P4,
        total_top_level: snapshot.counts.totalTopLevel,
        total_all: snapshot.counts.totalAll,
      },
      open_p0_top_level: openP0.map((task) => ({
        id: task.id,
        title: task.title,
        owner: task.owner,
      })),
      open_p0_subtasks: openP0Subtasks.map((task) => ({
        id: task.id,
        title: task.title,
        owner: task.owner,
      })),
      evidence_paths: snapshot.evidenceArtifacts.map((artifact) => ({
        path: artifact.path,
        status: artifact.status,
        last_updated: artifact.lastUpdatedAt,
        related_tasks: artifact.relatedTaskIds,
      })),
    },
  };

  return JSON.stringify(payload, null, 2);
}

function downloadTextFile(filename: string, content: string) {
  const blob = new Blob([content], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export default function EvidenceBundleButton({
  snapshot,
  label,
  evidenceAnchorHint,
  scenarioId,
  mode = "overview",
}: EvidenceBundleButtonProps) {
  const [copied, setCopied] = useState(false);

  const payload = buildBundlePayload(snapshot, scenarioId, evidenceAnchorHint, mode);
  const filename = `${scenarioId}-evidence-bundle-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;

  const copyBundle = async () => {
    try {
      await navigator.clipboard.writeText(payload);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="outline"
        onClick={() => {
          downloadTextFile(filename, payload);
        }}
        className="inline-flex items-center gap-1.5"
      >
        <ArrowDown className="h-3.5 w-3.5" />
        Download {label}
      </Button>

      <Button
        variant="outline"
        onClick={() => {
          void copyBundle();
        }}
        className="inline-flex items-center gap-1.5"
      >
        <Copy className="h-3.5 w-3.5" />
        {copied ? <span>Copied</span> : <span>Copy JSON</span>}
        {copied ? <Check className="h-3 w-3 text-emerald-500" /> : null}
      </Button>

      <Button
        variant="secondary"
        onClick={() => {
          window.location.reload();
        }}
        className="inline-flex items-center gap-1.5"
      >
        <RefreshCcw className="h-3.5 w-3.5" />
        Refresh snapshot
      </Button>
    </div>
  );
}
