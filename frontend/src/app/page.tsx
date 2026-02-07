"use client";

import { useRef, useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  motion,
  useInView,
  useMotionValue,
  useTransform,
  animate,
} from "framer-motion";
import {
  ArrowRight,
  Activity,
  Shield,
  Zap,
  Database,
  GitBranch,
  Target,
  CheckCircle2,
  BarChart3,
  Globe,
  Lock,
  FileText,
  FlaskConical,
  HeartPulse,
  Eye,
  ShieldCheck,
  Sparkles,
  Microscope,
  Network,
  BrainCircuit,
} from "lucide-react";

// ============================================================================
// Animated Counter — counts from 0 to target when in view
// ============================================================================
function AnimatedNumber({
  value,
  suffix = "",
  prefix = "",
  className = "",
  duration = 1.5,
}: {
  value: number;
  suffix?: string;
  prefix?: string;
  className?: string;
  duration?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-50px" });
  const motionValue = useMotionValue(0);
  const rounded = useTransform(motionValue, (v) =>
    v >= 1000 ? Math.round(v).toLocaleString() : Math.round(v).toString()
  );

  useEffect(() => {
    if (isInView) {
      animate(motionValue, value, { duration, ease: "easeOut" });
    }
  }, [isInView, value, duration, motionValue]);

  return (
    <span ref={ref} className={className}>
      {prefix}
      <motion.span>{rounded}</motion.span>
      {suffix}
    </span>
  );
}

// ============================================================================
// Stagger container + item variants
// ============================================================================
const EASE_OUT: [number, number, number, number] = [0.25, 0.46, 0.45, 0.94];

const stagger = {
  container: {
    hidden: {},
    visible: {
      transition: { staggerChildren: 0.1, delayChildren: 0.1 },
    },
  },
  item: {
    hidden: { opacity: 0, y: 24 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.5, ease: EASE_OUT },
    },
  },
};

const fadeUp = {
  hidden: { opacity: 0, y: 32 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: EASE_OUT },
  },
};

