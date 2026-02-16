"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, RefreshCw, ShieldAlert } from "lucide-react";

type HealthState = "not_configured" | "checking" | "online" | "offline" | "error";

function formatRelativeTime(date: Date | null): string {
  if (!date) return "never";
  const now = Date.now();
  const diff = Math.max(0, Math.floor((now - date.getTime()) / 1000));
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export default function BackendHealthProbe() {
  const [state, setState] = useState<HealthState>("not_configured");
  const [statusText, setStatusText] = useState<string>("");
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [lastPayload, setLastPayload] = useState<string>("");

  const runProbe = async () => {
    const base = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
    if (!base) {
      setState("not_configured");
      setStatusText("Set NEXT_PUBLIC_API_URL for live backend readiness probe.");
      return;
    }

    setState("checking");
    setStatusText("Checking /health...");
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 2500);
      const response = await fetch(`${base}/health`, {
        method: "GET",
        signal: controller.signal,
      });
      clearTimeout(timer);

      if (!response.ok) {
        setState("offline");
        setStatusText(`Health endpoint returned HTTP ${response.status}`);
        setLastChecked(new Date());
        setLastPayload("");
        return;
      }

      const body = await response.text();
      setState("online");
      setStatusText("Backend /health endpoint is reachable.");
      setLastPayload(body.slice(0, 140));
      setLastChecked(new Date());
    } catch (error: unknown) {
      setState("error");
      setStatusText(error instanceof Error ? error.message : "Health check failed");
      setLastChecked(new Date());
      setLastPayload("");
    }
  };

  useEffect(() => {
    runProbe();
  }, []);

  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">Live Backend Snapshot</p>
          <p className="text-sm text-slate-500">
            {statusText || "Backend readiness probe is not running."}
          </p>
        </div>
        <button
          onClick={() => {
            void runProbe();
          }}
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>
      <div className="mt-3 flex items-center gap-2 text-xs text-slate-600">
        {state === "online" && <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
        {state === "offline" && <ShieldAlert className="h-4 w-4 text-amber-500" />}
        {state === "error" && <ShieldAlert className="h-4 w-4 text-red-500" />}
        {state === "checking" && <Loader2 className="h-4 w-4 animate-spin text-blue-500" />}
        {state === "not_configured" && <ShieldAlert className="h-4 w-4 text-slate-400" />}
        <span>
          {state === "online" && "Online"}
          {state === "offline" && "Unreachable"}
          {state === "error" && "Error"}
          {state === "checking" && "Checking"}
          {state === "not_configured" && "Not configured"}
          {lastChecked ? ` · ${formatRelativeTime(lastChecked)}` : ""}
        </span>
      </div>
      {lastPayload && (
        <p className="mt-2 text-xs text-slate-500">
          Last payload: <span className="font-mono break-all">{lastPayload}</span>
        </p>
      )}
    </div>
  );
}
