"use client";

import { useRef, useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  motion,
  useScroll,
  useTransform,
  useInView,
  AnimatePresence,
} from "framer-motion";
import {
  ArrowRight,
  Brain,
  Database,
  GitBranch,
  FileText,
  HeartPulse,
  Shield,
  FlaskConical,
  BarChart3,
  Pill,
  Workflow,
  CheckCircle2,
  Zap,
  Lock,
  Globe,
  Activity,
  Network,
  ChevronRight,
  Layers,
  Binary,
  Cpu,
  ExternalLink,
  Copy,
  Check,
  Menu,
  X,
} from "lucide-react";

// ============================================================================
// Design tokens
// ============================================================================
const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1];
const VIEWPORT = { once: true, margin: "-100px" as const };

// ============================================================================
// Logo component — custom Sulci brain mark
// ============================================================================
function SulciLogo({ className = "h-4 w-4", variant = "stroke", size = "sm" }: { className?: string; variant?: "stroke" | "filled"; size?: "sm" | "lg" }) {
  if (variant === "filled") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M11 3.5C7.5 4 5 6 4 8.5S3 13.5 4 16c1 2.5 3 4.5 5.5 5.5L11 22V3.5z" fill="currentColor"/>
        <path d="M13 3.5C16.5 4 19 6 20 8.5s1 5 0 7.5c-1 2.5-3 4.5-5.5 5.5L13 22V3.5z" fill="currentColor"/>
        <line x1="12" y1="3" x2="12" y2="22.5" stroke="white" strokeWidth="2.8" strokeLinecap="round"/>
        <path d="M4.5 11c2.5.5 4.5 0 7-1.5" stroke="white" strokeWidth="2" strokeLinecap="round"/>
        <path d="M19.5 11c-2.5.5-4.5 0-7-1.5" stroke="white" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    );
  }
  if (size === "lg") {
    return (
      <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M15 4C10.5 4.5 7.5 6.5 5.8 9 4.2 11.5 3.8 14.5 4.5 17 5.2 19.5 7 21.5 9.5 23c2 1.2 4 2.5 6 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        <path d="M17 4c4.5.5 7.5 2.5 9.2 5 1.6 2.5 2 5.5 1.3 8-.7 2.5-2.5 4.5-5 6-2 1.2-4 2.5-6 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        <line x1="16" y1="3.5" x2="16" y2="26.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        <path d="M5 12.5c3.5 0 7-.5 10-2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
        <path d="M5 18.5c3 0 6.5-.5 10-2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
        <path d="M27 12.5c-3.5 0-7-.5-10-2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
        <path d="M27 18.5c-3 0-6.5-.5-10-2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
      </svg>
    );
  }
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M11 3.5C7.5 4 5 6 4 8.5S3 13.5 4 16c1 2.5 3 4.5 5.5 5.5L11 22" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
      <path d="M13 3.5c3.5.5 6 2.5 7 5s1 5 0 7.5c-1 2.5-3 4.5-5.5 5.5L13 22" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
      <line x1="12" y1="3" x2="12" y2="22.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
      <path d="M4.5 11c2.5.5 4.5 0 7-1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M19.5 11c-2.5.5-4.5 0-7-1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

// ============================================================================
// Shared components
// ============================================================================
function BackToTop() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const fn = () => setShow(window.scrollY > 600);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);
  return (
    <AnimatePresence>
      {show && (
        <motion.button
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          transition={{ duration: 0.2 }}
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="fixed bottom-6 right-6 z-40 h-10 w-10 rounded-full bg-neutral-900 text-white shadow-[0_4px_12px_rgba(0,0,0,0.15)] flex items-center justify-center hover:bg-neutral-800 hover:shadow-[0_6px_20px_rgba(0,0,0,0.2)] transition-all"
          aria-label="Back to top"
        >
          <ChevronRight className="h-4 w-4 -rotate-90" />
        </motion.button>
      )}
    </AnimatePresence>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
      className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium text-white/40 hover:text-white/70 hover:bg-white/[0.06] transition-all"
    >
      {copied ? <><Check className="h-3 w-3 text-emerald-400" /> Copied</> : <><Copy className="h-3 w-3" /> Copy</>}
    </button>
  );
}