// ============================================================================
// Section wrapper with scroll-triggered reveal
// ============================================================================
function RevealSection({
  children,
  className = "",
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 40 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{
        duration: 0.7,
        delay,
        ease: EASE_OUT,
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

// ============================================================================
// HERO SECTION
// ============================================================================
function HeroSection() {
  return (
    <section className="relative overflow-hidden bg-[#002B5C] text-white">
      {/* Precision grid background */}
      <div className="absolute inset-0">
        {/* Fine dot grid */}
        <div
          className="absolute inset-0 opacity-[0.08]"
          style={{
            backgroundImage:
              "radial-gradient(circle, rgba(255,255,255,0.8) 1px, transparent 1px)",
            backgroundSize: "32px 32px",
          }}
        />
        {/* Horizontal scan lines */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              "repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(255,255,255,0.5) 3px, rgba(255,255,255,0.5) 4px)",
          }}
        />
        {/* Gradient wash */}
        <div className="absolute inset-0 bg-gradient-to-br from-[#045AA9]/30 via-transparent to-[#D50057]/10" />
        {/* Top-right accent glow */}
        <div className="absolute -top-40 -right-40 w-[600px] h-[600px] rounded-full bg-[#045AA9]/15 blur-[150px]" />
        {/* Bottom-left subtle glow */}
        <div className="absolute -bottom-32 -left-32 w-[400px] h-[400px] rounded-full bg-[#D50057]/8 blur-[120px]" />
      </div>

      {/* Animated molecular bonds — top right */}
      <motion.svg
        className="absolute -top-4 right-[6%] w-[240px] h-[240px] opacity-0 pointer-events-none"
        viewBox="0 0 240 240"
        animate={{ opacity: 0.06 }}
        transition={{ duration: 2, delay: 1 }}
      >
        <motion.path
          d="M120 50 L170 80 L170 140 L120 170 L70 140 L70 80 Z"
          stroke="white"
          strokeWidth="1.5"
          fill="none"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 3, delay: 1.5 }}
        />
        <motion.line x1="120" y1="50" x2="120" y2="15" stroke="white" strokeWidth="1.5"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1, delay: 3 }} />
        <motion.line x1="170" y1="80" x2="205" y2="65" stroke="white" strokeWidth="1.5"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1, delay: 3.2 }} />
        <motion.line x1="170" y1="140" x2="205" y2="155" stroke="white" strokeWidth="1.5"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1, delay: 3.4 }} />
        {[
          [120, 50], [170, 80], [170, 140], [120, 170], [70, 140], [70, 80],
          [120, 15], [205, 65], [205, 155],
        ].map(([cx, cy], i) => (
          <motion.circle
            key={i} cx={cx} cy={cy} r="3" fill="white"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 2 + i * 0.1, type: "spring" }}
          />
        ))}
      </motion.svg>

      {/* Animated molecular bonds — bottom left */}
      <motion.svg
        className="absolute bottom-8 left-[4%] w-[180px] h-[180px] opacity-0 pointer-events-none"
        viewBox="0 0 180 180"
        animate={{ opacity: 0.04 }}
        transition={{ duration: 2, delay: 1.5 }}
      >
        <motion.path
          d="M90 25 L145 65 L125 130 L55 130 L35 65 Z"
          stroke="white"
          strokeWidth="1.5"
          fill="none"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 2.5, delay: 2 }}
        />
        {[
          [90, 25], [145, 65], [125, 130], [55, 130], [35, 65],
        ].map(([cx, cy], i) => (
          <motion.circle
            key={i} cx={cx} cy={cy} r="2.5" fill="white"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 3 + i * 0.1, type: "spring" }}
          />
        ))}
      </motion.svg>

      {/* Geometric accent lines */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#045AA9]/40 to-transparent" />
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />

      <div className="relative max-w-6xl mx-auto px-6 py-20 md:py-28">
        <motion.div
          variants={stagger.container}
          initial="hidden"
          animate="visible"
          className="text-center max-w-4xl mx-auto"
        >
          {/* Platform badge */}
          <motion.div variants={stagger.item}>
            <Badge className="bg-white/[0.06] text-white/90 border-white/[0.12] backdrop-blur-sm text-[11px] font-medium tracking-wider uppercase px-4 py-1.5 hover:bg-white/10 transition-colors">
              <span className="relative flex h-2 w-2 mr-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
              </span>
              Regeneron Clinical Trial Platform
            </Badge>
          </motion.div>

          {/* Headline */}
          <motion.h1
            variants={stagger.item}
            className="mt-10 text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.05]"
          >
            <span className="text-white/90">Accelerating</span>
            <br />
            <span className="bg-gradient-to-r from-white via-blue-200 to-[#D50057] bg-clip-text text-transparent">
              Patient Recruitment
            </span>
          </motion.h1>

          <motion.p
            variants={stagger.item}
            className="mt-3 text-xl md:text-2xl font-light text-blue-200/60 tracking-tight"
          >
            for Regeneron Therapeutics
          </motion.p>

          <motion.p
            variants={stagger.item}
            className="mt-6 text-[15px] md:text-base text-blue-100/50 max-w-2xl mx-auto leading-relaxed font-light"
          >
            Ingest patient data from Health Information Exchanges via Metriport,
            standardize to OMOP, and automatically screen patients against
            trial eligibility criteria — in real time.
          </motion.p>

          {/* CTAs */}
          <motion.div
            variants={stagger.item}
            className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3"
          >
            <Link href="/trials">
              <Button
                size="lg"
                className="bg-[#D50057] hover:bg-[#B8004B] text-white font-semibold px-8 shadow-lg shadow-[#D50057]/20 border-0 rounded-xl h-12"
              >
                View Active Trials
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <Link href="/dashboard">
              <Button
                size="lg"
                className="bg-white/[0.06] backdrop-blur-sm border border-white/[0.12] text-white/80 hover:bg-white/10 hover:text-white px-8 rounded-xl h-12"
              >
                Platform Dashboard
              </Button>
            </Link>
          </motion.div>

          {/* Stats terminal */}
          <motion.div variants={stagger.item} className="mt-16 max-w-4xl mx-auto">
            <div className="rounded-2xl bg-white/[0.03] backdrop-blur-sm border border-white/[0.08] overflow-hidden">
              {/* Terminal header */}
              <div className="flex items-center gap-2 px-5 py-2.5 border-b border-white/[0.06] bg-white/[0.02]">
                <div className="flex gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-white/20" />
                  <div className="w-2 h-2 rounded-full bg-white/20" />
                  <div className="w-2 h-2 rounded-full bg-white/20" />
                </div>
                <span className="text-[10px] font-mono text-white/30 tracking-wider uppercase ml-2">
                  Trial Metrics — Live
                </span>
              </div>
              {/* Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-white/[0.06]">
                {[
                  { value: "3", label: "Active Regeneron Trials", accent: false },
                  { value: "80M+", label: "EYLEA Injections Worldwide", accent: true },
                  { value: "1.4M+", label: "DUPIXENT Patients Globally", accent: false },
                  { value: "68%", label: "LIBTAYO Recurrence Reduction", accent: true },
                ].map((stat, i) => (
                  <div
                    key={stat.label}
                    className="px-6 py-6 text-center group"
                  >
                    <div
                      className={`text-3xl md:text-4xl font-bold font-mono tracking-tighter ${
                        stat.accent ? "text-[#D50057]" : "text-white"
                      }`}
                    >
                      {stat.value}
                    </div>
                    <div className="text-[11px] text-blue-200/40 mt-2 font-medium tracking-wide uppercase">
                      {stat.label}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}

// ============================================================================
// THERAPEUTIC PIPELINE
// ============================================================================
const trials = [
  {
    icon: Eye,
    area: "Ophthalmology",
    drug: "EYLEA HD",
    indication:
      "Phase III for Diabetic Macular Edema in adults with Type 2 Diabetes. High-dose aflibercept with extended dosing intervals.",
    phase: "Phase III",
    nct: "NCT04429503",
    stat: "900",
    statLabel: "Target enrollment",
    accentColor: "#F59E0B",
    gradientFrom: "from-amber-500",
    gradientTo: "to-orange-600",
  },
  {
    icon: ShieldCheck,
    area: "Oncology",
    drug: "LIBTAYO",
    indication:
      "Phase II for advanced Cutaneous Squamous Cell Carcinoma. Cemiplimab anti-PD-1 immunotherapy for patients ineligible for surgery.",
    phase: "Phase II",
    nct: "NCT02760498",
    stat: "200",
    statLabel: "Target enrollment",
    accentColor: "#D50057",
    gradientFrom: "from-[#D50057]",
    gradientTo: "to-rose-600",
  },
  {
    icon: Sparkles,
    area: "Immunology",
    drug: "DUPIXENT",
    indication:
      "Phase III LIBERTY AD CHRONOS for moderate-to-severe Atopic Dermatitis. Dupilumab long-term efficacy with topical corticosteroids.",
    phase: "Phase III",
    nct: "NCT02395133",
    stat: "600",
    statLabel: "Target enrollment",
    accentColor: "#14B8A6",
    gradientFrom: "from-teal-500",
    gradientTo: "to-emerald-500",
  },
];

function TherapeuticPipelineSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <section className="py-20 px-6 bg-gradient-to-b from-slate-50/80 to-white dark:from-gray-950 dark:to-gray-900">
      <div className="max-w-6xl mx-auto" ref={ref}>
        <RevealSection>
          <div className="text-center mb-14">
            <Badge className="bg-[#045AA9]/8 text-[#045AA9] border-[#045AA9]/15 text-[11px] font-medium tracking-wider uppercase mb-4">
              Active Trials
            </Badge>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
              Regeneron Therapeutic Pipeline
            </h2>
            <p className="text-muted-foreground mt-3 max-w-lg mx-auto text-[15px]">
              Automated eligibility screening across ophthalmology, oncology,
              and immunology
            </p>
          </div>
        </RevealSection>

        <div className="grid md:grid-cols-3 gap-5">
          {trials.map((trial, i) => {
            const Icon = trial.icon;
            return (
              <motion.div
                key={trial.drug}
                initial={{ opacity: 0, y: 32 }}
                animate={isInView ? { opacity: 1, y: 0 } : {}}
                transition={{
                  duration: 0.5,
                  delay: i * 0.12,
                  ease: EASE_OUT,
                }}
              >
                <Link href="/trials" className="group block h-full">
                  <div className="relative h-full rounded-2xl border border-border/60 bg-white dark:bg-gray-950 overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-black/[0.04] hover:-translate-y-0.5 hover:border-border">
                    {/* Top accent line */}
                    <div
                      className="h-0.5 w-full"
                      style={{ backgroundColor: trial.accentColor }}
                    />

                    <div className="p-6">
                      {/* Icon + Phase */}
                      <div className="flex items-start justify-between mb-5">
                        <div
                          className={`h-11 w-11 rounded-xl bg-gradient-to-br ${trial.gradientFrom} ${trial.gradientTo} flex items-center justify-center text-white shadow-sm`}
                        >
                          <Icon className="h-5 w-5" />
                        </div>
                        <span className="text-[10px] font-mono font-semibold tracking-wider uppercase px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800 text-muted-foreground">
                          {trial.phase}
                        </span>
                      </div>

                      {/* Content */}
                      <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/60 mb-1.5">
                        {trial.area}
                      </p>
                      <h3 className="text-xl font-bold tracking-tight mb-2 group-hover:text-[#045AA9] transition-colors">
                        {trial.drug}
                      </h3>
                      <p className="text-[13px] text-muted-foreground leading-relaxed">
                        {trial.indication}
                      </p>

                      {/* Stats divider */}
                      <div className="mt-5 pt-4 border-t border-border/50 flex items-end justify-between">
                        <div>
                          <div className="text-2xl font-bold font-mono tracking-tight text-[#045AA9]">
                            {trial.stat}
                          </div>
                          <div className="text-[10px] text-muted-foreground/60 font-medium uppercase tracking-wider mt-0.5">
                            {trial.statLabel}
                          </div>
                        </div>
                        <span className="text-[10px] font-mono text-muted-foreground/40">
                          {trial.nct}
                        </span>
                      </div>
                    </div>

                    {/* Hover arrow */}
                    <div className="absolute bottom-6 right-6 opacity-0 group-hover:opacity-100 transition-all duration-300 translate-x-1 group-hover:translate-x-0">
                      <ArrowRight className="h-4 w-4 text-[#045AA9]" />
                    </div>
                  </div>
                </Link>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// LIVE ENROLLMENT PIPELINE
// ============================================================================
const pipelineSteps = [
  { label: "Screened", count: 415, pct: 100, color: "bg-slate-400" },
  { label: "Eligible", count: 287, pct: 69, color: "bg-[#045AA9]" },
  { label: "Consented", count: 198, pct: 48, color: "bg-teal-500" },
  { label: "Enrolled", count: 133, pct: 32, color: "bg-emerald-500" },
  { label: "Active", count: 89, pct: 21, color: "bg-green-600" },
];

const conversionMetrics = [
  { rate: "69.2%", label: "Screen-to-Eligible Rate", color: "text-[#045AA9]" },
  { rate: "69.0%", label: "Eligible-to-Consent Rate", color: "text-teal-600" },
  { rate: "67.2%", label: "Consent-to-Enrolled Rate", color: "text-emerald-600" },
];

function EnrollmentPipelineSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <section className="py-20 px-6">
      <div className="max-w-5xl mx-auto" ref={ref}>
        <RevealSection>
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 mb-4">
              <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
                Live Enrollment Pipeline
              </h2>
              <span className="relative flex h-2.5 w-2.5 ml-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
              </span>
            </div>
            <p className="text-muted-foreground text-[15px]">
              Real-time patient flow across all Regeneron trials
            </p>
          </div>
        </RevealSection>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="rounded-2xl border bg-white dark:bg-gray-950 overflow-hidden shadow-sm"
        >
          {/* Terminal header */}
          <div className="flex items-center gap-2 px-6 py-3 border-b bg-slate-50/80 dark:bg-gray-900/50">
            <div className="flex gap-1.5">
              <div className="w-2 h-2 rounded-full bg-slate-300 dark:bg-slate-600" />
              <div className="w-2 h-2 rounded-full bg-slate-300 dark:bg-slate-600" />
              <div className="w-2 h-2 rounded-full bg-slate-300 dark:bg-slate-600" />
            </div>
            <span className="text-[10px] font-mono text-muted-foreground/50 tracking-wider uppercase ml-2">
              Enrollment Funnel — All Trials
            </span>
          </div>

          <div className="p-8">
            {/* Pipeline funnel */}
            <div className="flex items-stretch gap-2 md:gap-3">
              {pipelineSteps.map((step, i) => (
                <div key={step.label} className="flex-1 flex items-center gap-2 md:gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="text-center mb-3">
                      <div className="text-2xl md:text-3xl font-bold font-mono tracking-tight">
                        <AnimatedNumber value={step.count} />
                      </div>
                      <div className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider mt-1">
                        {step.label}
                      </div>
                    </div>
                    {/* Animated bar */}
                    <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                      <motion.div
                        className={`h-full rounded-full ${step.color}`}
                        initial={{ width: 0 }}
                        animate={isInView ? { width: `${step.pct}%` } : {}}
                        transition={{
                          duration: 1,
                          delay: 0.3 + i * 0.1,
                          ease: "easeOut",
                        }}
                      />
                    </div>
                  </div>
                  {i < pipelineSteps.length - 1 && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={isInView ? { opacity: 1 } : {}}
                      transition={{ delay: 0.5 + i * 0.1 }}
                    >
                      <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/20 flex-shrink-0" />
                    </motion.div>
                  )}
                </div>
              ))}
            </div>

            {/* Conversion metrics */}
            <div className="mt-8 pt-6 border-t grid grid-cols-3 gap-3">
              {conversionMetrics.map((metric) => (
                <div
                  key={metric.label}
                  className="text-center rounded-xl bg-slate-50 dark:bg-gray-900/50 p-4"
                >
                  <div className={`text-lg font-bold font-mono ${metric.color}`}>
                    {metric.rate}
                  </div>
                  <div className="text-[10px] text-muted-foreground mt-1.5 uppercase tracking-wider font-medium">
                    {metric.label}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ============================================================================
// HOW IT WORKS
// ============================================================================
const steps = [
  {
    step: "01",
    icon: Network,
    title: "Ingest from HIE",
    description:
      "Patient records flow from Carequality, CommonWell, and eHealth Exchange via Metriport. FHIR R4 Bundles are ingested automatically — conditions, medications, labs, and procedures.",
    gradient: "from-[#045AA9] to-blue-600",
  },
  {
    step: "02",
    icon: BrainCircuit,
    title: "Normalize to OMOP",
    description:
      "All clinical data is mapped to OMOP concepts — ICD-10, LOINC, RxNorm, SNOMED CT. NLP extracts facts from unstructured notes. A patient knowledge graph captures every relationship.",
    gradient: "from-teal-500 to-emerald-500",
  },
  {
    step: "03",
    icon: Target,
    title: "Screen & Match",
    description:
      "Patients are evaluated against Regeneron trial criteria instantly. Structured inclusion/exclusion rules check conditions, labs, and medications. Candidates are ranked and surfaced to coordinators.",
    gradient: "from-[#D50057] to-rose-500",
  },
];

function HowItWorksSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <section className="py-20 px-6 bg-gradient-to-b from-white to-slate-50/80 dark:from-gray-900 dark:to-gray-950">
      <div className="max-w-5xl mx-auto" ref={ref}>
        <RevealSection>
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
              How It Works
            </h2>
            <p className="text-muted-foreground mt-3 text-[15px]">
              From HIE data to trial enrollment in three steps
            </p>
          </div>
        </RevealSection>

        <div className="relative">
          {/* Connecting line — desktop only */}
          <motion.div
            className="hidden md:block absolute top-[52px] left-[16%] right-[16%] h-px"
            initial={{ scaleX: 0 }}
            animate={isInView ? { scaleX: 1 } : {}}
            transition={{ duration: 0.8, delay: 0.3, ease: "easeOut" }}
            style={{ originX: 0 }}
          >
            <div className="w-full h-full bg-gradient-to-r from-[#045AA9]/30 via-teal-500/30 to-[#D50057]/30" />
          </motion.div>

          <div className="grid md:grid-cols-3 gap-10">
            {steps.map(({ step, icon: Icon, title, description, gradient }, i) => (
              <motion.div
                key={step}
                initial={{ opacity: 0, y: 32 }}
                animate={isInView ? { opacity: 1, y: 0 } : {}}
                transition={{
                  duration: 0.5,
                  delay: 0.2 + i * 0.15,
                  ease: EASE_OUT,
                }}
                className="relative text-center"
              >
                {/* Icon with step number */}
                <div className="relative inline-flex mb-6">
                  <div
                    className={`h-[72px] w-[72px] rounded-2xl bg-gradient-to-br ${gradient} flex items-center justify-center text-white shadow-lg`}
                  >
                    <Icon className="h-8 w-8" />
                  </div>
                  <span className="absolute -top-2 -right-2 h-7 w-7 rounded-full bg-white dark:bg-gray-950 border-2 border-slate-200 dark:border-slate-700 flex items-center justify-center text-[11px] font-mono font-bold text-[#045AA9] shadow-sm">
                    {step}
                  </span>
                </div>
                <h3 className="font-bold text-lg mb-3 tracking-tight">{title}</h3>
                <p className="text-[13px] text-muted-foreground leading-relaxed max-w-xs mx-auto">
                  {description}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// PLATFORM CAPABILITIES — Bento Grid
// ============================================================================
function CapabilitiesSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  const smallCards = [
    {
      icon: Globe,
      color: "text-teal-500",
      accent: "bg-teal-500",
      iconBg: "bg-teal-50 dark:bg-teal-950/50",
      title: "HIE Integration",
      description: "Carequality, CommonWell, eHealth Exchange via Metriport",
    },
    {
      icon: Database,
      color: "text-[#045AA9]",
      accent: "bg-[#045AA9]",
      iconBg: "bg-blue-50 dark:bg-blue-950/50",
      title: "OMOP CDM",
      description: "Standardized concepts for cross-site analysis",
    },
    {
      icon: GitBranch,
      color: "text-purple-500",
      accent: "bg-purple-500",
      iconBg: "bg-purple-50 dark:bg-purple-950/50",
      title: "Knowledge Graph",
      description: "Clinical relationships and temporal context",
    },
    {
      icon: Zap,
      color: "text-amber-500",
      accent: "bg-amber-500",
      iconBg: "bg-amber-50 dark:bg-amber-950/50",
      title: "Real-time Screening",
      description: "Instant eligibility evaluation against trial criteria",
    },
  ];

  return (
    <section className="py-20 px-6">
      <div className="max-w-5xl mx-auto" ref={ref}>
        <RevealSection>
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
              Platform Capabilities
            </h2>
            <p className="text-muted-foreground mt-3 text-[15px]">
              End-to-end clinical data infrastructure powering Regeneron trial
              recruitment
            </p>
          </div>
        </RevealSection>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Large card — FHIR */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="col-span-2 row-span-2 rounded-2xl bg-gradient-to-br from-[#045AA9] to-[#002B5C] p-6 text-white relative overflow-hidden group hover:shadow-xl hover:shadow-[#045AA9]/10 transition-all duration-300"
          >
            {/* Subtle pattern overlay */}
            <div
              className="absolute inset-0 opacity-[0.04]"
              style={{
                backgroundImage:
                  "radial-gradient(circle, rgba(255,255,255,0.8) 1px, transparent 1px)",
                backgroundSize: "24px 24px",
              }}
            />
            <div className="relative">
              <div className="h-11 w-11 rounded-xl bg-white/10 flex items-center justify-center mb-5">
                <HeartPulse className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-bold mb-2 tracking-tight">
                FHIR R4 Bundle Import
              </h3>
              <p className="text-sm text-blue-100/60 leading-relaxed mb-6">
                Ingest complete patient records as FHIR Bundles. Conditions,
                medications, observations, procedures, and allergies are parsed
                and mapped to OMOP automatically.
              </p>
              <div className="grid grid-cols-2 gap-2.5">
                {["Conditions", "Medications", "Lab Results", "Procedures"].map(
                  (item) => (
                    <div
                      key={item}
                      className="flex items-center gap-2 text-xs text-blue-200/70"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400/80" />
                      {item}
                    </div>
                  )
                )}
              </div>
            </div>
          </motion.div>

          {/* Small cards */}
          {smallCards.map((card, i) => {
            const Icon = card.icon;
            return (
              <motion.div
                key={card.title}
                initial={{ opacity: 0, y: 24 }}
                animate={isInView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.5, delay: 0.15 + i * 0.08 }}
                className="rounded-2xl border bg-white dark:bg-gray-950 overflow-hidden hover:shadow-md hover:shadow-black/[0.03] transition-all duration-300 group"
              >
                {/* Top accent line */}
                <div className={`h-0.5 ${card.accent} opacity-60`} />
                <div className="p-5">
                  <div className={`h-10 w-10 rounded-xl ${card.iconBg} flex items-center justify-center mb-3`}>
                    <Icon className={`h-5 w-5 ${card.color}`} />
                  </div>
                  <h3 className="font-semibold text-sm mb-1 tracking-tight">
                    {card.title}
                  </h3>
                  <p className="text-[12px] text-muted-foreground leading-relaxed">
                    {card.description}
                  </p>
                </div>
              </motion.div>
            );
          })}

          {/* Wide card — Analytics */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.5 }}
            className="col-span-2 rounded-2xl border bg-gradient-to-r from-slate-50 to-white dark:from-gray-900 dark:to-gray-950 p-5 hover:shadow-md hover:shadow-black/[0.03] transition-all duration-300"
          >
            <div className="flex items-start gap-4">
              <BarChart3 className="h-7 w-7 text-emerald-500 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-semibold text-sm mb-1 tracking-tight">
                  Enrollment Analytics & Reporting
                </h3>
                <p className="text-[12px] text-muted-foreground leading-relaxed">
                  Track screening-to-enrollment conversion by trial, site, and
                  time period. Monitor recruitment bottlenecks and optimize
                  pipeline velocity.
                </p>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// STANDARDS & COMPLIANCE
// ============================================================================
function ComplianceSection() {
  return (
    <section className="py-14 px-6 border-y border-border/40 bg-white dark:bg-gray-900">
      <RevealSection className="max-w-5xl mx-auto">
        <div className="grid md:grid-cols-2 gap-12">
          {/* Standards */}
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/60 mb-4">
              Standards & Vocabularies
            </p>
            <div className="flex flex-wrap gap-2">
              {[
                "FHIR R4",
                "OMOP CDM",
                "ICD-10-CM",
                "SNOMED CT",
                "LOINC",
                "RxNorm",
                "CPT",
                "CDS Hooks",
                "SMART on FHIR",
              ].map((standard) => (
                <span
                  key={standard}
                  className="px-3 py-1.5 text-[11px] font-mono rounded-lg bg-slate-50 dark:bg-slate-800 text-muted-foreground/80 border border-border/30"
                >
                  {standard}
                </span>
              ))}
            </div>
          </div>

          {/* Compliance */}
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/60 mb-4">
              Security & Compliance
            </p>
            <div className="grid grid-cols-2 gap-3">
              {[
                { icon: Shield, label: "HIPAA Compliant" },
                { icon: Lock, label: "SOC 2 Type II" },
                { icon: FileText, label: "21 CFR Part 11" },
                { icon: Activity, label: "Full Audit Trail" },
              ].map(({ icon: Icon, label }) => (
                <div
                  key={label}
                  className="flex items-center gap-3 rounded-xl bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900/50 p-3"
                >
                  <div className="h-8 w-8 rounded-lg bg-white dark:bg-gray-900 shadow-sm flex items-center justify-center flex-shrink-0">
                    <Icon className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <span className="text-[13px] text-muted-foreground font-medium">
                    {label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </RevealSection>
    </section>
  );
}

// ============================================================================
// CTA
// ============================================================================
function CTASection() {
  return (
    <section className="py-24 px-6 bg-[#002B5C] text-white relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0">
        <div
          className="absolute inset-0 opacity-[0.06]"
          style={{
            backgroundImage:
              "radial-gradient(circle, rgba(255,255,255,0.8) 1px, transparent 1px)",
            backgroundSize: "32px 32px",
          }}
        />
        <div className="absolute -top-24 right-0 w-[400px] h-[400px] bg-[#D50057]/10 rounded-full blur-[120px]" />
        <div className="absolute -bottom-24 left-0 w-[300px] h-[300px] bg-[#045AA9]/20 rounded-full blur-[100px]" />
      </div>

      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />

      <RevealSection className="relative max-w-3xl mx-auto text-center">
        <h2 className="text-3xl md:text-4xl font-bold leading-tight tracking-tight">
          Ready to Accelerate
          <br />
          <span className="bg-gradient-to-r from-white to-[#D50057] bg-clip-text text-transparent">
            Regeneron Trial Enrollment?
          </span>
        </h2>
        <p className="mt-4 text-blue-100/50 text-base max-w-xl mx-auto font-light">
          See how automated eligibility screening reduces time-to-enrollment and
          ensures no eligible patient is missed.
        </p>
        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link href="/trials">
            <Button
              size="lg"
              className="bg-[#D50057] hover:bg-[#B8004B] text-white font-semibold px-8 shadow-lg shadow-[#D50057]/20 border-0 rounded-xl h-12"
            >
              <FlaskConical className="mr-2 h-4 w-4" />
              Explore Trials
            </Button>
          </Link>
          <Link href="/dashboard">
            <Button
              size="lg"
              className="bg-white/[0.06] backdrop-blur-sm border border-white/[0.12] text-white/80 hover:bg-white/10 hover:text-white px-8 rounded-xl h-12"
            >
              View Dashboard
            </Button>
          </Link>
        </div>
      </RevealSection>
    </section>
  );
}

// ============================================================================
// FOOTER
// ============================================================================
function FooterSection() {
  return (
    <footer className="py-8 px-6 border-t border-border/40 bg-white dark:bg-gray-900">
      <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-[#045AA9] flex items-center justify-center">
            <Microscope className="h-4 w-4 text-white" />
          </div>
          <div>
            <span className="font-semibold text-sm">
              Clinical Ontology Normalizer
            </span>
            <span className="text-xs text-muted-foreground ml-2">
              for Regeneron
            </span>
          </div>
        </div>
        <div className="flex items-center gap-6 text-[11px] font-mono text-muted-foreground/60 tracking-wider">
          <span>HIPAA</span>
          <span>SOC 2</span>
          <span>21 CFR Part 11</span>
          <span>FHIR R4</span>
        </div>
        <p className="text-xs text-muted-foreground/50">
          &copy; 2026 Clinical Ontology Platform
        </p>
      </div>
    </footer>
  );
}

// ============================================================================
// PAGE EXPORT
// ============================================================================
export default function Home() {
  return (
    <div className="min-h-screen">
      <HeroSection />
      <TherapeuticPipelineSection />
      <EnrollmentPipelineSection />
      <HowItWorksSection />
      <CapabilitiesSection />
      <ComplianceSection />
      <CTASection />
      <FooterSection />
    </div>
  );
}
