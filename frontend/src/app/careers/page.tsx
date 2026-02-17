"use client";

import Link from "next/link";
import { Brain, MapPin, ArrowRight } from "lucide-react";

export default function CareersPage() {
  const openings = [
    { title: "Senior Backend Engineer", team: "Platform", location: "Remote (US)", description: "Build and scale our clinical NLP and ontology mapping pipelines. Python, FastAPI, PostgreSQL." },
    { title: "ML Engineer — Clinical NLP", team: "AI", location: "Remote (US)", description: "Develop and improve transformer-based models for clinical entity extraction, assertion detection, and relation extraction." },
    { title: "Frontend Engineer", team: "Product", location: "Remote (US)", description: "Build the next generation of clinical data tools with React, Next.js, and knowledge graph visualizations." },
    { title: "Clinical Informaticist", team: "Clinical", location: "Remote (US)", description: "Bridge clinical domain expertise with engineering. Help shape our ontology mapping strategy and validate NLP outputs." },
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
          <h1 className="text-[2rem] md:text-[2.5rem] font-semibold tracking-[-0.04em] text-neutral-900 mb-4">Join Sulci</h1>
          <p className="text-neutral-500 max-w-lg mx-auto text-[16px] leading-relaxed">
            We&apos;re building clinical data infrastructure that turns unstructured notes into structured, traceable knowledge. Come help us make healthcare data work.
          </p>
        </div>

        <div className="space-y-4 mb-16">
          {openings.map((job) => (
            <div key={job.title} className="group p-6 rounded-xl border border-neutral-200/80 hover:border-neutral-300 hover:shadow-[0_2px_12px_rgba(0,0,0,0.04)] transition-all cursor-pointer">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-[15px] font-semibold text-neutral-900 mb-1">{job.title}</h3>
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-[12px] font-medium px-2.5 py-0.5 rounded-full bg-neutral-100 text-neutral-600">{job.team}</span>
                    <span className="flex items-center gap-1 text-[12px] text-neutral-400"><MapPin className="h-3 w-3" />{job.location}</span>
                  </div>
                  <p className="text-[14px] text-neutral-500 leading-relaxed">{job.description}</p>
                </div>
                <ArrowRight className="h-4 w-4 text-neutral-300 group-hover:text-neutral-600 mt-1 flex-shrink-0 transition-colors" />
              </div>
            </div>
          ))}
        </div>

        <div className="rounded-xl border border-neutral-200/80 p-8 md:p-10 text-center">
          <h2 className="text-[18px] font-semibold text-neutral-900 mb-3">Don&apos;t see your role?</h2>
          <p className="text-[14px] text-neutral-500 leading-relaxed max-w-lg mx-auto mb-6">
            We&apos;re always looking for exceptional people who care about healthcare data. Send us a note and tell us what you&apos;d build.
          </p>
          <p className="text-[14px] text-neutral-900 font-medium">careers@sulci.ai</p>
        </div>
      </main>
    </div>
  );
}
