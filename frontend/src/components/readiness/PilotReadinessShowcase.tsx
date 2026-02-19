import Link from "next/link";
import {
  CheckCircle,
  Clock,
  Database,
  FileCheck,
  ArrowRight,
  PlayCircle,
  ShieldAlert,
  ShieldCheck,
  Timer,
  Workflow,
} from "lucide-react";

interface DrillResult {
  id: string;
  title: string;
  status: "PASS" | "DEFERRED" | "FAIL";
  metric: string;
  metricLabel: string;
  timestamp: string;
  evidencePath: string;
  notes?: string;
}

const DRILL_RESULTS: DrillResult[] = [
  {
    id: "P0-019",
    title: "OpenEHR Reconciliation & Rollback",
    status: "PASS",
    metric: "10/10",
    metricLabel: "scenarios (5 dry-run + 5 round-trip)",
    timestamp: "2026-02-16T16:27:23Z",
    evidencePath: "docs/evidence/p0-019/p0-019-evidence-20260216T162723Z.json",
  },
  {
    id: "P0-025",
    title: "Incident Escalation Drill",
    status: "PASS",
    metric: "4/4",
    metricLabel: "severity levels exercised (SEV-1 to SEV-4)",
    timestamp: "2026-02-16T16:34:00Z",
    evidencePath: "docs/evidence/p0-025/p0-025-escalation-drill-evidence.md",
    notes: "HIPAA breach clock documented for SEV-1",
  },
  {
    id: "P0-026",
    title: "Backup Restore Drill",
    status: "PASS",
    metric: "30.42s",
    metricLabel: "RTO (PostgreSQL)",
    timestamp: "2026-02-16T16:31:46Z",
    evidencePath: "docs/evidence/p0-026/p0-026-restore-drill-evidence.md",
    notes: "Neo4j deferred (mock_mode, non-critical)",
  },
  {
    id: "P0-027",
    title: "Failover Simulation",
    status: "PASS",
    metric: "15.2s",
    metricLabel: "MTTR (PostgreSQL)",
    timestamp: "2026-02-16T16:33:31Z",
    evidencePath: "docs/evidence/p0-027/p0-027-failover-evidence.md",
    notes: "Zero data loss confirmed",
  },
  {
    id: "P0-028",
    title: "Pre-Pilot Signoff",
    status: "PASS",
    metric: "CONDITIONAL GO",
    metricLabel: "6 role signoffs collected",
    timestamp: "2026-02-16T17:00:00Z",
    evidencePath: "docs/evidence/p0-028/p0-028-signoff-template.md",
    notes: "5 staging conditions, 30-day expiry",
  },
];

const STAGING_BLOCKERS = [
  "OpenEHR round-trip staging confirmation",
  "Redis containerized failover simulation",
  "Neo4j restore drill (staging-only)",
  "Cascade failover simulation (all dependencies)",
  "30-day post-pilot review date (scheduled)",
];

const SNAPSHOT_CONTROL_ARTIFACTS = [
  {
    label: "Run log",
    path: "/tasks/04_enterprise_readiness_multi_agent_playbook_run.md",
    github:
      "https://github.com/astinard/clinical-ontology-normalizer/blob/master/tasks/04_enterprise_readiness_multi_agent_playbook_run.md",
  },
  {
    label: "Execution board",
    path: "/tasks/08_autonomous_execution_board.md",
    github:
      "https://github.com/astinard/clinical-ontology-normalizer/blob/master/tasks/08_autonomous_execution_board.md",
  },
  {
    label: "Backlog",
    path: "/tasks/09_master_change_backlog_p0_p4.md",
    github:
      "https://github.com/astinard/clinical-ontology-normalizer/blob/master/tasks/09_master_change_backlog_p0_p4.md",
  },
  {
    label: "Snapshot packet",
    path: "/docs/readiness_snapshot_2026-02-17.md",
    github:
      "https://github.com/astinard/clinical-ontology-normalizer/blob/master/docs/readiness_snapshot_2026-02-17.md",
  },
];