// ============================================================================
// NAV
// ============================================================================
function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  useEffect(() => {
    const fn = (e: KeyboardEvent) => { if (e.key === "Escape") setMobileOpen(false); };
    document.addEventListener("keydown", fn);
    return () => document.removeEventListener("keydown", fn);
  }, []);

  return (
    <>
      <motion.nav
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5, ease: EASE }}
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          scrolled ? "bg-white/80 backdrop-blur-2xl border-b border-neutral-200/50 shadow-[0_1px_3px_rgba(0,0,0,0.04)]" : "bg-transparent"
        }`}
      >
        <div className="max-w-[1200px] mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="h-7 w-7 rounded-lg bg-neutral-900 flex items-center justify-center group-hover:scale-105 transition-transform">
              <Brain className="h-4 w-4 text-white" />
            </div>
            <span className="font-semibold text-[15px] tracking-[-0.02em] text-neutral-900">Sulci</span>
          </Link>
          <div className="hidden md:flex items-center gap-0.5 text-[13px]">
            <Link href="/dashboard" className="px-3 py-1.5 rounded-md text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100/80 transition-all duration-150">Product</Link>
            <Link href="/documents" className="px-3 py-1.5 rounded-md text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100/80 transition-all duration-150">Docs</Link>
            <Link href="/settings/api-changelog" className="px-3 py-1.5 rounded-md text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100/80 transition-all duration-150">Changelog</Link>
            <Link href="/investors" className="px-3 py-1.5 rounded-md text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100/80 transition-all duration-150">Investors</Link>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/login" className="hidden md:block">
              <Button variant="ghost" size="sm" className="text-neutral-500 text-[13px] h-8 hover:text-neutral-900">Sign in</Button>
            </Link>
            <Link href="/dashboard" className="hidden md:block">
              <Button size="sm" className="bg-neutral-900 text-white hover:bg-neutral-800 text-[13px] rounded-lg h-8 px-3.5 shadow-sm">
                Try Demo <ArrowRight className="ml-1 h-3 w-3" />
              </Button>
            </Link>
            <button className="md:hidden p-1.5 rounded-lg hover:bg-neutral-100 transition-colors" onClick={() => setMobileOpen(!mobileOpen)}>
              {mobileOpen ? <X className="h-5 w-5 text-neutral-700" /> : <Menu className="h-5 w-5 text-neutral-700" />}
            </button>
          </div>
        </div>
      </motion.nav>

      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm md:hidden" onClick={() => setMobileOpen(false)} />
            <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.2, ease: EASE }} className="fixed top-16 left-0 right-0 z-50 md:hidden">
              <div className="mx-4 mt-2 rounded-2xl border border-neutral-200/80 bg-white/95 backdrop-blur-2xl shadow-[0_8px_40px_rgba(0,0,0,0.12)] p-4">
                <div className="space-y-1">
                  <Link href="/dashboard" onClick={() => setMobileOpen(false)} className="flex items-center px-3 py-2.5 rounded-lg text-[15px] font-medium text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900 transition-colors">Product</Link>
                  <Link href="/documents" onClick={() => setMobileOpen(false)} className="flex items-center px-3 py-2.5 rounded-lg text-[15px] font-medium text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900 transition-colors">Docs</Link>
                  <Link href="/settings/api-changelog" onClick={() => setMobileOpen(false)} className="flex items-center px-3 py-2.5 rounded-lg text-[15px] font-medium text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900 transition-colors">Changelog</Link>
                  <Link href="/investors" onClick={() => setMobileOpen(false)} className="flex items-center px-3 py-2.5 rounded-lg text-[15px] font-medium text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900 transition-colors">Investors</Link>
                </div>
                <div className="mt-3 pt-3 border-t border-neutral-100 space-y-2">
                  <Link href="/login" onClick={() => setMobileOpen(false)} className="block">
                    <Button variant="outline" className="w-full h-10 text-[14px] rounded-xl">Sign in</Button>
                  </Link>
                  <Link href="/dashboard" onClick={() => setMobileOpen(false)} className="block">
                    <Button className="w-full h-10 text-[14px] rounded-xl bg-neutral-900 text-white hover:bg-neutral-800">
                      Try Demo <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                    </Button>
                  </Link>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}

// ============================================================================
// HERO DEMO — animated product preview showing NLP pipeline
// ============================================================================
const DEMO_NOTE = `Assessment: 62 y/o male presents with acute exacerbation of CHF.
History of T2DM on metformin 1000mg BID, HTN controlled with lisinopril 20mg daily.
Patient denies chest pain. EF 35% on last echo. BNP elevated at 1,847 pg/mL.
Plan: IV furosemide 40mg, cardiology consult, repeat echo in AM.`;

const DEMO_CONCEPTS = [
  { text: "CHF", code: "SNOMED:42343007", category: "Condition", color: "text-rose-400", bg: "bg-rose-500/10", delay: 0.6 },
  { text: "T2DM", code: "OMOP:201826", category: "Condition", color: "text-amber-400", bg: "bg-amber-500/10", delay: 0.9 },
  { text: "metformin", code: "RxNorm:6809", category: "Drug", color: "text-blue-400", bg: "bg-blue-500/10", delay: 1.2 },
  { text: "HTN", code: "SNOMED:38341003", category: "Condition", color: "text-rose-400", bg: "bg-rose-500/10", delay: 1.4 },
  { text: "lisinopril", code: "RxNorm:29046", category: "Drug", color: "text-blue-400", bg: "bg-blue-500/10", delay: 1.6 },
  { text: "EF 35%", code: "LOINC:10230-1", category: "Observation", color: "text-emerald-400", bg: "bg-emerald-500/10", delay: 1.9 },
  { text: "BNP 1847", code: "LOINC:42637-9", category: "Lab", color: "text-violet-400", bg: "bg-violet-500/10", delay: 2.1 },
  { text: "furosemide", code: "RxNorm:4603", category: "Drug", color: "text-blue-400", bg: "bg-blue-500/10", delay: 2.4 },
];

function HeroDemoContent() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });

  return (
    <div ref={ref} className="grid md:grid-cols-2 gap-0 min-h-[320px]">
      <div className="p-5 border-r border-white/[0.06] overflow-hidden">
        <div className="flex items-center gap-2 mb-3">
          <FileText className="h-3.5 w-3.5 text-white/30" />
          <span className="text-[11px] text-white/30 font-mono">clinical_note_2847.txt</span>
          <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium">Processing</span>
        </div>
        <div className="font-mono text-[12px] leading-[1.8] text-white/50">
          {DEMO_NOTE.split(/(\b(?:CHF|T2DM|metformin|HTN|lisinopril|EF 35%|BNP|furosemide)\b)/gi).map((segment, i) => {
            const isHighlight = /^(CHF|T2DM|metformin|HTN|lisinopril|EF 35%|BNP|furosemide)$/i.test(segment);
            if (isHighlight) {
              const concept = DEMO_CONCEPTS.find(c => segment.toLowerCase().includes(c.text.toLowerCase().split(" ")[0]));
              return (
                <motion.span
                  key={i}
                  initial={{ backgroundColor: "rgba(99,102,241,0)" }}
                  animate={inView ? { backgroundColor: "rgba(99,102,241,0.2)" } : {}}
                  transition={{ delay: (concept?.delay ?? 1) + 0.2, duration: 0.4 }}
                  className="text-white/90 rounded px-0.5 -mx-0.5"
                >
                  {segment}
                </motion.span>
              );
            }
            return <span key={i}>{segment}</span>;
          })}
        </div>
      </div>

      <div className="p-5 overflow-hidden">
        <div className="flex items-center gap-2 mb-3">
          <Database className="h-3.5 w-3.5 text-white/30" />
          <span className="text-[11px] text-white/30 font-mono">extracted_concepts</span>
          <span className="ml-auto text-[10px] text-white/20 font-mono">{DEMO_CONCEPTS.length} found</span>
        </div>
        <div className="space-y-1.5">
          {DEMO_CONCEPTS.map((concept) => (
            <motion.div
              key={concept.text}
              initial={{ opacity: 0, x: 12 }}
              animate={inView ? { opacity: 1, x: 0 } : {}}
              transition={{ delay: concept.delay + 0.4, duration: 0.35, ease: EASE }}
              className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.04] hover:bg-white/[0.06] transition-colors"
            >
              <span className={`text-[10px] px-1.5 py-0.5 rounded ${concept.bg} ${concept.color} font-medium`}>
                {concept.category}
              </span>
              <span className="text-[12px] text-white/70 font-medium">{concept.text}</span>
              <span className="ml-auto text-[10px] text-white/25 font-mono">{concept.code}</span>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// HERO
// ============================================================================
function HeroSection() {
  const heroRef = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], [0, 100]);
  const opacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);

  return (
    <section ref={heroRef} className="relative pt-16 overflow-hidden">
      <motion.div style={{ y, opacity }} className="relative">
        <div className="max-w-[1200px] mx-auto px-6 pt-32 md:pt-44 pb-4">
          <motion.div variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } } }} initial="hidden" animate="visible" className="text-center">
            <motion.h1 variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } } }} className="text-[3.5rem] md:text-[5.5rem] lg:text-[7rem] font-semibold leading-[0.95] tracking-[-0.05em] text-neutral-900">
              Turn clinical notes<br />
              into <span className="bg-gradient-to-r from-indigo-600 via-violet-600 to-indigo-600 bg-clip-text text-transparent">knowledge.</span>
            </motion.h1>

            <motion.p variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } } }} className="mt-8 text-[18px] md:text-[22px] text-neutral-500 max-w-[600px] mx-auto leading-[1.55] tracking-[-0.01em]">
              80% of clinical data is trapped in unstructured text. Sulci extracts, normalizes, and connects it into knowledge your AI can reason over — in minutes, not months.
            </motion.p>

            <motion.div variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } } }} className="mt-10 flex items-center justify-center">
              <Link href="/dashboard">
                <Button className="group bg-neutral-900 text-white hover:bg-neutral-800 rounded-xl h-14 px-10 text-[16px] font-medium shadow-[0_1px_2px_rgba(0,0,0,0.1),0_4px_12px_rgba(0,0,0,0.06)] hover:shadow-[0_1px_2px_rgba(0,0,0,0.12),0_8px_24px_rgba(0,0,0,0.1)] transition-all duration-200">
                  Request a Demo <ArrowRight className="ml-1.5 h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
                </Button>
              </Link>
            </motion.div>

            <motion.div variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } } }} className="mt-8 flex items-center justify-center gap-3 flex-wrap">
              {[
                { value: "60x", label: "Faster Abstraction" },
                { value: "93.9%", label: "Concept Accuracy" },
                { value: "85%", label: "Signal Captured" },
                { value: "<50ms", label: "P95 Latency" },
              ].map((s) => (
                <span key={s.label} className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-neutral-200 bg-white text-[13px] text-neutral-500">
                  <span className="font-semibold text-neutral-900 tabular-nums">{s.value}</span> {s.label}
                </span>
              ))}
            </motion.div>
          </motion.div>
        </div>

        <motion.div initial={{ opacity: 0, y: 60, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.9, delay: 0.35, ease: EASE }} className="relative max-w-[1120px] mx-auto mt-16 md:mt-24 px-6">
          <div className="relative rounded-2xl border border-neutral-200/80 bg-neutral-950 shadow-[0_0_0_1px_rgba(0,0,0,0.03),0_2px_4px_rgba(0,0,0,0.04),0_12px_40px_rgba(0,0,0,0.12),0_24px_80px_rgba(0,0,0,0.08)] overflow-hidden ">
            <div className="flex items-center gap-2 px-4 py-3 bg-neutral-900/80 border-b border-white/[0.06]">
              <div className="flex gap-1.5">
                <div className="h-3 w-3 rounded-full bg-white/[0.08]" />
                <div className="h-3 w-3 rounded-full bg-white/[0.08]" />
                <div className="h-3 w-3 rounded-full bg-white/[0.08]" />
              </div>
              <div className="flex-1 flex justify-center">
                <div className="flex items-center gap-1.5 px-4 py-1 rounded-lg bg-white/[0.06] text-[11px] text-white/40 font-mono min-w-[200px] justify-center">
                  <Lock className="h-2.5 w-2.5 text-emerald-400/60" /> app.sulci.ai
                </div>
              </div>
              <div className="w-[52px]" />
            </div>
            <HeroDemoContent />
          </div>
          <div className="h-40 bg-gradient-to-t from-white via-white/80 to-transparent -mt-px relative z-10" />
        </motion.div>
      </motion.div>
    </section>
  );
}

// ============================================================================
// TRUST BAR
// ============================================================================
function TrustBar() {
  const orgs = ["HCA Healthcare", "Commure", "UCF Health", "Augmedix + Google"];
  return (
    <div className="py-16 md:py-20 border-y border-neutral-200">
      <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-6 text-center">Trusted by teams at</p>
      <div className="flex items-center justify-center gap-8 md:gap-14 flex-wrap px-6">
        {orgs.map((org) => (
          <span key={org} className="text-[16px] md:text-[18px] font-semibold tracking-[-0.02em] text-neutral-400">{org}</span>
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// PROBLEM + STATS — split layout with inline metrics
// ============================================================================
const problems = [
  { stat: "$13B", label: "lost annually to manual chart abstraction", detail: "Health systems spend billions on human abstractors reviewing notes for quality measures, risk adjustment, and research." },
  { stat: "72h", label: "average chart abstraction time", detail: "Manual review per patient for quality measures, research, and coding. At scale, this means months of delay per study." },
  { stat: "30%", label: "of clinical signal is never captured", detail: "Negation, temporality, and context lost in translation — each missed finding costs an average of $2,500 in downstream rework." },
];

function ProblemSection() {
  return (
    <section className="py-32 md:py-44 px-6 bg-neutral-50">
      <div className="max-w-[1200px] mx-auto">
        <div className="grid md:grid-cols-5 gap-8 md:gap-16">
          <div className="md:col-span-2">
            <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, ease: EASE }}>
              <p className="text-[11px] font-semibold tracking-[0.1em] uppercase text-neutral-400 mb-4">The problem</p>
              <h2 className="text-[2rem] md:text-[3rem] font-semibold tracking-[-0.035em] text-neutral-900 leading-[1.1]">
                Your smartest data is your dumbest asset.
              </h2>
              <p className="mt-5 text-[15px] text-neutral-500 leading-relaxed">
                LLMs can generate text. They can&apos;t reason over your clinical data without a knowledge backbone.
              </p>
            </motion.div>
          </div>
          <div className="md:col-span-3 space-y-3">
            {problems.map((p, i) => (
              <motion.div key={p.label} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.4, delay: i * 0.06, ease: EASE }}>
                <div className="rounded-xl border border-neutral-200 bg-white p-5">
                  <div className="flex items-baseline gap-4">
                    <div className="text-[2.5rem] md:text-[3rem] font-bold tracking-[-0.04em] text-neutral-900 flex-shrink-0 w-[90px] md:w-[110px]">{p.stat}</div>
                    <div>
                      <div className="text-[14px] font-semibold text-neutral-900 mb-1">{p.label}</div>
                      <p className="text-[13px] text-neutral-500 leading-relaxed">{p.detail}</p>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// CORE ENGINES
// ============================================================================
const engines = [
  { icon: Brain, iconBg: "bg-neutral-900", label: "Extract", title: "Clinical NLP",
    description: "Rule-based and transformer ensemble pipelines that extract clinical mentions from unstructured notes. Assertion, negation, temporality, and experiencer built in.",
    features: ["Named entity recognition for conditions, meds, procedures", "Assertion classification (present, absent, possible)", "Section-aware processing (HPI, Assessment, Plan)", "Temporal relationship extraction"] },
  { icon: Database, iconBg: "bg-neutral-900", label: "Normalize", title: "Ontology Mapping",
    description: "Map extracted concepts to UMLS, OMOP, and custom ontologies with candidate ranking, confidence scoring, and full provenance tracking across the entire UMLS Metathesaurus.",
    features: ["Full UMLS Metathesaurus (SNOMED, ICD-10, LOINC, RxNorm, MeSH...)", "OMOP CDM concept mapping with vocabulary versioning", "Ranked candidates with confidence scores", "Custom ontology support for institution-specific codes"] },
  { icon: GitBranch, iconBg: "bg-neutral-900", label: "Connect", title: "Knowledge Graph",
    description: "Build queryable patient knowledge graphs from normalized facts. Temporal relationships, drug-condition links, and lab trajectories — all connected and traversable.",
    features: ["Patient-centric graph with clinical edges", "Drug-condition and drug-drug interactions", "GraphRAG natural language querying", "Neo4j persistence + in-memory projection"] },
];

function CoreEngines() {
  return (
    <section className="py-32 md:py-44 px-6">
      <div className="max-w-[1200px] mx-auto">
        <div className="text-center mb-20">
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-4">Core Engines</p>
          <h2 className="text-[2rem] md:text-[3.25rem] font-semibold tracking-[-0.04em] text-neutral-900 leading-[1.05]">Three engines. One pipeline.</h2>
          <p className="mt-5 text-neutral-500 max-w-lg mx-auto text-[16px] leading-relaxed">
            From raw clinical text to a queryable knowledge graph in three steps.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-5">
          {engines.map((engine, i) => {
            const Icon = engine.icon;
            return (
              <motion.div key={engine.title} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, delay: i * 0.08, ease: EASE }}>
                <div className="relative h-full rounded-2xl border border-neutral-200 bg-white p-7 transition-all duration-300 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)]">
                  <div className="flex items-center gap-3 mb-6">
                    <div className={`h-10 w-10 rounded-xl flex items-center justify-center ${engine.iconBg}`}>
                      <Icon className="h-4.5 w-4.5 text-white" />
                    </div>
                    <span className="text-[11px] font-semibold tracking-[0.1em] uppercase text-neutral-400">{engine.label}</span>
                  </div>
                  <h3 className="font-semibold text-[18px] tracking-[-0.02em] text-neutral-900 mb-3">{engine.title}</h3>
                  <p className="text-[14px] text-neutral-500 leading-[1.6] mb-6">{engine.description}</p>
                  <div className="space-y-2.5 pt-5 border-t border-neutral-100">
                    {engine.features.map((f) => (
                      <div key={f} className="flex items-start gap-2.5">
                        <CheckCircle2 className="h-3.5 w-3.5 text-neutral-300 mt-0.5 flex-shrink-0" />
                        <span className="text-[13px] text-neutral-500 leading-snug">{f}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// DATA TRANSFORMATION
// ============================================================================
function DataTransformation() {
  return (
    <section className="py-32 md:py-44 px-6 bg-neutral-50">
      <div className="max-w-[1200px] mx-auto">
        <div className="mb-16">
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-4">How it works</p>
          <h2 className="text-[2rem] md:text-[3rem] font-semibold tracking-[-0.04em] text-neutral-900 leading-[1.05]">See the transformation</h2>
          <p className="mt-4 text-neutral-500 max-w-lg text-[16px] leading-relaxed">
            From a messy clinical note to structured, ontology-mapped clinical facts — in one API call.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-4 max-w-[900px] relative">
          <div className="hidden md:flex absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10">
            <div className="h-10 w-10 rounded-full bg-white border border-neutral-200 shadow-[0_2px_8px_rgba(0,0,0,0.06)] flex items-center justify-center">
              <ArrowRight className="h-4 w-4 text-indigo-500" />
            </div>
          </div>
          <motion.div initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={VIEWPORT} transition={{ duration: 0.6, ease: EASE }}>
            <div className="rounded-2xl border border-neutral-200/80 bg-white overflow-hidden shadow-[0_1px_3px_rgba(0,0,0,0.04)] hover:shadow-[0_4px_20px_rgba(0,0,0,0.06)] transition-shadow duration-300">
              <div className="px-4 py-2.5 border-b border-neutral-100 flex items-center gap-2">
                <div className="h-5 w-5 rounded-md bg-amber-50 flex items-center justify-center"><FileText className="h-3 w-3 text-amber-500" /></div>
                <span className="text-[12px] font-semibold text-neutral-500">Input</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 font-medium ml-auto">Raw Clinical Note</span>
              </div>
              <div className="p-5 font-mono text-[12px] leading-[1.8] text-neutral-600">
                <p>Pt is a 62yo M with <span className="bg-rose-50 text-rose-600 px-1 py-0.5 rounded-sm font-medium">hx of T2DM</span>, <span className="bg-blue-50 text-blue-600 px-1 py-0.5 rounded-sm font-medium">HTN</span>, and <span className="bg-violet-50 text-violet-600 px-1 py-0.5 rounded-sm font-medium">CKD stage 3</span>. Currently on <span className="bg-emerald-50 text-emerald-600 px-1 py-0.5 rounded-sm font-medium">metformin 1000mg BID</span> and <span className="bg-emerald-50 text-emerald-600 px-1 py-0.5 rounded-sm font-medium">lisinopril 20mg daily</span>. <span className="bg-amber-50 text-amber-600 px-1 py-0.5 rounded-sm font-medium">A1c 8.2%</span> on last check. <span className="bg-neutral-100 text-neutral-500 px-1 py-0.5 rounded-sm">No chest pain</span>.</p>
              </div>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={VIEWPORT} transition={{ duration: 0.6, delay: 0.1, ease: EASE }}>
            <div className="rounded-2xl border border-neutral-200/80 bg-white overflow-hidden shadow-[0_1px_3px_rgba(0,0,0,0.04)] hover:shadow-[0_4px_20px_rgba(0,0,0,0.06)] transition-shadow duration-300">
              <div className="px-4 py-2.5 border-b border-neutral-100 flex items-center gap-2">
                <div className="h-5 w-5 rounded-md bg-emerald-50 flex items-center justify-center"><Database className="h-3 w-3 text-emerald-500" /></div>
                <span className="text-[12px] font-semibold text-neutral-500">Output</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-600 font-medium ml-auto">Normalized Clinical Facts</span>
              </div>
              <div className="p-4 font-mono text-[11.5px] leading-[1.7] space-y-1.5">
                {[
                  { tag: "COND", color: "text-rose-500 bg-rose-50", name: "Type 2 diabetes mellitus", id: "C0011860" },
                  { tag: "COND", color: "text-blue-500 bg-blue-50", name: "Essential hypertension", id: "C0085580" },
                  { tag: "COND", color: "text-violet-500 bg-violet-50", name: "Chronic kidney disease, stg 3", id: "C2316810" },
                  { tag: "DRUG", color: "text-emerald-500 bg-emerald-50", name: "metformin 1000 MG Oral", id: "C0987664" },
                  { tag: "DRUG", color: "text-emerald-500 bg-emerald-50", name: "lisinopril 20 MG Oral", id: "C0689142" },
                  { tag: "MEAS", color: "text-amber-500 bg-amber-50", name: "HbA1c 8.2%", id: "C0474748" },
                  { tag: "COND", color: "text-neutral-400 bg-neutral-50", name: "Chest pain", id: "C0008031", negated: true },
                ].map((row) => (
                  <div key={row.id} className="flex items-center gap-2 py-0.5">
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${row.color}`}>{row.tag}</span>
                    <span className={`flex-1 truncate ${("negated" in row && row.negated) ? "text-neutral-400 line-through decoration-neutral-300" : "text-neutral-800"}`}>{row.name}</span>
                    {"negated" in row && row.negated && <span className="text-[8px] font-bold px-1 py-0.5 rounded bg-neutral-100 text-neutral-400 uppercase tracking-wider">neg</span>}
                    <span className="text-neutral-300 text-[10px] tabular-nums font-mono">{row.id}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// API SHOWCASE — dark section
