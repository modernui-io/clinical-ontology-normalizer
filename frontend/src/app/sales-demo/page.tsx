import Link from "next/link";
import {
  ArrowRight,
  ShieldCheck,
  PlayCircle,
  FileText,
  Activity,
  Settings,
  FileSearch,
  CircleDashed,
} from "lucide-react";
import { getReadinessSnapshot } from "@/lib/readinessEvidence.server";
import EvidenceBundleButton from "@/components/readiness/EvidenceBundleButton";
import ReviewerChecklist from "@/components/readiness/ReviewerChecklist";
import ScenarioEvidence from "@/components/readiness/ScenarioEvidence";

type DemoScenario = {
  id: string;
  title: string;
  summary: string;
  href: string;
  evidenceHint: string;
  readiness: "ready" | "simulation";
  claims: string[];
};

const demoScenarios: DemoScenario[] = [
  {
    id: "sales-clinical-safety",
    title: "Clinical safety + provenance",
    summary:
      "Demonstrate confidence gating, source evidence propagation, and degraded-mode behavior for unsafe scenarios.",
    href: "/clinical/intelligence",
    evidenceHint: "Clinical outputs should reference source evidence IDs and confidence rationale.",
    readiness: "ready",
    claims: [
      "Question to answer path",
      "Evidence IDs and confidence fields",
      "Unsafe path shows refusal + escalation",
    ],
  },
  {
    id: "sales-interoperability",
    title: "Interop + OpenEHR replay",
    summary:
      "Walk through import/extract/reconciliation path and show evidence hooks in docs and runbooks.",
    href: "/pipelines/openehr",
    evidenceHint: "Show mapping contract and reconciliation artifact links before external onboarding statements.",
    readiness: "ready",
    claims: [
      "End-to-end clinical data route",
      "Contract-driven extraction and conversion evidence",
      "Reconciliation workflow path",
    ],
  },
  {
    id: "sales-ops-resilience",
    title: "Operations resilience",
    summary:
      "Walk through readiness proof links and operational drill evidence for backup/rollback posture.",
    href: "/pipelines/openehr/operations",
    evidenceHint: "Pair with P0-025, P0-026, P0-027 evidence before claiming production resilience.",
    readiness: "simulation",
    claims: [
      "Readiness/health status visibility",
      "Escalation and response-path controls",
      "Backups and failover drill tracking",
    ],
  },
];

function readinessTone(openP0: number): "warning" | "success" {
  return openP0 > 0 ? "warning" : "success";
}

