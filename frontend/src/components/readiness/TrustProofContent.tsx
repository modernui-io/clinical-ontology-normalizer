import Link from "next/link";
import type { ElementType } from "react";
import {
  Activity,
  AlertTriangle,
  BadgeCheck,
  ArrowRight,
  CalendarClock,
  DatabaseZap,
  FileCheck,
  LayoutDashboard,
  ShieldCheck,
  TimerReset,
} from "lucide-react";
import { getReadinessSnapshot, type BacklogTask, type EvidenceArtifact } from "@/lib/readinessEvidence.server";
import BackendHealthProbe from "@/components/readiness/BackendHealthProbe";
import EvidenceBundleButton from "@/components/readiness/EvidenceBundleButton";

type SectionId = "p0" | "p4" | "evidence" | "demo";

function formatTime(iso: string | null): string {
  if (!iso) return "No file timestamp";
  return new Date(iso).toLocaleString("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function taskById(taskId: string, tasks: BacklogTask[]): BacklogTask | undefined {
  return tasks.find((task) => task.id === taskId);
}

function subtaskRowsFor(taskId: string, subtasks: BacklogTask[]) {
  const basePrefix = `${taskId}-`;
  return subtasks.filter((task) => task.id.startsWith(basePrefix));
}

function renderStatusBadge(done: boolean, label: string) {
  return done
    ? {
        className:
          "inline-flex items-center gap-1 rounded-full border border-emerald-200/70 bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700",
        text: "done",
      }
    : {
        className:
          "inline-flex items-center gap-1 rounded-full border border-amber-200/70 bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700",
        text: label,
      };
}

function EvidenceStatus({
  artifact,
}: {
  artifact: EvidenceArtifact;
}) {
  const statusClass =
    artifact.status === "present"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : artifact.status === "missing"
      ? "bg-red-50 text-red-700 border-red-200"
      : "bg-slate-50 text-slate-700 border-slate-200";

  return (
    <li className="rounded-lg border border-slate-200 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-900">{artifact.path}</p>
          <p className="text-xs text-slate-500">
            Related work: {artifact.relatedTaskIds.join(", ")}
          </p>
        </div>
        <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] ${statusClass}`}>
          {artifact.status}
        </span>
      </div>
      <p className="mt-2 text-xs text-slate-500">Updated: {formatTime(artifact.lastUpdatedAt)}</p>
    </li>
  );
}

function SummaryCard({
  title,
  description,
  metric,
  icon: Icon,
  tone,
}: {
  title: string;
  description: string;
  metric: string | number;
  icon: ElementType;
  tone: "warning" | "success" | "neutral";
}) {
  const toneClass =
    tone === "warning"
      ? "border-amber-200 bg-amber-50/70 text-amber-700"
      : tone === "success"
      ? "border-emerald-200 bg-emerald-50/70 text-emerald-700"
      : "border-slate-200 bg-slate-50 text-slate-700";

  return (
    <div className={`rounded-xl border p-4 ${toneClass}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium">{title}</p>
          <p className="text-xs text-slate-600 mt-1">{description}</p>
        </div>
        <Icon className="h-4.5 w-4.5" />
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight">{metric}</p>
    </div>
  );
}

