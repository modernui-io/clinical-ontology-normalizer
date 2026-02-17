"use client";

import Link from "next/link";
import { Brain } from "lucide-react";

export default function AboutPage() {
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
        <h1 className="text-[2rem] md:text-[2.5rem] font-semibold tracking-[-0.04em] text-neutral-900 mb-8">About Sulci</h1>

        <div className="text-[15px] leading-relaxed text-neutral-600 space-y-6">
          <p>
            Sulci AI builds clinical data infrastructure. We take unstructured clinical notes — the messy, free-text reality of healthcare — and transform them into structured, standards-compliant, traceable clinical knowledge.
          </p>

          <p>
            Our platform combines rule-based and ML-powered NLP extraction with deep ontology mapping across UMLS, OMOP CDM, SNOMED CT, ICD-10, and RxNorm. Every extracted concept carries full provenance: the source text, the extraction method, the mapping confidence, and the reasoning chain that produced it.
          </p>

          <p>
            The result is a clinical knowledge graph — a structured, queryable representation of patient data that supports clinical decision support, pharmacovigilance, cohort identification, regulatory reporting, and research. All built on open standards. All with full auditability.
          </p>

          <h2 className="text-[18px] font-semibold text-neutral-900 mt-10 mb-3">Why &quot;Sulci&quot;?</h2>
          <p>
            Sulci are the grooves and folds of the cerebral cortex — the physical structure that gives the brain its capacity for complex thought. They represent the hidden architecture beneath the surface. That&apos;s what we do: reveal the structured knowledge hidden within unstructured clinical text.
          </p>

          <h2 className="text-[18px] font-semibold text-neutral-900 mt-10 mb-3">Our Approach</h2>
          <p>
            We believe clinical AI must be transparent, auditable, and grounded in established medical ontologies. We don&apos;t build black boxes. Every output has a traceable path back to the source evidence. That&apos;s not a feature — it&apos;s a requirement for responsible AI in healthcare.
          </p>

          <h2 className="text-[18px] font-semibold text-neutral-900 mt-10 mb-3">Contact</h2>
          <p>
            Reach us at <span className="text-neutral-900 font-medium">hello@sulci.ai</span>
          </p>
        </div>
      </main>
    </div>
  );
}
