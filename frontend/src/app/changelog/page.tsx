"use client";

import Link from "next/link";
import { Brain } from "lucide-react";

export default function ChangelogPage() {
  const entries = [
    {
      date: "February 2026",
      version: "v2.4",
      evidence: "tasks/09_master_change_backlog_p0_p4.md",
      updated: "2026-02-16",
      changes: [
        { text: "Knowledge graph builder with full provenance tracking", artifact: "backend/app/services/graph_builder_service.py", freshness: "2026-02-14" },
        { text: "GraphRAG query engine for clinical reasoning", artifact: "backend/app/services/graph_augmented_rag.py", freshness: "2026-02-15" },
        { text: "Clinical decision support (CDS Hooks) integration", artifact: "backend/app/api/cds_hooks.py", freshness: "2026-02-14" },
        { text: "Drug interaction checker with severity scoring", artifact: "backend/app/services/drug_safety.py", freshness: "2026-02-15" },
      ],
    },
    {
      date: "January 2026",
      version: "v2.3",
      evidence: "tasks/09_master_change_backlog_p0_p4.md",
      updated: "2026-01-24",
      changes: [
        { text: "FHIR R4 import/export with Condition, MedicationRequest, and Observation resources", artifact: "backend/app/services/fhir_export_service.py", freshness: "2026-01-20" },
        { text: "Assertion detection engine (negation, hypothetical, family history)", artifact: "backend/app/services/narrative_extractor.py", freshness: "2026-01-18" },
        { text: "Bulk document ingestion API", artifact: "backend/app/api/documents.py", freshness: "2026-01-15" },
        { text: "Clinical calculators (CHA2DS2-VASc, MELD, Wells, CURB-65)", artifact: "backend/app/services/clinical_calculators.py", freshness: "2026-01-22" },
      ],
    },
    {
      date: "December 2025",
      version: "v2.2",
      evidence: "tasks/09_master_change_backlog_p0_p4.md",
      updated: "2026-01-02",
      changes: [
        { text: "ML ensemble NLP pipeline with transformer-based extraction", artifact: "backend/app/services/ml_ensemble_extractor.py", freshness: "2025-12-20" },
        { text: "OMOP CDM vocabulary mapping with confidence scoring", artifact: "backend/app/services/clinical_ontology_mapper.py", freshness: "2025-12-18" },
        { text: "Clinical trials management module", artifact: "backend/app/api/clinical_trials.py", freshness: "2025-12-15" },
        { text: "Audit logging and compliance reporting", artifact: "backend/app/middleware/audit_middleware.py", freshness: "2025-12-22" },
      ],
    },
    {
      date: "November 2025",
      version: "v2.1",
      evidence: "tasks/09_master_change_backlog_p0_p4.md",
      updated: "2025-11-15",
      changes: [
        { text: "Rule-based NLP extraction engine", artifact: "backend/app/services/narrative_extractor.py", freshness: "2025-11-10" },
        { text: "UMLS concept lookup and normalization", artifact: "backend/app/services/umls_service.py", freshness: "2025-11-08" },
        { text: "Patient knowledge graph visualization", artifact: "frontend/src/app/clinical/intelligence/page.tsx", freshness: "2025-11-12" },
        { text: "REST API with OpenAPI documentation", artifact: "backend/app/main.py", freshness: "2025-11-14" },
      ],
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
                {entry.changes.map((change) => (
                  <li key={change.text} className="text-[14px] text-neutral-600 leading-relaxed">
                    <div className="flex items-start gap-2">
                      <span className="text-neutral-300 mt-1.5 text-[8px]">&#9679;</span>
                      <div>
                        <span>{change.text}</span>
                        <div className="text-[11px] text-neutral-400 mt-0.5">
                          Artifact: <span className="font-mono">{change.artifact}</span>
                          <span className="mx-1">·</span>
                          {change.freshness}
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
