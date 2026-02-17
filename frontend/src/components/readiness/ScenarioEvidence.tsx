"use client";

import { useState } from "react";
import { ArrowDown, CheckCircle2, XCircle, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function downloadJSON(filename: string, content: string) {
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

interface AcceptanceCriterion {
  label: string;
  met: boolean;
}

interface ScenarioEvidenceProps {
  scenarioId: string;
  scenarioTitle: string;
  claims: string[];
  href: string;
  readiness: "ready" | "simulation";
  evidenceHint: string;
}

export default function ScenarioEvidence({
  scenarioId,
  scenarioTitle,
  claims,
  href,
  readiness,
  evidenceHint,
}: ScenarioEvidenceProps) {
  const [lastExecuted, setLastExecuted] = useState("");

  const acceptanceCriteria: AcceptanceCriterion[] = [
    { label: "Deterministic output check", met: readiness === "ready" },
    { label: "No silent demo fallbacks", met: readiness === "ready" },
    { label: "Evidence bundle exportable", met: true },
    { label: "Provenance chain complete", met: readiness === "ready" },
    { label: "Reviewer signoff captured", met: false },
  ];

  const exportManifest = () => {
    const manifest = {
      id: scenarioId,
      title: scenarioTitle,
      inputs: { claims, evidence_hint: evidenceHint },
      api_endpoints: [href],
      outputs: {
        readiness_status: readiness,
        acceptance_criteria: acceptanceCriteria.map((c) => ({
          label: c.label,
          met: c.met,
        })),
      },
      evidence_pack_link: `/sales-demo#${scenarioId}`,
      executed_at: lastExecuted || null,
      exported_at_utc: new Date().toISOString(),
    };
    const filename = `${scenarioId}-manifest-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
    downloadJSON(filename, JSON.stringify(manifest, null, 2));
  };

  return (
    <div className="mt-3 space-y-3 border-t border-slate-100 pt-3">
      <div className="flex items-center gap-2">
        <Clock className="h-3 w-3 text-slate-400" />
        <label className="text-[11px] text-slate-500">Last executed:</label>
        <Input
          type="datetime-local"
          value={lastExecuted}
          onChange={(e) => setLastExecuted(e.target.value)}
          className="h-7 text-xs max-w-[200px]"
        />
      </div>

      <div className="space-y-1.5">
        <p className="text-[11px] font-medium text-slate-500 uppercase tracking-wide">
          Acceptance criteria
        </p>
        {acceptanceCriteria.map((criterion) => (
          <div key={criterion.label} className="flex items-center gap-1.5">
            {criterion.met ? (
              <CheckCircle2 className="h-3 w-3 text-emerald-500" />
            ) : (
              <XCircle className="h-3 w-3 text-slate-300" />
            )}
            <span
              className={`text-[11px] ${
                criterion.met ? "text-slate-700" : "text-slate-400"
              }`}
            >
              {criterion.label}
            </span>
          </div>
        ))}
      </div>

      <Button
        variant="outline"
        size="sm"
        onClick={exportManifest}
        className="inline-flex items-center gap-1.5 h-7 text-xs"
      >
        <ArrowDown className="h-3 w-3" />
        Evidence bundle
      </Button>
    </div>
  );
}