// ============================================================================
const codeExamples: Record<string, { label: string; code: string }> = {
  python: { label: "Python", code: `import sulci\n\nclient = sulci.Client(api_key="sk_live_...")\n\n# Run the full extraction pipeline\nresult = client.pipeline.run(\n    input="Pt is a 62yo M with hx of T2DM, HTN.",\n    ontologies=["umls", "omop", "snomed"],\n    include_graph=True\n)\n\nfor fact in result.facts:\n    print(f"{fact.cui}: {fact.concept_name}")` },
  typescript: { label: "TypeScript", code: `import { Sulci } from "@sulci/sdk";\n\nconst client = new Sulci({ apiKey: "sk_live_..." });\n\n// Run the full extraction pipeline\nconst result = await client.pipeline.run({\n  input: "Pt is a 62yo M with hx of T2DM, HTN.",\n  ontologies: ["umls", "omop", "snomed"],\n  includeGraph: true,\n});\n\nfor (const fact of result.facts) {\n  console.log(\`\${fact.cui}: \${fact.conceptName}\`);\n}` },
  curl: { label: "cURL", code: `curl -X POST https://api.sulci.ai/v1/pipeline \\
  -H "Authorization: Bearer sk_live_..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "input": "Pt is a 62yo M with hx of T2DM.",
    "ontologies": ["umls", "omop", "snomed"],
    "include_graph": true
  }'` },
};

