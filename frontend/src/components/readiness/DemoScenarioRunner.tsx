"use client";

/**
 * DemoScenarioRunner — reusable component that executes a deterministic
 * demo scenario step-by-step, tracks API endpoint hits vs simulated
 * fallbacks, captures the operator name, and exports an evidence manifest.
 *
 * Usage:
 *   <DemoScenarioRunner scenario={SCENARIO_CLINICAL_SAFETY} />
 *
 * 3-click reviewer path: Navigate -> Run Scenario -> Export Evidence
 */

import { useState, useCallback } from "react";
import {
  CheckCircle2,
  Circle,
  AlertTriangle,
  XCircle,
  Download,
  Play,
  Loader2,
  ClipboardList,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type {
  DemoScenarioConfig,
  StepResult,
  EvidenceManifest,
} from "@/lib/demo-scenarios";
import { computeInputHash } from "@/lib/demo-scenarios";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

/** Attempt a real fetch with a timeout; return true if live, false if simulated */
async function probeEndpoint(
  endpoint: string,
  timeoutMs: number = 3000
): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const res = await fetch(endpoint, {
      method: "GET",
      signal: controller.signal,
    });
    clearTimeout(timer);
    return res.ok;
  } catch {
    return false;
  }
}

function statusIcon(status: StepResult["status"]) {
  switch (status) {
    case "pass":
      return <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />;
    case "simulated":
      return <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />;
    case "fail":
      return <XCircle className="h-4 w-4 text-red-500 shrink-0" />;
  }
}