export default async function SalesDemoPage() {
  const snapshot = await getReadinessSnapshot();
  const openP0 = snapshot.openTopLevel.filter((task) => task.priority === "P0").length;
  const snapshotMode = readinessTone(openP0);

  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="sticky top-0 z-50 backdrop-blur-xl bg-white/90 border-b border-slate-200/70">
        <div className="max-w-[1100px] mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <PlayCircle className="h-4 w-4 text-slate-700" />
            <span className="text-[15px] font-semibold tracking-[-0.02em] text-slate-900">
              Sulci Sales Demo Workspace
            </span>
          </div>
          <Link href="/" className="text-[13px] text-slate-500 hover:text-slate-900 transition-colors">
            &larr; Back to home
          </Link>
        </div>
      </nav>

      <main className="max-w-[1100px] mx-auto px-6 py-12 space-y-6">
        <header>
          <p className="text-xs uppercase tracking-[0.08em] text-slate-500">Pilot visibility</p>
          <h1 className="mt-2 text-[2rem] md:text-[2.4rem] font-semibold text-slate-900 tracking-[-0.03em]">
            Production-facing demo workspace
          </h1>
          <p className="mt-3 text-[14px] text-slate-600 leading-relaxed max-w-3xl">
            These scenarios are intended for external walkthroughs. If any critical readiness item is missing or
            unresolved, call it out in the evidence bundle before claiming production guarantees.
          </p>
        </header>

        <section className="rounded-xl border border-slate-200 p-5 bg-white">
          <div className="flex flex-wrap justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-900">Scenario launch deck</h2>
            <p
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                snapshotMode === "warning"
                  ? "bg-amber-100 text-amber-800 border border-amber-200"
                  : "bg-emerald-100 text-emerald-800 border border-emerald-200"
              }`}
            >
              {snapshotMode === "warning" ? "Pilot hold: open P0s remain" : "P0 blockers clear"}
            </p>
          </div>

          <div className="mt-5 grid md:grid-cols-2 xl:grid-cols-3 gap-4">
            {demoScenarios.map((scenario) => (
              <article
                key={scenario.id}
                className="rounded-lg border border-slate-200 p-4 bg-white hover:shadow-sm transition-shadow"
              >
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-sm font-semibold text-slate-900">{scenario.title}</h3>
                  <ShieldCheck
                    className={`h-4 w-4 ${
                      scenario.readiness === "ready" ? "text-emerald-600" : "text-amber-600"
                    }`}
                  />
                </div>
                <p className="mt-2 text-xs text-slate-600 leading-relaxed">{scenario.summary}</p>
                <p className="mt-2 text-xs text-slate-500">Evidence anchor: {scenario.evidenceHint}</p>

                <ul className="mt-3 space-y-2 text-xs text-slate-600">
                  {scenario.claims.map((claim) => (
                    <li key={claim} className="flex gap-2">
                      <CircleDashed className="h-3.5 w-3.5 mt-0.5 text-slate-400" />
                      <span>{claim}</span>
                    </li>
                  ))}
                </ul>

                <div className="mt-4">
                  <Link
                    href={scenario.href}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-900 border border-slate-300 rounded-md px-2.5 py-1.5"
                  >
                    Open scenario
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>

                <ScenarioEvidence
                  scenarioId={scenario.id}
                  scenarioTitle={scenario.title}
                  claims={scenario.claims}
                  href={scenario.href}
                  readiness={scenario.readiness}
                  evidenceHint={scenario.evidenceHint}
                />
              </article>
            ))}
          </div>
        </section>

        <section className="grid lg:grid-cols-2 gap-4">
          <article className="rounded-xl border border-slate-200 p-5 bg-white">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-slate-700" />
              <h2 className="text-lg font-semibold text-slate-900">Evidence pack for this run</h2>
            </div>
            <p className="mt-2 text-sm text-slate-600">
              Export a package with open blockers, artifact freshness, and linked task IDs before external review.
            </p>
            <div className="mt-4">
              <EvidenceBundleButton
                snapshot={snapshot}
                label="Demo evidence bundle"
                mode="scenario"
                scenarioId="sales-demo-overview"
                evidenceAnchorHint="Scenario deck + Trust/Proof links"
              />
            </div>
          </article>

          <article className="rounded-xl border border-slate-200 p-5 bg-white">
            <div className="flex items-center gap-2">
              <Settings className="h-4 w-4 text-slate-700" />
              <h2 className="text-lg font-semibold text-slate-900">Readiness links</h2>
            </div>
            <p className="mt-2 text-sm text-slate-600">
              Point external stakeholders to these pages before asserting any operational promise.
            </p>
            <ul className="mt-3 space-y-2 text-sm text-slate-700">
              <li className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-2">
                  <FileText className="h-3.5 w-3.5 text-slate-500" />
                  Trust & Proof
                </span>
                <Link href="/trust" className="text-slate-900 underline underline-offset-4">
                  Open
                </Link>
              </li>
              <li className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-2">
                  <FileSearch className="h-3.5 w-3.5 text-slate-500" />
                  Proof log references
                </span>
                <Link href="/proof" className="text-slate-900 underline underline-offset-4">
                  Open
                </Link>
              </li>
              <li className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-2">
                  <ShieldCheck className="h-3.5 w-3.5 text-slate-500" />
                  Security posture
                </span>
                <Link href="/security" className="text-slate-900 underline underline-offset-4">
                  Open
                </Link>
              </li>
              <li className="flex items-center justify-between gap-2 pt-2">
                <span className="inline-flex items-center gap-2 text-slate-500">
                  Open P0 blockers:
                </span>
                <span className="font-medium">{openP0}</span>
              </li>
            </ul>
          </article>
        </section>

        <ReviewerChecklist
          scenarioIds={demoScenarios.map((s) => s.id)}
        />
      </main>
    </div>
  );
}