const SALES_SCENES = [
  {
    title: "Clinical safety walkthrough",
    description:
      "Confidence scoring, provenance links, and safe decline path for unsafe assertions.",
    href: "/clinical/intelligence",
    evidence: "P0-019 + clinical safety controls",
    state: "ready",
    stateLabel: "Production-ready logic",
  },
  {
    title: "Interop + OpenEHR replay",
    description:
      "End-to-end import, reconcile, and rollback with audit evidence.",
    href: "/pipelines/openehr",
    evidence: "P0-019 evidence and operations runbook",
    state: "ready",
    stateLabel: "Demo-ready",
  },
  {
    title: "Ops + resiliency proof",
    description:
      "Escalation drills, restore/failover metrics, and conditional-go posture.",
    href: "/pipelines/openehr/operations",
    evidence: "P0-025 / P0-026 / P0-027 records",
    state: "conditional",
    stateLabel: "Conditional GO",
  },
];

const P0_COUNTS = {
  total: 28,
  closed: 28,
  closedDate: "2026-02-16",
};

function statusBadge(status: DrillResult["status"]) {
  if (status === "PASS")
    return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (status === "DEFERRED")
    return "bg-amber-50 text-amber-700 border-amber-200";
  return "bg-red-50 text-red-700 border-red-200";
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  });
}

