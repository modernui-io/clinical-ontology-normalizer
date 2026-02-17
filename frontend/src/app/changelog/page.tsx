"use client";

import Link from "next/link";
import { Brain, CheckCircle, AlertTriangle, XCircle } from "lucide-react";
import { type EvidenceStatus, type FreshnessSLA, type SupportingLink, getEvidenceStatusColor } from "@/lib/evidence";

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "Verified":
      return <CheckCircle className="h-3 w-3 text-emerald-600" />;
    case "Stale":
      return <AlertTriangle className="h-3 w-3 text-amber-600" />;
    default:
      return <XCircle className="h-3 w-3 text-red-600" />;
  }
}

interface ChangeEntry {
  text: string;
  artifact: string;
  freshness: string;
  claim_id: string;
  verified_by: string;
  status: EvidenceStatus;
  freshness_sla: FreshnessSLA;
  supportingLinks?: SupportingLink[];
}

export default function ChangelogPage() {
  const entries = [
    {
      date: "February 2026",
      version: "v2.4",
      evidence: "tasks/09_master_change_backlog_p0_p4.md",
      updated: "2026-02-16",
      changes: [
        { text: "Knowledge graph builder with full provenance tracking", artifact: "backend/app/services/graph_builder_service.py", freshness: "2026-02-14", claim_id: "CLAIM-CL-001", verified_by: "CTO", status: "verified" as EvidenceStatus, freshness_sla: "per-release" as FreshnessSLA, supportingLinks: [{ label: "KG Docs", href: "/docs" }] },
        { text: "GraphRAG query engine for clinical reasoning", artifact: "backend/app/services/graph_augmented_rag.py", freshness: "2026-02-15", claim_id: "CLAIM-CL-002", verified_by: "VP Engineering", status: "verified" as EvidenceStatus, freshness_sla: "per-release" as FreshnessSLA },
        { text: "Clinical decision support (CDS Hooks) integration", artifact: "backend/app/api/cds_hooks.py", freshness: "2026-02-14", claim_id: "CLAIM-CL-003", verified_by: "VP Engineering", status: "verified" as EvidenceStatus, freshness_sla: "per-release" as FreshnessSLA },
        { text: "Drug interaction checker with severity scoring", artifact: "backend/app/services/drug_safety.py", freshness: "2026-02-15", claim_id: "CLAIM-CL-004", verified_by: "CISO", status: "verified" as EvidenceStatus, freshness_sla: "per-release" as FreshnessSLA },
      ] as ChangeEntry[],
    },
    {
      date: "January 2026",
      version: "v2.3",
      evidence: "tasks/09_master_change_backlog_p0_p4.md",
      updated: "2026-01-24",
      changes: [
        { text: "FHIR R4 import/export with Condition, MedicationRequest, and Observation resources", artifact: "backend/app/services/fhir_export_service.py", freshness: "2026-01-20", claim_id: "CLAIM-CL-005", verified_by: "VP Engineering", status: "verified" as EvidenceStatus, freshness_sla: "per-release" as FreshnessSLA, supportingLinks: [{ label: "Interop Docs", href: "/docs" }] },
        { text: "Assertion detection engine (negation, hypothetical, family history)", artifact: "backend/app/services/narrative_extractor.py", freshness: "2026-01-18", claim_id: "CLAIM-CL-006", verified_by: "VP Engineering", status: "verified" as EvidenceStatus, freshness_sla: "per-release" as FreshnessSLA },
        { text: "Bulk document ingestion API", artifact: "backend/app/api/documents.py", freshness: "2026-01-15", claim_id: "CLAIM-CL-007", verified_by: "CTO", status: "verified" as EvidenceStatus, freshness_sla: "monthly" as FreshnessSLA },
        { text: "Clinical calculators (CHA2DS2-VASc, MELD, Wells, CURB-65)", artifact: "backend/app/services/clinical_calculators.py", freshness: "2026-01-22", claim_id: "CLAIM-CL-008", verified_by: "VP Engineering", status: "verified" as EvidenceStatus, freshness_sla: "monthly" as FreshnessSLA },
      ] as ChangeEntry[],
    },
    {
      date: "December 2025",
      version: "v2.2",
      evidence: "tasks/09_master_change_backlog_p0_p4.md",
      updated: "2026-01-02",
      changes: [
        { text: "ML ensemble NLP pipeline with transformer-based extraction", artifact: "backend/app/services/ml_ensemble_extractor.py", freshness: "2025-12-20", claim_id: "CLAIM-CL-009", verified_by: "VP Engineering", status: "verified" as EvidenceStatus, freshness_sla: "quarterly" as FreshnessSLA },
        { text: "OMOP CDM vocabulary mapping with confidence scoring", artifact: "backend/app/services/clinical_ontology_mapper.py", freshness: "2025-12-18", claim_id: "CLAIM-CL-010", verified_by: "CTO", status: "verified" as EvidenceStatus, freshness_sla: "quarterly" as FreshnessSLA },
        { text: "Clinical trials management module", artifact: "backend/app/api/clinical_trials.py", freshness: "2025-12-15", claim_id: "CLAIM-CL-011", verified_by: "VP Engineering", status: "verified" as EvidenceStatus, freshness_sla: "quarterly" as FreshnessSLA },
        { text: "Audit logging and compliance reporting", artifact: "backend/app/middleware/audit_middleware.py", freshness: "2025-12-22", claim_id: "CLAIM-CL-012", verified_by: "CISO", status: "verified" as EvidenceStatus, freshness_sla: "quarterly" as FreshnessSLA },
      ] as ChangeEntry[],
    },
    {
      date: "November 2025",
      version: "v2.1",
      evidence: "tasks/09_master_change_backlog_p0_p4.md",
      updated: "2025-11-15",
      changes: [
        { text: "Rule-based NLP extraction engine", artifact: "backend/app/services/narrative_extractor.py", freshness: "2025-11-10", claim_id: "CLAIM-CL-013", verified_by: "CTO", status: "verified" as EvidenceStatus, freshness_sla: "quarterly" as FreshnessSLA },
        { text: "UMLS concept lookup and normalization", artifact: "backend/app/services/umls_service.py", freshness: "2025-11-08", claim_id: "CLAIM-CL-014", verified_by: "VP Engineering", status: "verified" as EvidenceStatus, freshness_sla: "quarterly" as FreshnessSLA },
        { text: "Patient knowledge graph visualization", artifact: "frontend/src/app/clinical/intelligence/page.tsx", freshness: "2025-11-12", claim_id: "CLAIM-CL-015", verified_by: "CTO", status: "verified" as EvidenceStatus, freshness_sla: "quarterly" as FreshnessSLA },
        { text: "REST API with OpenAPI documentation", artifact: "backend/app/main.py", freshness: "2025-11-14", claim_id: "CLAIM-CL-016", verified_by: "CTO", status: "verified" as EvidenceStatus, freshness_sla: "quarterly" as FreshnessSLA },
      ] as ChangeEntry[],
    },
  ];

  return (
    <div className="min-h-screen bg-white">
      <nav className="sticky top-0 z-50 backdrop-blur-xl bg-white/80 border-b border-neutral-200/60">
        <div className="max-w-[1200px] mx-auto px-6 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="h-7 w-7 rounded-lg bg-neutral-900 flex items-center justify-center"><Brain className="h-4 w-4 text-white" /></div>
            <span className="font-semibold text-[15px] tracking-[-0.02em]">Sulci</span>
          </Link>
          <Link href="/" className="text-[13px] text-neutral-500 hover:text-neutral-900 transition-colors">&larr; Back to home</Link>
        </div>
      </nav>

      <main className="max-w-[720px] mx-auto px-6 py-20 md:py-32">
        <h1 className="text-[2rem] md:text-[2.5rem] font-semibold tracking-[-0.04em] text-neutral-900 mb-4">Changelog</h1>
        <p className="text-neutral-500 text-[16px] leading-relaxed mb-16">What&apos;s new in Sulci.</p>
        <p className="mb-12 text-sm text-neutral-500 max-w-2xl leading-relaxed">
          Evidence-backed claims for the above releases should be cross-referenced in
          {" "}
          <a href="/trust" className="text-neutral-900 underline underline-offset-4">Trust/Proof Center</a>.
          Use that page for external-ready readiness evidence and artifact links.
        </p>

        <div className="space-y-12">
          {entries.map((entry) => (
            <div key={entry.version} className="relative pl-6 border-l-2 border-neutral-200">
              <div className="absolute -left-[7px] top-1 h-3 w-3 rounded-full bg-neutral-900" />
              <div className="flex items-center gap-3 mb-3">
                <span className="text-[13px] font-mono font-semibold text-neutral-900 px-2.5 py-0.5 rounded-md bg-neutral-100">{entry.version}</span>
                <span className="text-[13px] text-neutral-400">{entry.date}</span>
              </div>
              <p className="text-xs text-neutral-500 mb-2">
                Evidence anchor: <span className="font-mono">{entry.evidence}</span> • Updated {entry.updated}
              </p>
              <ul className="space-y-3">
                {entry.changes.map((change: ChangeEntry) => {
                  const color = getEvidenceStatusColor(change.status, change.freshness_sla, change.freshness);
                  return (
                    <li key={change.claim_id} className="text-[14px] text-neutral-600 leading-relaxed">
                      <div className="flex items-start gap-2">
                        <span className="mt-1.5 shrink-0">
                          <StatusIcon status={color.label} />
                        </span>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono text-[10px] text-neutral-400">{change.claim_id}</span>
                            <span>{change.text}</span>
                            <span className={`inline-flex rounded-full border px-1.5 py-0.5 text-[10px] font-medium ${color.bg} ${color.text} ${color.border}`}>
                              {color.label}
                            </span>
                          </div>
                          <div className="text-[11px] text-neutral-400 mt-0.5">
                            Artifact: <span className="font-mono">{change.artifact}</span>
                            <span className="mx-1">·</span>
                            {change.freshness}
                            <span className="mx-1">·</span>
                            Verified by {change.verified_by}
                            <span className="mx-1">·</span>
                            SLA: {change.freshness_sla}
                            {change.supportingLinks && change.supportingLinks.length > 0 && (
                              <>
                                <span className="mx-1">·</span>
                                {change.supportingLinks.map((link) => (
                                  <a key={link.href} href={link.href} className="inline-flex items-center gap-1 text-[10px] text-blue-600 hover:text-blue-800 underline underline-offset-2 ml-1">
                                    {link.label}
                                  </a>
                                ))}
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
