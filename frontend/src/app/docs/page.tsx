"use client";

import Link from "next/link";
import { Brain, FileText, Code, Zap, Database, GitBranch, ArrowRight, ShieldCheck, Play } from "lucide-react";

type EvidenceClaim = {
  claim: string;
  artifact: string;
  updated: string;
};

type DocSection = {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  href: string;
  evidenceArtifact: string;
  evidenceFreshness: string;
};

export default function DocsPage() {
  const evidenceClaims: EvidenceClaim[] = [
    {
      claim: "Trust/Readiness claim routing",
      artifact: "frontend/src/app/docs/page.tsx → /trust",
      updated: "2026-02-16",
    },
    {
      claim: "Sales demo discoverability",
      artifact: "frontend/src/app/sales-demo/page.tsx",
      updated: "2026-02-16",
    },
    {
      claim: "Operational docs + changelog anchors",
      artifact: "frontend/src/app/changelog/page.tsx",
      updated: "2026-02-16",
    },
    {
      claim: "Per-section evidence artifact coverage",
      artifact: "tasks/26_frontend_sales_readiness_p0_p4_todo.md (P4-020)",
      updated: "2026-02-16",
    },
  ];

  const sections: DocSection[] = [
    { icon: Zap, title: "Quickstart", description: "Ingest your first document, extract concepts, and query the knowledge graph.", href: "/login?next=/dashboard", evidenceArtifact: "backend/app/api/documents.py", evidenceFreshness: "2026-02-14" },
    { icon: Code, title: "API Reference", description: "REST API documentation with authentication guides and rate limit details.", href: "/login?next=/dashboard", evidenceArtifact: "backend/app/main.py (OpenAPI spec)", evidenceFreshness: "2026-02-16" },
    { icon: FileText, title: "NLP Pipeline", description: "Extraction engine — rule-based patterns, ML models, assertion detection, and negation handling.", href: "/login?next=/nlp", evidenceArtifact: "backend/app/services/narrative_extractor.py", evidenceFreshness: "2026-02-15" },
    { icon: Database, title: "Ontology Mapping", description: "Mapping clinical concepts to UMLS, OMOP CDM, SNOMED CT, ICD-10, and RxNorm with confidence scoring.", href: "/login?next=/vocabularies", evidenceArtifact: "backend/app/services/clinical_ontology_mapper.py", evidenceFreshness: "2026-02-15" },
    { icon: GitBranch, title: "Knowledge Graph", description: "Building and querying clinical knowledge graphs. Node types, edge semantics, and graph query patterns.", href: "/login?next=/clinical", evidenceArtifact: "backend/app/services/graph_builder_service.py", evidenceFreshness: "2026-02-14" },
    { icon: FileText, title: "FHIR & Interoperability", description: "FHIR R4 import/export, resource mapping, and EHR integration.", href: "/login?next=/exports", evidenceArtifact: "backend/app/services/fhir_export_service.py", evidenceFreshness: "2026-02-14" },
    { icon: ShieldCheck, title: "Trust Center", description: "Evidence-backed pilot readiness and proof links.", href: "/trust", evidenceArtifact: "docs/operations/pre_pilot_signoff_matrix.md", evidenceFreshness: "2026-02-16" },
    { icon: Play, title: "Sales Demo", description: "Clinical and interoperability walkthroughs for sales and partner demos.", href: "/sales-demo", evidenceArtifact: "frontend/src/app/sales-demo/page.tsx", evidenceFreshness: "2026-02-16" },
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

      <main className="max-w-[900px] mx-auto px-6 py-20 md:py-32">
        <div className="text-center mb-16">
          <h1 className="text-[2rem] md:text-[2.5rem] font-semibold tracking-[-0.04em] text-neutral-900 mb-4">Documentation</h1>
          <p className="text-neutral-500 max-w-lg mx-auto text-[16px] leading-relaxed">
            Everything you need to integrate Sulci into your clinical data pipeline.
          </p>
        </div>

        <section className="mb-8 rounded-xl border border-neutral-200/80 p-4">
          <h2 className="text-sm font-semibold text-neutral-900 uppercase tracking-[0.08em] mb-3">
            Evidence index
          </h2>
          <ul className="space-y-2 text-[13px] text-neutral-600">
            {evidenceClaims.map((item) => (
              <li key={item.claim} className="flex items-start gap-2">
                <span className="text-neutral-300 mt-1">&#8226;</span>
                <span>
                  <span className="font-medium text-neutral-900">{item.claim}</span>
                  <span className="ml-2 text-neutral-400">•</span>
                  <span className="font-mono text-[12px]">{item.artifact}</span>
                  <span className="ml-2 text-neutral-400">Updated {item.updated}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sections.map((s) => (
            <Link key={s.title} href={s.href} className="group p-6 rounded-xl border border-neutral-200/80 hover:border-neutral-300 hover:shadow-[0_2px_12px_rgba(0,0,0,0.04)] transition-all">
              <div className="flex items-center gap-3 mb-3">
                <div className="h-9 w-9 rounded-lg bg-neutral-100 flex items-center justify-center">
                  <s.icon className="h-4.5 w-4.5 text-neutral-600" />
                </div>
                <h3 className="text-[15px] font-semibold text-neutral-900">{s.title}</h3>
                <ArrowRight className="h-3.5 w-3.5 text-neutral-300 group-hover:text-neutral-600 ml-auto transition-colors" />
              </div>
              <p className="text-[14px] text-neutral-500 leading-relaxed">{s.description}</p>
              <p className="mt-2 text-[11px] text-neutral-400">
                Artifact: <span className="font-mono">{s.evidenceArtifact}</span>
                <span className="mx-1.5">·</span>
                Updated {s.evidenceFreshness}
              </p>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}