export default function PilotReadinessShowcase() {
  return (
    <section className="rounded-xl border border-slate-200 p-5 mt-4">
      <div className="mb-3 flex items-center gap-2">
        <ShieldAlert className="h-4.5 w-4.5 text-slate-600" />
        <h2 className="text-lg font-semibold text-slate-900">
          Sprint-1 Operational Drill Results
        </h2>
      </div>
      <p className="mb-5 inline-flex items-center gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700">
        <Clock className="h-3 w-3" />
        Simulation fallback — data captured 2026-02-16T17:00:00Z
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <div className="rounded-lg border border-emerald-200 bg-emerald-50/70 p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <CheckCircle className="h-3.5 w-3.5 text-emerald-600" />
            <span className="text-[11px] font-medium text-emerald-700 uppercase tracking-wide">
              P0 Closed
            </span>
          </div>
          <p className="text-xl font-semibold text-emerald-800">
            {P0_COUNTS.closed}/{P0_COUNTS.total}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <Workflow className="h-3.5 w-3.5 text-slate-500" />
            <span className="text-[11px] font-medium text-slate-600 uppercase tracking-wide">
              Drills Run
            </span>
          </div>
          <p className="text-xl font-semibold text-slate-800">
            {DRILL_RESULTS.length}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <Timer className="h-3.5 w-3.5 text-slate-500" />
            <span className="text-[11px] font-medium text-slate-600 uppercase tracking-wide">
              Best MTTR
            </span>
          </div>
          <p className="text-xl font-semibold text-slate-800">15.2s</p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <Database className="h-3.5 w-3.5 text-slate-500" />
            <span className="text-[11px] font-medium text-slate-600 uppercase tracking-wide">
              Data Loss
            </span>
          </div>
          <p className="text-xl font-semibold text-slate-800">Zero</p>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4 mb-5">
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4.5 w-4.5 text-slate-600" />
            <h3 className="text-sm font-semibold text-slate-900">
              Team handoff snapshot (single source of truth)
            </h3>
          </div>
          <span className="text-[10px] text-slate-500">As of 2026-02-17</span>
        </div>
        <p className="text-xs text-slate-600">
          P0/P1/P2/P3 are fully closed. P4 decision is 20/20 complete. P4 I/V are
          15/20 with 5 ADR deferred. ROL-08/ROL-09 are PASS; posture remains
          CONDITIONAL GO until 5 staging conditions are cleared.
        </p>
        <ul className="mt-3 text-xs text-slate-700 space-y-1 list-disc pl-5">
          {SNAPSHOT_CONTROL_ARTIFACTS.map((artifact) => (
            <li key={artifact.label}>
              <a
                href={artifact.github}
                target="_blank"
                rel="noreferrer"
                className="hover:text-slate-900 underline"
              >
                {artifact.label}
              </a>{" "}
              <span className="text-slate-500">({artifact.path})</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4 mb-5">
        <div className="flex items-center gap-2 mb-3">
          <PlayCircle className="h-4 w-4 text-slate-700" />
          <h3 className="text-sm font-semibold text-slate-900">
            External demo lanes (for sales)
          </h3>
        </div>
        <p className="text-xs text-slate-600 mb-3">
          Concrete product paths to show during meetings. Each card maps to an evidence
          anchor and an operational gate.
        </p>
        <div className="grid sm:grid-cols-3 gap-2">
          {SALES_SCENES.map((scenario) => (
            <article
              key={scenario.title}
              className="rounded-lg border border-slate-200 bg-slate-50 p-3"
            >
              <div className="flex items-start justify-between gap-2">
                <h4 className="text-xs font-medium text-slate-900">
                  {scenario.title}
                </h4>
                <span
                  className={`inline-flex rounded-full px-2 py-0.5 text-[10px] border ${
                    scenario.state === "ready"
                      ? "border-emerald-200 text-emerald-700 bg-emerald-50"
                      : "border-amber-200 text-amber-700 bg-amber-50"
                  }`}
                >
                  {scenario.stateLabel}
                </span>
              </div>
              <p className="mt-2 text-xs text-slate-600">{scenario.description}</p>
              <p className="mt-2 text-[11px] text-slate-500">Evidence: {scenario.evidence}</p>
              <Link
                href={scenario.href}
                className="mt-3 inline-flex items-center gap-1.5 text-[11px] font-medium text-slate-900"
              >
                Open scenario
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </article>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-4 mb-5">
        <div className="flex items-center gap-2 mb-2">
          <ShieldAlert className="h-4 w-4 text-amber-700" />
          <h3 className="text-sm font-semibold text-amber-900">
            Staging Blockers — Full GO holdouts (staging dependency required)
          </h3>
        </div>
        <ul className="list-disc pl-5 text-sm text-amber-800 space-y-1">
          {STAGING_BLOCKERS.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>

      <div className="space-y-2">
        {DRILL_RESULTS.map((drill) => (
          <div
            key={drill.id}
            className="rounded-lg border border-slate-200 p-3 hover:shadow-sm transition-shadow"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-slate-500">
                    {drill.id}
                  </span>
                  <h3 className="text-sm font-medium text-slate-900 truncate">
                    {drill.title}
                  </h3>
                </div>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-lg font-semibold text-slate-800">
                    {drill.metric}
                  </span>
                  <span className="text-xs text-slate-500">
                    {drill.metricLabel}
                  </span>
                </div>
                {drill.notes && (
                  <p className="mt-1 text-xs text-slate-500">{drill.notes}</p>
                )}
              </div>
              <div className="flex flex-col items-end gap-1.5 shrink-0">
                <span
                  className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${statusBadge(drill.status)}`}
                >
                  {drill.status}
                </span>
                <span className="flex items-center gap-1 text-[10px] text-slate-400">
                  <Clock className="h-3 w-3" />
                  {formatTimestamp(drill.timestamp)}
                </span>
              </div>
            </div>
            <p className="mt-1.5 text-[10px] text-slate-400 flex items-center gap-1">
              <FileCheck className="h-3 w-3" />
              {drill.evidencePath}
            </p>
          </div>
        ))}
      </div>

      <p className="mt-3 text-xs text-slate-500">
        All P0 items closed as of {P0_COUNTS.closedDate}. Signoff decision:
        CONDITIONAL GO with 5 staging conditions and 30-day expiry.
      </p>
    </section>
  );
}