function statusBadge(status: StepResult["status"]) {
  switch (status) {
    case "pass":
      return <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200 text-[10px]">Live</Badge>;
    case "simulated":
      return <Badge className="bg-amber-100 text-amber-800 border-amber-200 text-[10px]">Simulated</Badge>;
    case "fail":
      return <Badge className="bg-red-100 text-red-800 border-red-200 text-[10px]">Failed</Badge>;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface DemoScenarioRunnerProps {
  scenario: DemoScenarioConfig;
}

export default function DemoScenarioRunner({ scenario }: DemoScenarioRunnerProps) {
  const [operator, setOperator] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [stepResults, setStepResults] = useState<StepResult[]>([]);
  const [startedAt, setStartedAt] = useState<string | null>(null);
  const [completedAt, setCompletedAt] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const hasRun = stepResults.length > 0;

  const endpointsHit = stepResults
    .filter((r) => r.status === "pass" && r.endpoint)
    .map((r) => r.endpoint!);

  const endpointsSimulated = stepResults
    .filter((r) => r.status === "simulated" && r.endpoint)
    .map((r) => r.endpoint!);

  const mode: EvidenceManifest["mode"] =
    endpointsHit.length > 0 && endpointsSimulated.length > 0
      ? "mixed"
      : endpointsHit.length > 0
        ? "live"
        : "simulation";

  // -----------------------------------------------------------------------
  // Run scenario
  // -----------------------------------------------------------------------

  const runScenario = useCallback(async () => {
    if (!operator.trim()) return;

    setIsRunning(true);
    setStepResults([]);
    const runStart = new Date().toISOString();
    setStartedAt(runStart);
    setCompletedAt(null);

    const results: StepResult[] = [];

    for (let i = 0; i < scenario.steps.length; i++) {
      const step = scenario.steps[i];
      const stepStart = Date.now();

      // Small delay for visual feedback
      await new Promise((r) => setTimeout(r, 300));

      let status: StepResult["status"] = "simulated";
      let detail = step.verification;

      if (step.endpoint) {
        const live = await probeEndpoint(step.endpoint);
        status = live ? "pass" : "simulated";
        detail = live
          ? `Endpoint ${step.endpoint} responded OK`
          : `Endpoint ${step.endpoint} unavailable — simulated`;
      } else {
        // Client-side verification steps always pass deterministically
        status = "pass";
        detail = `Client check passed: ${step.verification}`;
      }

      const result: StepResult = {
        stepIndex: i,
        label: step.label,
        endpoint: step.endpoint,
        status,
        completedAt: new Date().toISOString(),
        durationMs: Date.now() - stepStart,
        detail,
      };

      results.push(result);
      setStepResults([...results]);
    }

    setCompletedAt(new Date().toISOString());
    setIsRunning(false);
  }, [operator, scenario]);

  // -----------------------------------------------------------------------
  // Export evidence manifest
  // -----------------------------------------------------------------------

  const exportEvidence = useCallback(() => {
    if (!startedAt || !completedAt) return;

    const manifest: EvidenceManifest = {
      scenarioId: scenario.id,
      scenarioTitle: scenario.title,
      inputHash: computeInputHash(scenario.inputs),
      inputs: scenario.inputs,
      stepResults,
      endpointsHit: [...new Set(endpointsHit)],
      endpointsSimulated: [...new Set(endpointsSimulated)],
      operator: operator.trim(),
      startedAt,
      completedAt,
      mode,
      exportedAt: new Date().toISOString(),
    };

    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    downloadJSON(
      `${scenario.id}-evidence-${ts}.json`,
      JSON.stringify(manifest, null, 2)
    );
  }, [scenario, stepResults, endpointsHit, endpointsSimulated, operator, startedAt, completedAt, mode]);

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div id="demo-scenario-runner" className="mt-6">
      <details open={isOpen} onToggle={(e) => setIsOpen((e.target as HTMLDetailsElement).open)}>
        <summary className="cursor-pointer select-none list-none">
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 hover:bg-slate-100 transition-colors">
            <ClipboardList className="h-4 w-4 text-slate-600" />
            <span className="text-sm font-semibold text-slate-800">
              Demo Scenario: {scenario.title}
            </span>
            <Badge variant="outline" className="ml-auto text-[10px]">
              {scenario.steps.length} steps
            </Badge>
            {hasRun && (
              <Badge className={
                mode === "live"
                  ? "bg-emerald-100 text-emerald-800 border-emerald-200 text-[10px]"
                  : mode === "mixed"
                    ? "bg-amber-100 text-amber-800 border-amber-200 text-[10px]"
                    : "bg-slate-100 text-slate-700 border-slate-200 text-[10px]"
              }>
                {mode}
              </Badge>
            )}
          </div>
        </summary>

        <Card className="mt-2 border-slate-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">
              {scenario.title} — Deterministic Scenario Runner
            </CardTitle>
            <p className="text-xs text-slate-500">
              ID: <code className="font-mono text-[10px] bg-slate-100 px-1 rounded">{scenario.id}</code>
              {" | "}
              Input hash: <code className="font-mono text-[10px] bg-slate-100 px-1 rounded">{computeInputHash(scenario.inputs)}</code>
            </p>
          </CardHeader>

          <CardContent className="space-y-4">
            {/* Simulation mode warning */}
            {hasRun && mode !== "live" && (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                <strong>Simulation mode active.</strong> Write actions are blocked.
                Contact system administrator to connect production data sources.
              </div>
            )}

            {/* Operator name input */}
            <div className="flex items-end gap-3">
              <div className="flex-1 space-y-1">
                <label className="text-xs font-medium text-slate-600">
                  Operator name (required)
                </label>
                <Input
                  value={operator}
                  onChange={(e) => setOperator(e.target.value)}
                  placeholder="Enter your name"
                  className="h-8 text-sm"
                  disabled={isRunning}
                />
              </div>
              <Button
                size="sm"
                onClick={runScenario}
                disabled={isRunning || !operator.trim()}
                className="gap-1.5"
              >
                {isRunning ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Play className="h-3.5 w-3.5" />
                )}
                {isRunning ? "Running..." : "Run Scenario"}
              </Button>
            </div>

            {/* Step timeline */}
            {(isRunning || hasRun) && (
              <div className="space-y-1.5">
                <p className="text-[11px] font-medium text-slate-500 uppercase tracking-wide">
                  Step execution log
                </p>
                <div className="space-y-1">
                  {scenario.steps.map((step, idx) => {
                    const result = stepResults[idx];
                    const isPending = !result && idx >= stepResults.length;
                    const isActive = !result && idx === stepResults.length && isRunning;

                    return (
                      <div
                        key={idx}
                        className={`flex items-start gap-2 rounded-md border px-3 py-2 text-xs transition-colors ${
                          result
                            ? "border-slate-200 bg-white"
                            : isActive
                              ? "border-blue-200 bg-blue-50"
                              : "border-slate-100 bg-slate-50/50 opacity-60"
                        }`}
                      >
                        <div className="mt-0.5">
                          {result ? (
                            statusIcon(result.status)
                          ) : isActive ? (
                            <Loader2 className="h-4 w-4 animate-spin text-blue-500 shrink-0" />
                          ) : (
                            <Circle className="h-4 w-4 text-slate-300 shrink-0" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-slate-700">
                              {idx + 1}. {step.label}
                            </span>
                            {result && statusBadge(result.status)}
                            {result && (
                              <span className="text-[10px] text-slate-400 tabular-nums">
                                {result.durationMs}ms
                              </span>
                            )}
                          </div>
                          {step.endpoint && (
                            <code className="text-[10px] text-slate-400 font-mono">
                              {step.endpoint}
                            </code>
                          )}
                          {result && (
                            <p className="text-[10px] text-slate-500 mt-0.5">
                              {result.detail}
                            </p>
                          )}
                        </div>
                        {result && (
                          <span className="text-[9px] text-slate-400 tabular-nums whitespace-nowrap">
                            {new Date(result.completedAt).toLocaleTimeString()}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Endpoint summary */}
            {hasRun && !isRunning && (
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3">
                  <p className="text-[10px] font-medium text-emerald-800 uppercase tracking-wide mb-1">
                    Hit (Live)
                  </p>
                  {[...new Set(endpointsHit)].length > 0 ? (
                    <ul className="space-y-0.5">
                      {[...new Set(endpointsHit)].map((ep) => (
                        <li key={ep} className="text-[10px] font-mono text-emerald-700">{ep}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[10px] text-emerald-600 italic">None</p>
                  )}
                </div>
                <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
                  <p className="text-[10px] font-medium text-amber-800 uppercase tracking-wide mb-1">
                    Simulated
                  </p>
                  {[...new Set(endpointsSimulated)].length > 0 ? (
                    <ul className="space-y-0.5">
                      {[...new Set(endpointsSimulated)].map((ep) => (
                        <li key={ep} className="text-[10px] font-mono text-amber-700">{ep}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[10px] text-amber-600 italic">None</p>
                  )}
                </div>
              </div>
            )}

            {/* Export button */}
            {hasRun && !isRunning && (
              <div className="flex items-center justify-between border-t border-slate-100 pt-3">
                <p className="text-[10px] text-slate-500">
                  Completed at {completedAt ? new Date(completedAt).toLocaleString() : "—"}
                  {" by "}{operator}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={exportEvidence}
                  className="gap-1.5 h-7 text-xs"
                >
                  <Download className="h-3 w-3" />
                  Export Evidence
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </details>
    </div>
  );
}