function ScenarioCard({
  title,
  description,
  href,
  evidence,
}: {
  title: string;
  description?: string;
  href: string;
  evidence: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 p-4 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        <ShieldCheck className="h-4.5 w-4.5 text-slate-500" />
      </div>
      <p className="mt-2 text-xs text-slate-600">{description}</p>
      <p className="mt-2 text-xs text-slate-500">Evidence anchor: {evidence}</p>
      <Link href={href} className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-slate-900">
        Open scenario
        <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}

export default async function TrustProofContent() {
  const snapshot = await getReadinessSnapshot();
  const openP0 = snapshot.openTopLevel.filter((task) => task.priority === "P0");
  const openP4 = snapshot.openTopLevel.filter((task) => task.priority === "P4");
  const readinessState = openP0.length > 0 ? "warning" : "success";
  const readinessText =
    openP0.length > 0
      ? "Hold for Pilot: Open P0 items remain"
      : "No open P0 blockers from parsed backlog";

  const sections: Record<SectionId, { title: string; href: string; description?: string }[]> = {
    p0: [
      {
        title: "Clinical workflow proof",
        href: "/clinical/intelligence",
      },
      {
        title: "Reconciliation path",
        href: "/pipelines/openehr",
      },
      {
        title: "Operations drill workspace",
        href: "/pipelines/openehr/operations",
      },
    ],
    p4: [
      {
        title: "Data quality and evidence",
        href: "/analytics/knowledge-graph",
      },
      {
        title: "Operational reporting",
        href: "/admin/dashboard",
      },
      {
        title: "Escalation evidence",
        href: "/security",
      },
    ],
    evidence: [
      {
        title: "Readiness docs",
        href: "/docs",
      },
      {
        title: "Evidence changelog",
        href: "/changelog",
      },
      {
        title: "Trust Hub",
        href: "/trust",
      },
    ],
    demo: [
      {
        title: "Sales demo workspace",
        description: "Full guided walkthrough of platform capabilities",
        href: "/sales-demo",
      },
      {
        title: "Sales demo: Clinical safety + fallback",
        description: "Clinical agent with degraded mode and confidence policy",
        href: "/clinical/intelligence",
      },
      {
        title: "Sales demo: Interop + OpenEHR",
        description: "OpenEHR composition import, export, and archetype mapping",
        href: "/pipelines/openehr",
      },
      {
        title: "Sales demo: Operations resilience",
        description: "Dry-run import, reconciliation, and batch rollback",
        href: "/pipelines/openehr/operations",
      },
    ],
  };

  return (
    <div className="min-h-screen bg-white">
      <nav className="sticky top-0 z-50 backdrop-blur-xl bg-white/90 border-b border-slate-200/70">
        <div className="max-w-[1100px] mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="h-4 w-4 text-slate-700" />
            <span className="text-[15px] font-semibold tracking-[-0.02em] text-slate-900">
              Sulci Trust & Proof Center
            </span>
          </div>
          <Link href="/" className="text-[13px] text-slate-500 hover:text-slate-900 transition-colors">
            &larr; Back to home
          </Link>
        </div>
      </nav>

      <main className="max-w-[1100px] mx-auto px-6 py-12">
        <div className="mb-8">
          <p className="text-xs uppercase tracking-[0.08em] text-slate-500">Pilot Visibility</p>
          <h1 className="mt-2 text-[2rem] md:text-[2.4rem] font-semibold text-slate-900 tracking-[-0.03em]">
            Clinical evidence map for live confidence
          </h1>
          <p className="mt-3 text-[14px] text-slate-600 leading-relaxed max-w-3xl">
            This page is evidence-first: each trust claim links back to operational tasks and evidence artifacts
            in this repository.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <SummaryCard
            title="Pilot posture"
            description={readinessText}
            metric={openP0.length > 0 ? `${openP0.length} open` : "Clear"}
            icon={AlertTriangle}
            tone={readinessState}
          />
          <SummaryCard
            title="P0 open (top-level)"
            description="Blocking items in repo-backed priority list"
            metric={`${snapshot.counts.openTopLevelByPriority.P0}/${snapshot.counts.totalTopLevel.P0}`}
            icon={ShieldCheck}
            tone="warning"
          />
          <SummaryCard
            title="P4 open (top-level)"
            description="Strategic work available after pilot"
            metric={`${snapshot.counts.openTopLevelByPriority.P4}/${snapshot.counts.totalTopLevel.P4}`}
            icon={CalendarClock}
            tone="neutral"
          />
          <SummaryCard
            title="Evidence artifacts"
            description="Repository evidence paths discovered"
            metric={snapshot.evidenceArtifacts.length}
            icon={FileCheck}
            tone="neutral"
          />
        </div>

        <div className="mt-8 grid grid-cols-1 xl:grid-cols-3 gap-4">
          <section className="xl:col-span-2 rounded-xl border border-slate-200 p-5">
            <div className="mb-4 flex items-center gap-2">
              <Activity className="h-4 w-4 text-slate-600" />
              <h2 className="text-lg font-semibold text-slate-900">P0 blockers to close before external pilot</h2>
            </div>
            {openP0.length === 0 ? (
              <p className="text-sm text-slate-500">No open P0 items were found in parsed checklist.</p>
            ) : (
              <div className="space-y-4">
                {openP0.map((task) => {
                  const subtasks = subtaskRowsFor(task.id, snapshot.openSubtasks);
                  const status = renderStatusBadge(false, "open");
                  return (
                    <article key={task.id} className="rounded-lg border border-slate-200 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-medium text-slate-900">{task.id} — {task.title}</p>
                        <span className={status.className}>
                          <BadgeCheck className="h-3.5 w-3.5" />
                          {status.text}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        {task.owner ? `Owner: ${task.owner}` : "Owner not specified"} · Priority: {task.priority}
                      </p>
                      {subtasks.length > 0 && (
                        <div className="mt-3 space-y-2">
                          {subtasks.map((subtask) => (
                            <div key={subtask.id} className="text-xs text-slate-600">
                              • {subtask.id}: {subtask.title}
                            </div>
                          ))}
                        </div>
                      )}
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Link
                          href={sections.p0[1].href}
                          className="inline-flex items-center gap-1.5 text-xs text-slate-900 border border-slate-300 rounded-md px-2.5 py-1.5"
                        >
                          Open related demo
                          <ArrowRight className="h-3.5 w-3.5" />
                        </Link>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>

          <section className="rounded-xl border border-slate-200 p-5">
            <div className="mb-4 flex items-center gap-2">
              <TimerReset className="h-4 w-4 text-slate-600" />
              <h2 className="text-lg font-semibold text-slate-900">Live readiness signal</h2>
            </div>
            <BackendHealthProbe />
            <p className="mt-3 text-xs text-slate-500">
              Backlog snapshot generated: {formatTime(snapshot.generatedAt)} · Source updated: {formatTime(snapshot.sourceUpdatedAt)}.
            </p>
            <p className="mt-3 text-xs text-slate-500">
              Source file: {snapshot.sourceFile}
            </p>
          </section>
        </div>

        <div className="mt-4 grid grid-cols-1 xl:grid-cols-2 gap-4">
          <section className="rounded-xl border border-slate-200 p-5">
            <div className="mb-4 flex items-center gap-2">
              <LayoutDashboard className="h-4 w-4 text-slate-600" />
              <h2 className="text-lg font-semibold text-slate-900">Evidence map</h2>
            </div>
            {snapshot.evidenceArtifacts.length === 0 ? (
              <p className="text-sm text-slate-500">No mapped evidence artifact paths were found yet.</p>
            ) : (
              <ul className="space-y-2">
                {snapshot.evidenceArtifacts.map((artifact) => (
                  <EvidenceStatus key={artifact.path} artifact={artifact} />
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-xl border border-slate-200 p-5">
            <div className="mb-4 flex items-center gap-2">
              <DatabaseZap className="h-4 w-4 text-slate-600" />
              <h2 className="text-lg font-semibold text-slate-900">P4 visibility progress</h2>
            </div>
            {openP4.length === 0 ? (
              <p className="text-sm text-slate-500">No open P4 top-level items were found in parsed data.</p>
            ) : (
              <ul className="space-y-2">
                {openP4.map((task) => {
                  const badge = renderStatusBadge(false, "open");
                  return (
                    <li key={task.id} className="rounded-lg border border-slate-200 p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-medium text-slate-900">{task.id}</p>
                          <p className="text-xs text-slate-600 mt-1">{task.title}</p>
                          {task.owner && (
                            <p className="text-xs text-slate-500 mt-1">Owner: {task.owner}</p>
                          )}
                        </div>
                        <span className={badge.className}>
                          <BadgeCheck className="h-3.5 w-3.5" />
                          {badge.text}
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>

        <section className="mt-4 rounded-xl border border-slate-200 p-5">
          <div className="mb-4 flex items-center justify-between gap-2">
            <h2 className="text-lg font-semibold text-slate-900">External-facing demo pack</h2>
            <EvidenceBundleButton
              snapshot={snapshot}
              label="Evidence bundle"
              mode="overview"
              scenarioId="trust-page-overview"
              evidenceAnchorHint="Open docs and tasks linked via Trust/Proof Center"
            />
          </div>
          <p className="text-sm text-slate-600 mb-3">
            Use these links to show capabilities without claiming proof that is not yet executed.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {sections.demo.map((scenario) => {
              const matchingTask = taskById("P4-018", snapshot.openTopLevel) ? "P4-018" : "P4-016";
              return (
                <ScenarioCard
                  key={scenario.title}
                  title={scenario.title}
                  description={scenario.description}
                  href={scenario.href}
                  evidence={`Backed by open tasks: ${matchingTask}`}
                />
              );
            })}
          </div>
        </section>
      </main>
    </div>
  );
}