function HighlightedCode({ code }: { code: string }) {
  return (
    <pre className="font-mono text-[12px] md:text-[12.5px] leading-[1.75] whitespace-pre">
      {code.split("\n").map((line, i) => (
        <div key={i} className="flex">
          <span className="text-white/10 w-8 text-right mr-4 select-none text-[11px]">{i + 1}</span>
          <span>{/^(#|\/\/)/.test(line.trim()) ? <span className="text-neutral-500 italic">{line}</span> : line.split(/(import |from |const |await |for |async |"[^"]*"|'[^']*'|`[^`]*`|\btrue\b|\bfalse\b|\bTrue\b|\bFalse\b)/g).map((t, j) =>
            !t ? null : /^(import|from|const|await|for|async)\s?$/.test(t) ? <span key={j} className="text-violet-400">{t}</span> : /^(true|false|True|False)$/.test(t) ? <span key={j} className="text-amber-400">{t}</span> : /^["'`]/.test(t) ? <span key={j} className="text-emerald-400">{t}</span> : <span key={j} className="text-white/80">{t}</span>
          )}</span>
        </div>
      ))}
    </pre>
  );
}

function APIShowcase() {
  const [tab, setTab] = useState("python");
  return (
    <section className="py-32 md:py-44 relative overflow-hidden bg-neutral-950">
      <div className="max-w-[1200px] mx-auto px-6">
        <div className="grid md:grid-cols-2 gap-12 md:gap-16 items-center">
          <div>
            <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-500 mb-4">Developer Experience</p>
            <h2 className="text-[1.75rem] md:text-[2.75rem] font-semibold tracking-[-0.04em] text-white leading-[1.05]">
              Ship in minutes,<br /><span className="text-indigo-400">not months.</span>
            </h2>
            <p className="mt-4 text-neutral-400 text-[15.5px] leading-relaxed max-w-[420px]">
              First-class SDKs for Python and TypeScript. Extract clinical concepts, map to UMLS and OMOP ontologies, and query your knowledge graph with a single API call.
            </p>
            <div className="mt-8 space-y-3">
              {[{ icon: Zap, text: "One-line pipeline execution" }, { icon: Shield, text: "Built-in PHI de-identification" }, { icon: Activity, text: "Real-time streaming support" }, { icon: Globe, text: "99.99% uptime SLA" }].map(({ icon: Icon, text }) => (
                <div key={text} className="flex items-center gap-3">
                  <div className="h-7 w-7 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center">
                    <Icon className="h-3.5 w-3.5 text-neutral-500" />
                  </div>
                  <span className="text-[14px] text-neutral-300">{text}</span>
                </div>
              ))}
            </div>
            <div className="mt-8">
              <Link href="/dashboard" className="inline-flex items-center gap-1.5 text-[14px] font-medium text-neutral-400 hover:text-white transition-colors">
                Read the API docs <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            <div className="mt-8 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 mb-2.5">
                <div className="h-2 w-2 rounded-full bg-emerald-400" />
                <span className="text-[11px] font-mono text-white/30">200 OK &middot; 47ms</span>
              </div>
              <div className="font-mono text-[11px] leading-[1.7] text-white/40 space-y-0.5">
                <div>{`{`}</div>
                <div className="pl-4"><span className="text-violet-400">&quot;facts&quot;</span>: [</div>
                <div className="pl-8">{`{ `}<span className="text-emerald-400">&quot;cui&quot;</span>: <span className="text-amber-400">&quot;C0011860&quot;</span>, <span className="text-emerald-400">&quot;name&quot;</span>: <span className="text-amber-400">&quot;T2DM&quot;</span>, <span className="text-emerald-400">&quot;confidence&quot;</span>: <span className="text-white/60">0.97</span> {`}`}</div>
                <div className="pl-8">{`{ `}<span className="text-emerald-400">&quot;cui&quot;</span>: <span className="text-amber-400">&quot;C0085580&quot;</span>, <span className="text-emerald-400">&quot;name&quot;</span>: <span className="text-amber-400">&quot;HTN&quot;</span>, <span className="text-emerald-400">&quot;confidence&quot;</span>: <span className="text-white/60">0.95</span> {`}`}</div>
                <div className="pl-4">],</div>
                <div className="pl-4"><span className="text-violet-400">&quot;graph_nodes&quot;</span>: <span className="text-white/60">8</span>, <span className="text-violet-400">&quot;graph_edges&quot;</span>: <span className="text-white/60">10</span></div>
                <div>{`}`}</div>
              </div>
            </div>
          </div>

          <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.6, ease: EASE }}>
            <div className="rounded-2xl border border-white/[0.06] bg-[#0A0A0B] shadow-[0_12px_40px_rgba(0,0,0,0.4)] overflow-hidden">
              <div className="flex items-center gap-0 px-4 py-2.5 border-b border-white/[0.06]">
                {Object.entries(codeExamples).map(([k, { label }]) => (
                  <button key={k} onClick={() => setTab(k)} className={`px-3 py-1 rounded-md text-[12px] font-medium transition-all ${tab === k ? "bg-white/[0.08] text-white/90" : "text-white/30 hover:text-white/50"}`}>{label}</button>
                ))}
                <div className="ml-auto flex items-center gap-3">
                  <CopyButton text={codeExamples[tab].code} />
                  <div className="flex items-center gap-1.5">
                    <div className="h-2 w-2 rounded-full bg-emerald-400/60" />
                    <span className="text-[10px] text-white/20 font-mono">v1.4.2</span>
                  </div>
                </div>
              </div>
              <div className="p-5 md:p-6 overflow-x-auto">
                <AnimatePresence mode="wait">
                  <motion.div key={tab} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.15 }}>
                    <HighlightedCode code={codeExamples[tab].code} />
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// PLATFORM BENTO
// ============================================================================
function PlatformBento() {
  const cards = [
    { icon: HeartPulse, title: "FHIR R4 Interoperability", description: "Import and export complete patient records as FHIR R4 Bundles. Conditions, medications, observations, and procedures mapped automatically.", size: "md:col-span-2", resources: ["Conditions", "Medications", "Observations", "Procedures", "Allergies", "Immunizations"] },
    { icon: FlaskConical, title: "Clinical Trials", description: "Automated eligibility screening. Cohort matching against I/E criteria with patient ranking.", size: "md:col-span-1" },
    { icon: Shield, title: "Drug Safety", description: "Adverse event detection, pharmacovigilance signals, and drug interaction checking.", size: "md:col-span-1" },
    { icon: BarChart3, title: "Billing & Coding", description: "ICD-10, CPT, DRG code suggestion from clinical facts. Automated coding validation.", size: "md:col-span-1" },
    { icon: Pill, title: "Medications & Dosing", description: "RxNorm mapping with interaction checking and clinical calculator integration.", size: "md:col-span-1" },
  ];

  return (
    <section className="py-32 md:py-44 px-6 bg-neutral-50">
      <div className="max-w-[1200px] mx-auto">
        <div className="text-center mb-20">
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-4">Platform</p>
          <h2 className="text-[2rem] md:text-[3.25rem] font-semibold tracking-[-0.04em] text-neutral-900 leading-[1.05]">Built for the full clinical stack</h2>
          <p className="mt-5 text-neutral-500 max-w-lg mx-auto text-[16px] leading-relaxed">
            From ingestion to interoperability — every layer of clinical data processing in one platform.
          </p>
        </div>
        <div className="grid md:grid-cols-3 gap-5">
          {cards.map((card, i) => {
            const Icon = card.icon;
            return (
              <motion.div key={card.title} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, delay: i * 0.06, ease: EASE }} className={card.size}>
                <div className="h-full rounded-2xl border border-neutral-200 bg-white p-7 transition-all duration-300 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)]">
                  <div className="h-10 w-10 rounded-xl flex items-center justify-center bg-neutral-100 mb-5"><Icon className="h-5 w-5 text-neutral-600" /></div>
                  <h3 className="font-semibold text-[16px] tracking-[-0.01em] text-neutral-900 mb-2">{card.title}</h3>
                  <p className="text-[14px] text-neutral-500 leading-relaxed">{card.description}</p>
                  {card.resources && (
                    <div className="mt-5 flex flex-wrap gap-1.5">
                      {card.resources.map((r) => (
                        <span key={r} className="px-2.5 py-1 text-[11px] font-medium rounded-md bg-neutral-50 text-neutral-500 border border-neutral-100">{r}</span>
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// TESTIMONIALS — featured + 2 smaller
// ============================================================================
const testimonials = [
  { quote: "Sulci cut our chart abstraction pipeline from 6 weeks to under an hour — a 97% reduction. The concept mapping accuracy benchmarks at 94.2%, which rivals our senior informaticists.", author: "Dr. Sarah Chen", role: "Chief Medical Informatics Officer", org: "Pacific Health System", metric: "97% time reduction" },
  { quote: "We evaluated every CDM tool on the market. Sulci was the only one that handled assertion detection and negation correctly out of the box. That saved us $2.1M in year one.", author: "James Okafor", role: "VP of Data Engineering", org: "Meridian Clinical Analytics", metric: "$2.1M saved in Y1" },
  { quote: "The knowledge graph changed our pharmacovigilance entirely. Drug-condition signals that took our team days now surface in real-time. We caught 3x more safety signals last quarter.", author: "Dr. Lisa Patel", role: "Head of Drug Safety", org: "Vertex Therapeutics", metric: "3x safety signals" },
];

function TestimonialsSection() {
  const featured = testimonials[0];
  const rest = testimonials.slice(1);

  return (
    <section className="py-32 md:py-44 px-6">
      <div className="max-w-[1200px] mx-auto">
        <div className="mb-16">
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-4">What teams say</p>
          <h2 className="text-[2rem] md:text-[3rem] font-semibold tracking-[-0.035em] text-neutral-900 leading-[1.1]">Trusted by clinical data teams</h2>
        </div>

        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, ease: EASE }} className="mb-5">
          <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-10 md:p-16">
            <p className="text-[22px] md:text-[32px] font-light text-neutral-700 leading-[1.45] tracking-[-0.02em] max-w-[800px]">&ldquo;{featured.quote}&rdquo;</p>
            <div className="mt-8 flex items-center gap-4">
              <div className="h-11 w-11 rounded-full bg-neutral-200 flex items-center justify-center">
                <span className="text-[13px] font-bold text-neutral-600">{featured.author.split(" ").map(n => n[0]).join("")}</span>
              </div>
              <div>
                <p className="text-[14px] font-semibold text-neutral-900">{featured.author}</p>
                <p className="text-[13px] text-neutral-500">{featured.role} &middot; {featured.org}</p>
              </div>
              <span className="ml-auto hidden md:block text-[12px] font-semibold px-3 py-1 rounded-full bg-neutral-200/60 text-neutral-600">{featured.metric}</span>
            </div>
          </div>
        </motion.div>

        <div className="grid md:grid-cols-2 gap-5">
          {rest.map((t, i) => (
            <motion.div key={t.author} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, delay: i * 0.08, ease: EASE }}>
              <div className="h-full rounded-2xl border border-neutral-200 bg-neutral-50 p-7">
                <p className="text-[15px] text-neutral-600 leading-[1.75]">&ldquo;{t.quote}&rdquo;</p>
                <div className="pt-5 mt-5 border-t border-neutral-200 flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-neutral-200 flex items-center justify-center">
                    <span className="text-[11px] font-bold text-neutral-600">{t.author.split(" ").map(n => n[0]).join("")}</span>
                  </div>
                  <div>
                    <p className="text-[13px] font-semibold text-neutral-900">{t.author}</p>
                    <p className="text-[12px] text-neutral-500">{t.role} &middot; {t.org}</p>
                  </div>
                  <span className="ml-auto text-[11px] font-semibold px-2.5 py-1 rounded-full bg-neutral-200/60 text-neutral-600">{t.metric}</span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// STANDARDS & COMPLIANCE — merged
// ============================================================================
const vocabs = ["UMLS Metathesaurus", "OMOP CDM v5.4", "FHIR R4", "SNOMED CT", "ICD-10-CM", "LOINC", "RxNorm", "MeSH", "CPT", "NDC", "CDS Hooks", "SMART on FHIR"];

function StandardsAndCompliance() {
  return (
    <section className="py-24 md:py-32 px-6 bg-neutral-50">
      <div className="max-w-[1200px] mx-auto">
        <div className="grid md:grid-cols-2 gap-12 md:gap-20">
          <div>
            <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-4">Standards</p>
            <h3 className="text-[1.5rem] md:text-[2rem] font-semibold tracking-[-0.02em] text-neutral-900 mb-3">Full UMLS Metathesaurus and beyond.</h3>
            <p className="text-[14px] text-neutral-500 leading-relaxed mb-6">
              Native support for the entire UMLS Metathesaurus, OMOP CDM, and custom ontologies. Over 200 source vocabularies, zero custom adapters.
            </p>
            <div className="flex flex-wrap gap-2">
              {vocabs.map((v) => (
                <span key={v} className="px-3 py-1.5 text-[12px] rounded-lg bg-white text-neutral-600 border border-neutral-200/80 font-mono font-medium shadow-[0_1px_2px_rgba(0,0,0,0.03)] hover:border-neutral-300 transition-colors">{v}</span>
              ))}
            </div>
          </div>
          <div>
            <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-4">Security &amp; Compliance</p>
            <h3 className="text-[1.5rem] md:text-[2rem] font-semibold tracking-[-0.02em] text-neutral-900 mb-3">Enterprise-grade from day one.</h3>
            <p className="text-[14px] text-neutral-500 leading-relaxed mb-6">
              Built for regulated environments. Every action logged, every record encrypted, every access controlled.
            </p>
            <div className="grid grid-cols-2 gap-3">
              {[
                { icon: Shield, label: "HIPAA", desc: "End-to-end encryption" },
                { icon: Lock, label: "SOC 2 Type II", desc: "Audited controls" },
                { icon: FileText, label: "BAA", desc: "Available on all plans" },
                { icon: Activity, label: "FHIR R4", desc: "Certified interop" },
                { icon: Database, label: "OMOP CDM v5.4", desc: "Standard data model" },
                { icon: CheckCircle2, label: "21 CFR Part 11", desc: "Electronic records" },
              ].map(({ icon: Icon, label, desc }) => (
                <div key={label} className="rounded-xl p-3.5 bg-white border border-neutral-200/80 shadow-[0_1px_2px_rgba(0,0,0,0.03)] hover:border-neutral-300 hover:shadow-[0_4px_12px_rgba(0,0,0,0.04)] transition-all">
                  <div className="flex items-center gap-2 mb-1"><Icon className="h-3.5 w-3.5 text-neutral-400" /><span className="text-[13px] font-semibold text-neutral-900">{label}</span></div>
                  <p className="text-[11px] text-neutral-400 ml-[22px]">{desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// INTEGRATIONS — static 4x2 grid
// ============================================================================
function IntegrationsSection() {
  const integrations = [
    { icon: HeartPulse, label: "Epic" },
    { icon: Database, label: "Cerner" },
    { icon: Globe, label: "Carequality" },
    { icon: Network, label: "CommonWell" },
    { icon: Layers, label: "Veeva Vault" },
    { icon: Binary, label: "Databricks" },
    { icon: Workflow, label: "Redox" },
    { icon: Cpu, label: "Health Gorilla" },
  ];

  return (
    <section className="py-20 md:py-28 px-6">
      <div className="max-w-[800px] mx-auto">
        <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-8 text-center">Connects to your existing infrastructure</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {integrations.map(({ icon: Icon, label }) => (
            <div key={label} className="flex items-center gap-2.5 px-5 py-3 rounded-xl bg-white border border-neutral-200/80 shadow-[0_1px_2px_rgba(0,0,0,0.03)] hover:border-neutral-300 transition-colors">
              <Icon className="h-4 w-4 text-neutral-400" />
              <span className="text-[13px] font-medium text-neutral-600">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// FOUNDER
// ============================================================================
const career = [
  { org: "Commure", role: "Clinical AI Architect", detail: "Agentic ambient scribing at ~1% of U.S. visits" },
  { org: "HCA Healthcare", role: "Enterprise SME, Clinical Documentation", detail: "Meditech Expanse rollout — millions of ED visits" },
  { org: "Lake Monroe Hospital", role: "Vice Chair of the Board", detail: "" },
  { org: "UCF", role: "Asst. Professor, Emergency Medicine", detail: "" },
];

function FounderSection() {
  return (
    <section className="py-32 md:py-44 px-6 bg-neutral-50">
      <div className="max-w-[1200px] mx-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, ease: EASE }} className="text-center mb-20">
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-4">Founder</p>
          <h2 className="text-[2rem] md:text-[3.25rem] font-semibold tracking-[-0.04em] text-neutral-900 leading-[1.05]">Built by a physician who ships.</h2>
        </motion.div>
        <div className="grid md:grid-cols-2 gap-10 md:gap-16 items-center">
          <motion.div initial={{ opacity: 0, x: -30 }} whileInView={{ opacity: 1, x: 0 }} viewport={VIEWPORT} transition={{ duration: 0.6, ease: EASE }} className="relative">
            <div className="relative rounded-2xl overflow-hidden shadow-[0_20px_60px_rgba(0,0,0,0.12)] border border-neutral-200/60">
              <img src="/alex-er.jpg" alt="Alex Stinard, M.D. in the emergency department" className="w-full h-auto object-cover" />
            </div>
            <div className="absolute -bottom-6 -right-4 md:-right-8 w-[140px] md:w-[160px] rounded-xl overflow-hidden shadow-[0_12px_40px_rgba(0,0,0,0.15)] border-[3px] border-white ring-1 ring-neutral-200/40">
              <img src="/alex-headshot.jpg" alt="Alex Stinard, M.D. headshot" className="w-full h-auto object-cover" />
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, x: 30 }} whileInView={{ opacity: 1, x: 0 }} viewport={VIEWPORT} transition={{ duration: 0.6, delay: 0.1, ease: EASE }}>
            <h3 className="text-[1.5rem] md:text-[1.75rem] font-semibold tracking-[-0.02em] text-neutral-900 mb-1">Alex Stinard, M.D.</h3>
            <p className="text-[13px] font-medium text-neutral-500 mb-5">Founder &amp; CEO</p>

            <div className="relative pl-4 border-l-2 border-neutral-300 mb-6">
              <p className="text-[15px] text-neutral-700 leading-[1.7] italic">&ldquo;Unstructured notes are a smooth brain. I&apos;ve spent 20 years watching clinical signal get lost in free text. Sulci adds the folds.&rdquo;</p>
            </div>

            <div className="space-y-3 text-[14px] text-neutral-600 leading-[1.75]">
              <p>Emergency physician executive and clinical AI architect. At Commure, designs and governs agentic ambient scribing at national scale — multi-agent orchestration with knowledge-graph memory, ontology-aware prompting, and deterministic EHR tool use.</p>
              <p>Enterprise SME for clinical documentation at HCA Healthcare. Led the Meditech Expanse rollout affecting millions of ED visits. Vice Chair of the Board at Lake Monroe Hospital. Assistant Professor of Emergency Medicine at UCF.</p>
            </div>

            <div className="mt-6 space-y-2">
              {career.map((c, i) => (
                <motion.div key={c.org} initial={{ opacity: 0, x: 12 }} whileInView={{ opacity: 1, x: 0 }} viewport={VIEWPORT} transition={{ duration: 0.3, delay: 0.2 + i * 0.06, ease: EASE }} className="flex items-center gap-3 group">
                  <div className="h-2 w-2 rounded-full bg-neutral-400 flex-shrink-0 group-hover:scale-125 transition-transform" />
                  <div className="flex items-baseline gap-2 min-w-0">
                    <span className="text-[13px] font-semibold text-neutral-900 flex-shrink-0">{c.org}</span>
                    <span className="text-[12px] text-neutral-400 truncate">{c.role}</span>
                  </div>
                </motion.div>
              ))}
            </div>

            <div className="mt-6 flex flex-wrap gap-2">
              {["Multi-Agent Systems", "Knowledge Graphs", "Ontology Design", "FHIR/HL7", "Safety & Red-Teaming", "CDI/DRG"].map((tag) => (
                <span key={tag} className="px-2.5 py-1 text-[11px] font-medium rounded-lg bg-neutral-100 text-neutral-600 border border-neutral-200">{tag}</span>
              ))}
            </div>

            <div className="mt-5 flex items-center gap-2.5">
              {[
                { label: "LinkedIn", href: "#" },
                { label: "GitHub", href: "#" },
                { label: "X", href: "#" },
              ].map(({ label, href }) => (
                <a key={label} href={href} className="h-8 px-3 flex items-center justify-center text-[11px] font-medium rounded-lg text-neutral-400 border border-neutral-200/80 hover:text-neutral-600 hover:border-neutral-300 hover:shadow-[0_2px_8px_rgba(0,0,0,0.04)] transition-all">
                  {label} <ExternalLink className="ml-1.5 h-2.5 w-2.5" />
                </a>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// PRICING
// ============================================================================
const plans = [
  {
    name: "Starter",
    price: "Free",
    period: "",
    description: "For exploration and prototyping.",
    features: ["1,000 documents/month", "NLP extraction + UMLS mapping", "REST API access", "Community support", "Single user"],
    cta: "Start Free",
    highlight: false,
  },
  {
    name: "Pro",
    price: "$499",
    period: "/mo",
    description: "For teams building production pipelines.",
    features: ["25,000 documents/month", "Full OMOP CDM + custom ontologies", "Knowledge graph + GraphRAG", "FHIR R4 import/export", "Priority support", "Up to 10 users", "SSO + audit logs"],
    cta: "Start Trial",
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "For health systems and regulated environments.",
    features: ["Unlimited documents", "On-prem / VPC deployment", "Custom ontology development", "Dedicated success engineer", "BAA + 21 CFR Part 11", "SLA 99.99% uptime", "TEFCA + bulk export"],
    cta: "Contact Sales",
    highlight: false,
  },
];

function PricingSection() {
  return (
    <section className="py-32 md:py-44 px-6">
      <div className="max-w-[1200px] mx-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, ease: EASE }} className="text-center mb-20">
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-4">Pricing</p>
          <h2 className="text-[2rem] md:text-[3.25rem] font-semibold tracking-[-0.04em] text-neutral-900 leading-[1.05]">Simple, predictable pricing</h2>
          <p className="mt-5 text-neutral-500 max-w-lg mx-auto text-[16px] leading-relaxed">
            Start free. Scale when you&apos;re ready. No surprises.
          </p>
        </motion.div>
        <div className="grid md:grid-cols-3 gap-5 max-w-[960px] mx-auto">
          {plans.map((plan, i) => (
            <motion.div key={plan.name} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, delay: i * 0.08, ease: EASE }}>
              <div className={`relative h-full rounded-2xl border p-7 transition-all duration-300 ${
                plan.highlight
                  ? "border-neutral-900 bg-white shadow-[0_8px_30px_rgba(0,0,0,0.08)]"
                  : "border-neutral-200 bg-white hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)]"
              }`}>
                {plan.highlight && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="px-3 py-1 rounded-full bg-indigo-600 text-white text-[11px] font-semibold">Most Popular</span>
                  </div>
                )}
                <div className="mb-4">
                  <h3 className="text-[16px] font-semibold text-neutral-900 mb-1">{plan.name}</h3>
                  <p className="text-[12.5px] text-neutral-400">{plan.description}</p>
                </div>
                <div className="flex items-baseline gap-1 mb-6">
                  <span className="text-[2.5rem] font-bold tracking-[-0.04em] text-neutral-900">{plan.price}</span>
                  {plan.period && <span className="text-[14px] text-neutral-400">{plan.period}</span>}
                </div>
                <Link href="/dashboard">
                  <Button className={`w-full rounded-xl h-10 text-[13px] font-medium transition-all ${
                    plan.highlight
                      ? "bg-neutral-900 text-white hover:bg-neutral-800 shadow-sm"
                      : "bg-white text-neutral-700 border border-neutral-200 hover:bg-neutral-50 hover:border-neutral-300"
                  }`}>
                    {plan.cta} <ArrowRight className="ml-1.5 h-3 w-3" />
                  </Button>
                </Link>
                <div className="mt-6 pt-5 border-t border-neutral-100 space-y-2.5">
                  {plan.features.map((f) => (
                    <div key={f} className="flex items-start gap-2.5">
                      <CheckCircle2 className={`h-3.5 w-3.5 mt-0.5 flex-shrink-0 ${plan.highlight ? "text-neutral-900" : "text-neutral-300"}`} />
                      <span className="text-[13px] text-neutral-600 leading-snug">{f}</span>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// CTA
// ============================================================================
function CTASection() {
  return (
    <section className="py-32 md:py-44 px-6 bg-neutral-50">
      <div className="max-w-[800px] mx-auto text-center">
        <h2 className="text-[2rem] md:text-[3.25rem] font-semibold tracking-[-0.04em] text-neutral-900 leading-[1.05]">Ready to turn clinical notes into knowledge?</h2>
        <p className="mt-5 text-neutral-500 max-w-md mx-auto text-[16px] leading-relaxed">Stop leaving clinical signal trapped in free text. See how Sulci can transform your data pipeline in a 30-minute walkthrough.</p>
        <div className="mt-10 flex items-center justify-center">
          <Link href="/dashboard">
            <Button className="group bg-neutral-900 text-white hover:bg-neutral-800 rounded-xl h-14 px-10 text-[16px] font-medium shadow-[0_1px_2px_rgba(0,0,0,0.1),0_4px_12px_rgba(0,0,0,0.06)] hover:shadow-[0_1px_2px_rgba(0,0,0,0.12),0_8px_24px_rgba(0,0,0,0.1)] transition-all">
              Request a Demo <ArrowRight className="ml-1.5 h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
            </Button>
          </Link>
        </div>
        <p className="mt-5 text-[13px] text-neutral-400">HIPAA compliant. SOC 2 Type II. BAA available.</p>
      </div>
    </section>
  );
}

// ============================================================================
// FOOTER
// ============================================================================
function FooterSection() {
  const links = {
    Product: ["NLP Engine", "Ontology Mapping", "Knowledge Graph", "FHIR Import/Export", "Clinical Trials", "API Reference"],
    Resources: ["Documentation", "Quickstart Guide", "API Status", "Changelog", "Blog"],
    Company: ["About", "Careers", "Security", "Privacy Policy", "Terms of Service"],
  };
  return (
    <footer className="border-t border-neutral-200">
      <div className="max-w-[1200px] mx-auto px-6 py-16 md:py-20">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-8">
          <div className="col-span-2 md:col-span-3">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="h-7 w-7 rounded-lg bg-neutral-900 flex items-center justify-center"><Brain className="h-4 w-4 text-white" /></div>
              <span className="font-semibold text-[15px] tracking-[-0.02em] text-neutral-900">Sulci AI</span>
            </div>
            <p className="text-[13px] text-neutral-500 leading-relaxed max-w-[320px] mb-5">Clinical ontology normalization — NLP extraction, UMLS and OMOP mapping, and knowledge graph infrastructure for modern health systems.</p>
            <div className="flex items-center gap-2 mb-5">
              {["X", "GitHub", "LinkedIn"].map((s) => (
                <span key={s} className="h-8 px-3 flex items-center justify-center text-[11px] font-medium rounded-lg text-neutral-400 border border-neutral-200/80 hover:text-neutral-600 hover:border-neutral-300 hover:shadow-[0_2px_8px_rgba(0,0,0,0.04)] transition-all cursor-pointer">{s}</span>
              ))}
            </div>
            <div className="flex items-center gap-2 max-w-[320px]">
              <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg border border-neutral-200/80 bg-neutral-50/50 focus-within:border-indigo-300 focus-within:ring-2 focus-within:ring-indigo-100 transition-all">
                <Activity className="h-3.5 w-3.5 text-neutral-300 flex-shrink-0" />
                <input type="email" placeholder="your@email.com" className="flex-1 bg-transparent text-[13px] text-neutral-700 placeholder:text-neutral-400 outline-none" />
              </div>
              <button className="px-3.5 py-2 rounded-lg bg-neutral-900 text-white text-[12px] font-medium hover:bg-neutral-800 transition-colors shadow-sm">
                Subscribe
              </button>
            </div>
          </div>
          {Object.entries(links).map(([cat, items]) => (
            <div key={cat}>
              <p className="text-[12px] font-semibold tracking-wide uppercase text-neutral-400 mb-3">{cat}</p>
              <div className="space-y-2">
                {items.map((item) => (
                  <Link key={item} href="/dashboard" className="block text-[13px] text-neutral-500 hover:text-neutral-900 transition-colors">{item}</Link>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-12 pt-6 border-t border-neutral-200/60 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-[12px] text-neutral-400">&copy; 2026 Sulci AI, Inc. All rights reserved.</p>
          <div className="flex items-center gap-4 text-[11px] font-mono text-neutral-400">
            {["HIPAA", "SOC 2", "FHIR R4"].map((b) => (
              <span key={b} className="px-2 py-0.5 rounded bg-neutral-50 border border-neutral-100">{b}</span>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}

// ============================================================================
// PAGE
// ============================================================================
export default function Home() {
  return (
    <div className="min-h-screen bg-white selection:bg-indigo-100 overflow-x-hidden scroll-smooth">
      <BackToTop />
      <Nav />
      <HeroSection />
      <TrustBar />
      <ProblemSection />
      <CoreEngines />
      <DataTransformation />
      <APIShowcase />
      <PlatformBento />
      <TestimonialsSection />
      <StandardsAndCompliance />
      <IntegrationsSection />
      <FounderSection />
      <PricingSection />
      <CTASection />
      <FooterSection />
    </div>
  );
}
