"use client";

import Link from "next/link";
import { Brain, FileText, Code, Zap, Database, GitBranch, ArrowRight, ShieldCheck, Play, CheckCircle, AlertTriangle, XCircle } from "lucide-react";
import { type EvidenceStatus, type FreshnessSLA, type EvidenceCategory, type EvidenceEntry, type SupportingLink, getEvidenceStatusColor } from "@/lib/evidence";

type DocSection = {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  href: string;
  evidenceArtifact: string;
  evidenceFreshness: string;
  owner: string;
  claim_id: string;
  status: EvidenceStatus;
  freshness_sla: FreshnessSLA;
  verified_by: string;
  supportingLinks?: SupportingLink[];
};

function StatusIcon({ status }: { status: "verified" | "stale" | "unverified" | "disputed" }) {
  switch (status) {
    case "verified":
      return <CheckCircle className="h-3.5 w-3.5 text-emerald-600" />;
    case "stale":
      return <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />;
    case "unverified":
    case "disputed":
      return <XCircle className="h-3.5 w-3.5 text-red-600" />;
  }
}

export default function DocsPage() {
  const evidenceClaims: EvidenceEntry[] = [
    {
      claim_id: "CLAIM-DOC-001",
      claim_text: "Trust/Readiness claim routing",
      category: "product",
      evidence_paths: ["frontend/src/app/docs/page.tsx", "frontend/src/app/trust/page.tsx"],
      last_verified: "2026-02-16",
      verified_by: "CTO",
      freshness_sla: "per-release",
      status: "verified",
      supporting_links: [{ label: "Trust Center", href: "/trust" }],
    },
    {
      claim_id: "CLAIM-DOC-002",
      claim_text: "Sales demo discoverability",
      category: "product",
      evidence_paths: ["frontend/src/app/sales-demo/page.tsx"],
      last_verified: "2026-02-16",
      verified_by: "VP Sales",
      freshness_sla: "per-release",
      status: "verified",
      supporting_links: [{ label: "Sales Demo", href: "/sales-demo" }],
    },
    {
      claim_id: "CLAIM-DOC-003",
      claim_text: "Operational docs + changelog anchors",
      category: "operational",
      evidence_paths: ["frontend/src/app/changelog/page.tsx"],
      last_verified: "2026-02-16",
      verified_by: "CTO",
      freshness_sla: "per-release",
      status: "verified",
      supporting_links: [{ label: "Changelog", href: "/changelog" }],
    },
    {
      claim_id: "CLAIM-DOC-004",
      claim_text: "Per-section evidence artifact coverage",
      category: "operational",
      evidence_paths: ["tasks/26_frontend_sales_readiness_p0_p4_todo.md"],
      last_verified: "2026-02-16",
      verified_by: "CTO",
      freshness_sla: "monthly",
      status: "verified",
    },
  ];

  const sections: DocSection[] = [
    { icon: Zap, title: "Quickstart", description: "Ingest your first document, extract concepts, and query the knowledge graph.", href: "/login?next=/dashboard", evidenceArtifact: "backend/app/api/documents.py", evidenceFreshness: "2026-02-14", owner: "Engineering", claim_id: "CLAIM-DOC-QS1", status: "verified", freshness_sla: "per-release", verified_by: "CTO" },
    { icon: Code, title: "API Reference", description: "REST API documentation with authentication guides and rate limit details.", href: "/login?next=/dashboard", evidenceArtifact: "backend/app/main.py (OpenAPI spec)", evidenceFreshness: "2026-02-16", owner: "Engineering", claim_id: "CLAIM-DOC-API1", status: "verified", freshness_sla: "per-release", verified_by: "CTO" },
    { icon: FileText, title: "NLP Pipeline", description: "Extraction engine — rule-based patterns, ML models, assertion detection, and negation handling.", href: "/login?next=/nlp", evidenceArtifact: "backend/app/services/narrative_extractor.py", evidenceFreshness: "2026-02-15", owner: "ML Engineering", claim_id: "CLAIM-DOC-NLP1", status: "verified", freshness_sla: "per-release", verified_by: "VP Engineering" },
    { icon: Database, title: "Ontology Mapping", description: "Mapping clinical concepts to UMLS, OMOP CDM, SNOMED CT, ICD-10, and RxNorm with confidence scoring.", href: "/login?next=/vocabularies", evidenceArtifact: "backend/app/services/clinical_ontology_mapper.py", evidenceFreshness: "2026-02-15", owner: "Clinical Engineering", claim_id: "CLAIM-DOC-ONTO1", status: "verified", freshness_sla: "per-release", verified_by: "VP Engineering" },
    { icon: GitBranch, title: "Knowledge Graph", description: "Building and querying clinical knowledge graphs. Node types, edge semantics, and graph query patterns.", href: "/login?next=/clinical", evidenceArtifact: "backend/app/services/graph_builder_service.py", evidenceFreshness: "2026-02-14", owner: "Engineering", claim_id: "CLAIM-DOC-KG1", status: "verified", freshness_sla: "per-release", verified_by: "CTO" },
    { icon: FileText, title: "FHIR & Interoperability", description: "FHIR R4 import/export, resource mapping, and EHR integration.", href: "/login?next=/exports", evidenceArtifact: "backend/app/services/fhir_export_service.py", evidenceFreshness: "2026-02-14", owner: "Interop Engineering", claim_id: "CLAIM-DOC-FHIR1", status: "verified", freshness_sla: "per-release", verified_by: "VP Engineering" },
    { icon: ShieldCheck, title: "Trust Center", description: "Evidence-backed pilot readiness and proof links.", href: "/trust", evidenceArtifact: "docs/operations/pre_pilot_signoff_matrix.md", evidenceFreshness: "2026-02-16", owner: "CTO Office", claim_id: "CLAIM-DOC-TRUST1", status: "verified", freshness_sla: "monthly", verified_by: "CTO", supportingLinks: [{ label: "Proof Center", href: "/proof" }] },
    { icon: Play, title: "Sales Demo", description: "Clinical and interoperability walkthroughs for sales and partner demos.", href: "/sales-demo", evidenceArtifact: "frontend/src/app/sales-demo/page.tsx", evidenceFreshness: "2026-02-16", owner: "Sales Engineering", claim_id: "CLAIM-DOC-DEMO1", status: "verified", freshness_sla: "per-release", verified_by: "VP Sales", supportingLinks: [{ label: "Evidence Export", href: "/sales-demo" }] },
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
          <ul className="space-y-3 text-[13px] text-neutral-600">
            {evidenceClaims.map((item) => {
              const color = getEvidenceStatusColor(item.status, item.freshness_sla, item.last_verified);
              return (
                <li key={item.claim_id} className="flex items-start gap-2">
                  <StatusIcon status={color.label.toLowerCase() as EvidenceStatus} />
                  <span className="flex-1">
                    <span className="font-mono text-[11px] text-neutral-400">{item.claim_id}</span>
                    <span className="ml-2 font-medium text-neutral-900">{item.claim_text}</span>
                    <span className={`ml-2 inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-medium ${color.bg} ${color.text} ${color.border}`}>
                      {color.label}
                    </span>
                    <span className="ml-2 text-[11px] text-neutral-400">{item.category}</span>
                    <div className="mt-0.5">
                      {item.evidence_paths.map((path) => (
                        <span key={path} className="block font-mono text-[11px] text-neutral-500">{path}</span>
                      ))}
                    </div>
                    <span className="text-[11px] text-neutral-400">
                      Verified by {item.verified_by} on {item.last_verified} | SLA: {item.freshness_sla}
                    </span>
                    {item.supporting_links && item.supporting_links.length > 0 && (
                      <div className="mt-0.5 flex items-center gap-2">
                        {item.supporting_links.map((link) => (
                          <a key={link.href} href={link.href} className="inline-flex items-center gap-1 text-[10px] text-blue-600 hover:text-blue-800 underline underline-offset-2">
                            {link.label}
                          </a>
                        ))}
                      </div>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sections.map((s) => {
            const color = getEvidenceStatusColor(s.status, s.freshness_sla, s.evidenceFreshness);
            return (
              <Link key={s.title} href={s.href} className="group p-6 rounded-xl border border-neutral-200/80 hover:border-neutral-300 hover:shadow-[0_2px_12px_rgba(0,0,0,0.04)] transition-all">
                <div className="flex items-center gap-3 mb-3">
                  <div className="h-9 w-9 rounded-lg bg-neutral-100 flex items-center justify-center">
                    <s.icon className="h-4.5 w-4.5 text-neutral-600" />
                  </div>
                  <h3 className="text-[15px] font-semibold text-neutral-900">{s.title}</h3>
                  <ArrowRight className="h-3.5 w-3.5 text-neutral-300 group-hover:text-neutral-600 ml-auto transition-colors" />
                </div>
                <p className="text-[14px] text-neutral-500 leading-relaxed">{s.description}</p>
                <div className="mt-2 flex items-center gap-1.5">
                  <StatusIcon status={color.label.toLowerCase() as EvidenceStatus} />
                  <span className={`inline-flex rounded-full border px-1.5 py-0.5 text-[10px] font-medium ${color.bg} ${color.text} ${color.border}`}>
                    {color.label}
                  </span>
                  <span className="text-[11px] text-neutral-400">{s.owner}</span>
                  <span className="text-[11px] text-neutral-400 ml-auto">{s.verified_by}</span>
                </div>
                <p className="mt-1 text-[11px] text-neutral-400">
                  <span className="font-mono">{s.evidenceArtifact}</span>
                  <span className="mx-1.5">·</span>
                  Updated {s.evidenceFreshness}
                  <span className="mx-1.5">·</span>
                  SLA: {s.freshness_sla}
                </p>
                {s.supportingLinks && s.supportingLinks.length > 0 && (
                  <div className="mt-1 flex items-center gap-2">
                    {s.supportingLinks.map((link) => (
                      <span key={link.href} className="inline-flex items-center gap-1 text-[10px] text-blue-600 underline underline-offset-2">
                        {link.label}
                      </span>
                    ))}
                  </div>
                )}
              </Link>
            );
          })}
        </div>
      </main>
    </div>
  );
}
