"use client";

import { useRef, useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  motion,
  useInView,
  useMotionValue,
  useTransform,
  animate,
  AnimatePresence,
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
  ChevronUp,
} from "lucide-react";

// ============================================================================
// Google Fonts — DM Sans (display) + JetBrains Mono (data)
// ============================================================================
function FontLoader() {
  return (
    <>
      {/* eslint-disable-next-line @next/next/no-page-custom-font */}
      <link
        href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;0,9..40,800&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
        rel="stylesheet"
      />
    </>
  );
}

// ============================================================================
// Animated Counter with decimal support
// ============================================================================
function AnimatedNumber({
  value,
  suffix = "",
  prefix = "",
  className = "",
  duration = 1.5,
  decimals = 0,
}: {
  value: number;
  suffix?: string;
  prefix?: string;
  className?: string;
  duration?: number;
  decimals?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-50px" });
  const motionValue = useMotionValue(0);
  const rounded = useTransform(motionValue, (v) => {
    if (decimals > 0) return v.toFixed(decimals);
    return v >= 1000
      ? Math.round(v).toLocaleString()
      : Math.round(v).toString();
  });

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
// Animation Variants — simplified, no blur
// ============================================================================
const EASE: [number, number, number, number] = [0.25, 0.1, 0.25, 1];

const stagger = {
  container: {
    hidden: {},
    visible: {
      transition: { staggerChildren: 0.1, delayChildren: 0.2 },
    },
  },
  item: {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.6, ease: EASE },
    },
  },
};

// ============================================================================
// Section wrapper with scroll-triggered reveal (no blur)
// ============================================================================
function Reveal({
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
      initial={{ opacity: 0, y: 24 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.7, delay, ease: EASE }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

// ============================================================================
// Shared styles
// ============================================================================
const FONT_DISPLAY: React.CSSProperties = {
  fontFamily: "'DM Sans', sans-serif",
};
const FONT_MONO: React.CSSProperties = {
  fontFamily: "'JetBrains Mono', monospace",
};

// Section label component — clean, no flanking lines
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 mb-6 justify-center">
      <span
        className="text-xs font-medium tracking-[0.2em] uppercase text-[#5B9BD5]/60"
        style={FONT_MONO}
      >
        {children}
      </span>
    </div>
  );
}

// Section divider
function SectionDivider() {
  return (
    <div className="h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
  );
}

// ============================================================================
// FLOATING NAV (appears on scroll)
// ============================================================================
function FloatingNav() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 500);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <AnimatePresence>
      {visible && (
        <motion.nav
          initial={{ y: -80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -80, opacity: 0 }}
          transition={{ duration: 0.35, ease: EASE }}
          className="fixed top-4 left-1/2 -translate-x-1/2 z-50"
        >
          <div
            className="flex items-center gap-1 px-2 py-1.5 rounded-2xl border border-white/[0.08]"
            style={{
              background: "rgba(9,9,11,0.8)",
              backdropFilter: "blur(24px) saturate(1.4)",
              WebkitBackdropFilter: "blur(24px) saturate(1.4)",
            }}
          >
            <Link href="/trials">
              <Button
                size="sm"
                className="bg-transparent hover:bg-white/[0.06] text-white/50 hover:text-white/80 text-xs px-3 h-8 rounded-xl transition-colors"
                style={FONT_DISPLAY}
              >
                Trials
              </Button>
            </Link>
            <Link href="/dashboard">
              <Button
                size="sm"
                className="bg-transparent hover:bg-white/[0.06] text-white/50 hover:text-white/80 text-xs px-3 h-8 rounded-xl transition-colors"
                style={FONT_DISPLAY}
              >
                Dashboard
              </Button>
            </Link>
            <Link href="/patients">
              <Button
                size="sm"
                className="bg-transparent hover:bg-white/[0.06] text-white/50 hover:text-white/80 text-xs px-3 h-8 rounded-xl transition-colors"
                style={FONT_DISPLAY}
              >
                Patients
              </Button>
            </Link>
            <div className="w-px h-4 bg-white/[0.08] mx-1" />
            <button
              onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
              className="h-8 w-8 rounded-xl flex items-center justify-center text-white/30 hover:text-white/60 hover:bg-white/[0.06] transition-colors"
            >
              <ChevronUp className="h-4 w-4" />
            </button>
          </div>
        </motion.nav>
      )}
    </AnimatePresence>
  );
}

// ============================================================================
// HERO SECTION — Clean, minimal
// ============================================================================
function HeroSection() {
  const [trialCount, setTrialCount] = useState("3");
  useEffect(() => {
    fetch("/api/trials/stats")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.total_trials) setTrialCount(String(d.total_trials));
      })
      .catch(() => {});
  }, []);

  return (
    <section
      className="relative overflow-hidden text-white"
      style={{
        background:
          "linear-gradient(180deg, #09090B 0%, #111114 50%, #09090B 100%)",
      }}
    >
      {/* Single subtle radial glow */}
      <div
        className="absolute top-[-20%] left-[20%] w-[800px] h-[800px] rounded-full pointer-events-none"
        style={{
          background:
            "radial-gradient(circle, rgba(213,0,87,0.04) 0%, transparent 70%)",
        }}
      />

      <div className="relative max-w-6xl mx-auto px-6 pt-28 pb-32 md:pt-40 md:pb-44">
        <motion.div
          variants={stagger.container}
          initial="hidden"
          animate="visible"
          className="max-w-4xl"
        >
          {/* Platform indicator — static pink dot */}
          <motion.div variants={stagger.item} className="mb-10">
            <div
              className="inline-flex items-center gap-2.5 px-4 py-2 rounded-full border border-white/[0.08] bg-white/[0.02]"
              style={FONT_MONO}
            >
              <span className="h-2 w-2 rounded-full bg-[#D50057]" />
              <span className="text-[11px] text-white/50 tracking-wider uppercase">
                Regeneron Clinical Trial Platform
              </span>
            </div>
          </motion.div>

          {/* Headline — solid white, no gradient */}
          <motion.h1
            variants={stagger.item}
            className="text-5xl md:text-7xl lg:text-[5.5rem] font-bold leading-[0.95] tracking-[-0.04em] text-white/90"
            style={FONT_DISPLAY}
          >
            Accelerating
            <br />
            Patient Recruitment
          </motion.h1>

          {/* Static subtitle */}
          <motion.p
            variants={stagger.item}
            className="mt-6 text-lg md:text-xl text-white/40 tracking-tight"
            style={FONT_DISPLAY}
          >
            Automated eligibility screening for Regeneron clinical trials
          </motion.p>

          {/* CTAs — 2 buttons only */}
          <motion.div
            variants={stagger.item}
            className="mt-12 flex flex-col sm:flex-row items-start gap-3"
          >
            <Link href="/trials">
              <Button
                size="lg"
                className="bg-[#D50057] hover:bg-[#B8004B] text-white font-semibold px-8 border-0 rounded-xl h-12 transition-all duration-300"
                style={FONT_DISPLAY}
              >
                View Active Trials
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <Link href="/dashboard">
              <Button
                size="lg"
                className="bg-white/[0.04] border border-white/[0.08] text-white/50 hover:bg-white/[0.08] hover:text-white/70 hover:border-white/[0.15] px-8 rounded-xl h-12 transition-all duration-300"
                style={FONT_DISPLAY}
              >
                Platform Dashboard
              </Button>
            </Link>
          </motion.div>
        </motion.div>

        {/* Stats bar — clean row with dividers */}
        <motion.div
          variants={stagger.item}
          initial="hidden"
          animate="visible"
          className="mt-24"
        >
          <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-white/[0.06]">
            {[
              {
                value: trialCount,
                label: "Active Regeneron Trials",
              },
              {
                value: "80M+",
                label: "EYLEA Injections Worldwide",
              },
              {
                value: "1.4M+",
                label: "DUPIXENT Patients Globally",
              },
              {
                value: "68%",
                label: "LIBTAYO Recurrence Reduction",
              },
            ].map((stat) => (
              <div key={stat.label} className="px-6 py-6 text-center">
                <div
                  className="text-3xl md:text-4xl font-bold tracking-tighter text-white/90"
                  style={FONT_MONO}
                >
                  {stat.value}
                </div>
                <div
                  className="text-[10px] text-white/35 mt-2.5 tracking-[0.15em] uppercase"
                  style={FONT_MONO}
                >
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Bottom edge */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
    </section>
  );
}

// ============================================================================
// THERAPEUTIC PIPELINE — monochromatic cards
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
  },
];

function TherapeuticPipelineSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });
  const [trialCards, setTrialCards] = useState(trials);

  useEffect(() => {
    async function fetchTrialData() {
      try {
        const res = await fetch("/api/trials");
        if (!res.ok) return;
        const data = await res.json();
        const apiTrials: Array<{
          nct_number: string;
          enrollment_target: number;
          enrolled_count: number;
        }> = data.trials || [];
        if (apiTrials.length === 0) return;

        setTrialCards((prev) =>
          prev.map((card) => {
            const match = apiTrials.find((t) => t.nct_number === card.nct);
            if (!match) return card;
            const target = match.enrollment_target || 0;
            const enrolled = match.enrolled_count || 0;
            return {
              ...card,
              stat: `${enrolled} / ${target}`,
              statLabel: "Enrolled / Target",
            };
          })
        );
      } catch {
        // Keep defaults on error
      }
    }
    fetchTrialData();
  }, []);

  return (
    <section className="py-20 md:py-32 lg:py-40 px-6" style={{ background: "#09090B" }}>
      <div className="max-w-6xl mx-auto" ref={ref}>
        <Reveal>
          <div className="text-center mb-16">
            <SectionLabel>Active Trials</SectionLabel>
            <h2
              className="text-3xl md:text-4xl font-bold tracking-[-0.02em] text-white/90"
              style={FONT_DISPLAY}
            >
              Regeneron Therapeutic Pipeline
            </h2>
            <p
              className="text-white/45 mt-3 max-w-lg mx-auto text-[15px]"
              style={FONT_DISPLAY}
            >
              Automated eligibility screening across ophthalmology, oncology,
              and immunology
            </p>
          </div>
        </Reveal>

        <div className="grid md:grid-cols-3 gap-5">
          {trialCards.map((trial, i) => {
            const Icon = trial.icon;
            return (
              <motion.div
                key={trial.drug}
                initial={{ opacity: 0, y: 20 }}
                animate={isInView ? { opacity: 1, y: 0 } : {}}
                transition={{
                  duration: 0.6,
                  delay: 0.1 + i * 0.1,
                  ease: EASE,
                }}
              >
                <Link href="/trials" className="group block h-full">
                  <div className="relative h-full rounded-2xl border border-white/[0.08] bg-white/[0.02] p-7 transition-all duration-300 hover:border-white/[0.14] hover:bg-white/[0.03]">
                    {/* Icon + Phase */}
                    <div className="flex items-start justify-between mb-6">
                      <div className="h-11 w-11 rounded-xl flex items-center justify-center bg-white/[0.04] border border-white/[0.08]">
                        <Icon className="h-5 w-5 text-white/50" />
                      </div>
                      <span
                        className="text-[10px] font-semibold tracking-[0.15em] uppercase px-2.5 py-1 rounded-md bg-white/[0.04] text-white/40 border border-white/[0.06]"
                        style={FONT_MONO}
                      >
                        {trial.phase}
                      </span>
                    </div>

                    {/* Content */}
                    <p
                      className="text-[10px] font-semibold uppercase tracking-[0.2em] text-white/35 mb-2"
                      style={FONT_MONO}
                    >
                      {trial.area}
                    </p>
                    <h3
                      className="text-xl font-bold tracking-tight text-white/90 mb-3"
                      style={FONT_DISPLAY}
                    >
                      {trial.drug}
                    </h3>
                    <p
                      className="text-[13px] text-white/45 leading-relaxed"
                      style={FONT_DISPLAY}
                    >
                      {trial.indication}
                    </p>

                    {/* Stats */}
                    <div className="mt-6 pt-5 border-t border-white/[0.06] flex items-end justify-between">
                      <div>
                        <div
                          className="text-2xl font-bold tracking-tighter text-white/90"
                          style={FONT_MONO}
                        >
                          {trial.stat}
                        </div>
                        <div
                          className="text-[10px] text-white/35 mt-1 uppercase tracking-[0.15em]"
                          style={FONT_MONO}
                        >
                          {trial.statLabel}
                        </div>
                      </div>
                      <span
                        className="text-[10px] text-white/25"
                        style={FONT_MONO}
                      >
                        {trial.nct}
                      </span>
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
// LIVE ENROLLMENT PIPELINE — monochromatic, no pulse dots
// ============================================================================
const pipelineSteps = [
  { label: "Screened", count: 18, pct: 100 },
  { label: "Eligible", count: 10, pct: 56 },
  { label: "Enrolled", count: 7, pct: 39 },
  { label: "Active", count: 4, pct: 22 },
  { label: "Completed", count: 1, pct: 6 },
];

const conversionMetrics = [
  { rate: 55.6, label: "Screen-to-Eligible" },
  { rate: 70.0, label: "Eligible-to-Enrolled" },
  { rate: 57.1, label: "Enrolled-to-Active" },
];

function EnrollmentPipelineSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  const [pipeline, setPipeline] = useState(pipelineSteps);
  const [conversions, setConversions] = useState(conversionMetrics);

  useEffect(() => {
    async function fetchPipelineData() {
      try {
        const res = await fetch("/api/trials");
        if (!res.ok) return;
        const data = await res.json();
        const trialIds: string[] = (data.trials || []).map(
          (t: { id: string }) => t.id
        );
        if (trialIds.length === 0) return;

        const dashboards = await Promise.all(
          trialIds.map(async (id) => {
            const r = await fetch(`/api/trials/${id}/dashboard`);
            if (!r.ok) return null;
            return r.json();
          })
        );

        const valid = dashboards.filter(Boolean);
        if (valid.length === 0) return;

        const totals = valid.reduce(
          (acc, d) => ({
            candidates: acc.candidates + (d.total_candidates || 0),
            screened: acc.screened + (d.total_screened || 0),
            eligible: acc.eligible + (d.total_eligible || 0),
            enrolled: acc.enrolled + (d.total_enrolled || 0),
            active: acc.active + (d.total_active || 0),
            completed: acc.completed + (d.total_completed || 0),
            screenFailed: acc.screenFailed + (d.total_screen_failed || 0),
            withdrawn: acc.withdrawn + (d.total_withdrawn || 0),
          }),
          {
            candidates: 0,
            screened: 0,
            eligible: 0,
            enrolled: 0,
            active: 0,
            completed: 0,
            screenFailed: 0,
            withdrawn: 0,
          }
        );

        const screened =
          totals.screened +
          totals.eligible +
          totals.enrolled +
          totals.active +
          totals.completed +
          totals.screenFailed;
        const eligible =
          totals.eligible +
          totals.enrolled +
          totals.active +
          totals.completed;
        const enrolled = totals.enrolled + totals.active + totals.completed;
        const active = totals.active + totals.completed;
        const completed = totals.completed;

        if (screened === 0) return;

        setPipeline([
          { label: "Screened", count: screened, pct: 100 },
          {
            label: "Eligible",
            count: eligible,
            pct: Math.round((eligible / screened) * 100),
          },
          {
            label: "Enrolled",
            count: enrolled,
            pct: Math.round((enrolled / screened) * 100),
          },
          {
            label: "Active",
            count: active,
            pct: Math.round((active / screened) * 100),
          },
          {
            label: "Completed",
            count: completed,
            pct: Math.round((completed / screened) * 100),
          },
        ]);

        setConversions([
          {
            rate:
              eligible > 0
                ? parseFloat(((eligible / screened) * 100).toFixed(1))
                : 0,
            label: "Screen-to-Eligible",
          },
          {
            rate:
              eligible > 0
                ? parseFloat(((enrolled / eligible) * 100).toFixed(1))
                : 0,
            label: "Eligible-to-Enrolled",
          },
          {
            rate:
              enrolled > 0
                ? parseFloat(((active / enrolled) * 100).toFixed(1))
                : 0,
            label: "Enrolled-to-Active",
          },
        ]);
      } catch {
        // Keep defaults on error
      }
    }
    fetchPipelineData();
  }, []);

  return (
    <section className="py-20 md:py-32 lg:py-40 px-6" style={{ background: "#09090B" }}>
      <div className="max-w-5xl mx-auto" ref={ref}>
        <Reveal>
          <div className="text-center mb-14">
            <SectionLabel>Real-Time Data</SectionLabel>
            <h2
              className="text-3xl md:text-4xl font-bold tracking-[-0.02em] text-white/90"
              style={FONT_DISPLAY}
            >
              Live Enrollment Pipeline
            </h2>
            <p
              className="text-white/45 mt-3 text-[15px]"
              style={FONT_DISPLAY}
            >
              Real-time patient flow across all Regeneron trials
            </p>
          </div>
        </Reveal>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.7, delay: 0.15, ease: EASE }}
          className="rounded-2xl border border-white/[0.08] bg-white/[0.02] overflow-hidden"
        >
          {/* Header with live badge */}
          <div className="flex items-center gap-2 px-6 py-3 border-b border-white/[0.06]">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            <span
              className="text-[10px] text-white/35 tracking-[0.2em] uppercase"
              style={FONT_MONO}
            >
              Live Data — All Trials
            </span>
          </div>

          <div className="p-8">
            {/* Pipeline funnel — monochromatic bars */}
            <div className="flex items-stretch gap-2 md:gap-4">
              {pipeline.map((step, i) => (
                <div key={step.label} className="flex-1 min-w-0">
                  <div className="text-center mb-4">
                    <div
                      className="text-2xl md:text-3xl font-bold tracking-tighter text-white/90"
                      style={FONT_MONO}
                    >
                      <AnimatedNumber value={step.count} />
                    </div>
                    <div
                      className="text-[10px] text-white/35 mt-1.5 uppercase tracking-[0.12em]"
                      style={FONT_MONO}
                    >
                      {step.label}
                    </div>
                  </div>
                  {/* Monochromatic bar */}
                  <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                    <motion.div
                      className="h-full rounded-full bg-white/20"
                      initial={{ width: 0 }}
                      animate={isInView ? { width: `${step.pct}%` } : {}}
                      transition={{
                        duration: 1.2,
                        delay: 0.3 + i * 0.1,
                        ease: "easeOut",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Conversion metrics — monochromatic */}
            <div className="mt-10 pt-6 border-t border-white/[0.06] grid grid-cols-3 gap-3">
              {conversions.map((metric) => (
                <div
                  key={metric.label}
                  className="text-center rounded-xl p-4 border border-white/[0.06] bg-white/[0.02]"
                >
                  <div
                    className="text-lg font-bold text-white/90"
                    style={FONT_MONO}
                  >
                    <AnimatedNumber
                      value={metric.rate}
                      suffix="%"
                      decimals={1}
                    />
                  </div>
                  <div
                    className="text-[10px] text-white/35 mt-2 uppercase tracking-[0.12em]"
                    style={FONT_MONO}
                  >
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
// HOW IT WORKS — monochromatic icons, optional dashed line
// ============================================================================
const steps = [
  {
    step: "01",
    icon: Network,
    title: "Ingest from HIE",
    description:
      "Patient records flow from Carequality, CommonWell, and eHealth Exchange via Metriport. FHIR R4 Bundles are ingested automatically — conditions, medications, labs, and procedures.",
  },
  {
    step: "02",
    icon: BrainCircuit,
    title: "Normalize to OMOP",
    description:
      "All clinical data is mapped to OMOP concepts — ICD-10, LOINC, RxNorm, SNOMED CT. NLP extracts facts from unstructured notes. A patient knowledge graph captures every relationship.",
  },
  {
    step: "03",
    icon: Target,
    title: "Screen & Match",
    description:
      "Patients are evaluated against Regeneron trial criteria instantly. Structured inclusion/exclusion rules check conditions, labs, and medications. Candidates are ranked and surfaced to coordinators.",
  },
];

function HowItWorksSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <section className="py-20 md:py-32 lg:py-40 px-6" style={{ background: "#09090B" }}>
      <div className="max-w-5xl mx-auto" ref={ref}>
        <Reveal>
          <div className="text-center mb-16">
            <SectionLabel>Workflow</SectionLabel>
            <h2
              className="text-3xl md:text-4xl font-bold tracking-[-0.02em] text-white/90"
              style={FONT_DISPLAY}
            >
              How It Works
            </h2>
            <p
              className="text-white/45 mt-3 text-[15px]"
              style={FONT_DISPLAY}
            >
              From HIE data to trial enrollment in three steps
            </p>
          </div>
        </Reveal>

        <div className="relative">
          {/* Static dashed connecting line */}
          <div className="hidden md:block absolute top-[56px] left-[16%] right-[16%] h-px border-t border-dashed border-white/[0.06]" />

          <div className="grid md:grid-cols-3 gap-12">
            {steps.map(({ step, icon: Icon, title, description }, i) => (
              <motion.div
                key={step}
                initial={{ opacity: 0, y: 20 }}
                animate={isInView ? { opacity: 1, y: 0 } : {}}
                transition={{
                  duration: 0.6,
                  delay: 0.2 + i * 0.12,
                  ease: EASE,
                }}
                className="relative text-center"
              >
                {/* Icon */}
                <div className="relative inline-flex mb-7">
                  <div className="h-[72px] w-[72px] rounded-2xl flex items-center justify-center bg-white/[0.04] border border-white/[0.08]">
                    <Icon className="h-8 w-8 text-white/60" />
                  </div>
                  <span
                    className="absolute -top-2 -right-2 h-7 w-7 rounded-full bg-[#09090B] border border-white/[0.08] flex items-center justify-center text-[11px] font-bold text-white/50"
                    style={FONT_MONO}
                  >
                    {step}
                  </span>
                </div>
                <h3
                  className="font-bold text-lg mb-3 tracking-tight text-white/90"
                  style={FONT_DISPLAY}
                >
                  {title}
                </h3>
                <p
                  className="text-[13px] text-white/45 leading-relaxed max-w-xs mx-auto"
                  style={FONT_DISPLAY}
                >
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
// PLATFORM CAPABILITIES — Monochromatic bento grid, no tilt
// ============================================================================
function CapabilitiesSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  const smallCards = [
    {
      icon: Globe,
      title: "HIE Integration",
      description: "Carequality, CommonWell, eHealth Exchange via Metriport",
    },
    {
      icon: Database,
      title: "OMOP CDM",
      description: "Standardized concepts for cross-site analysis",
    },
    {
      icon: GitBranch,
      title: "Knowledge Graph",
      description: "Clinical relationships and temporal context",
    },
    {
      icon: Zap,
      title: "Real-time Screening",
      description: "Instant eligibility evaluation against trial criteria",
    },
  ];

  return (
    <section className="py-20 md:py-32 lg:py-40 px-6" style={{ background: "#09090B" }}>
      <div className="max-w-5xl mx-auto" ref={ref}>
        <Reveal>
          <div className="text-center mb-16">
            <SectionLabel>Infrastructure</SectionLabel>
            <h2
              className="text-3xl md:text-4xl font-bold tracking-[-0.02em] text-white/90"
              style={FONT_DISPLAY}
            >
              Platform Capabilities
            </h2>
            <p
              className="text-white/45 mt-3 text-[15px]"
              style={FONT_DISPLAY}
            >
              End-to-end clinical data infrastructure powering Regeneron trial
              recruitment
            </p>
          </div>
        </Reveal>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Large card — FHIR */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6, delay: 0.1, ease: EASE }}
            className="col-span-2 row-span-2"
          >
            <div className="rounded-2xl p-7 relative overflow-hidden h-full border border-white/[0.08] bg-white/[0.02] transition-all duration-300 hover:border-white/[0.14] hover:bg-white/[0.03]">
              <div className="relative">
                <div className="h-11 w-11 rounded-xl flex items-center justify-center mb-6 bg-white/[0.04] border border-white/[0.08]">
                  <HeartPulse className="h-5 w-5 text-white/50" />
                </div>
                <h3
                  className="text-lg font-bold mb-3 tracking-tight text-white/90"
                  style={FONT_DISPLAY}
                >
                  FHIR R4 Bundle Import
                </h3>
                <p
                  className="text-sm text-white/45 leading-relaxed mb-6"
                  style={FONT_DISPLAY}
                >
                  Ingest complete patient records as FHIR Bundles. Conditions,
                  medications, observations, procedures, and allergies are parsed
                  and mapped to OMOP automatically.
                </p>
                <div className="grid grid-cols-2 gap-3">
                  {["Conditions", "Medications", "Lab Results", "Procedures"].map(
                    (item) => (
                      <div
                        key={item}
                        className="flex items-center gap-2 text-xs text-white/45"
                        style={FONT_DISPLAY}
                      >
                        <CheckCircle2 className="h-3.5 w-3.5 text-white/30" />
                        {item}
                      </div>
                    )
                  )}
                </div>
              </div>
            </div>
          </motion.div>

          {/* Small cards */}
          {smallCards.map((card, i) => {
            const Icon = card.icon;
            return (
              <motion.div
                key={card.title}
                initial={{ opacity: 0, y: 20 }}
                animate={isInView ? { opacity: 1, y: 0 } : {}}
                transition={{
                  duration: 0.6,
                  delay: 0.15 + i * 0.06,
                  ease: EASE,
                }}
              >
                <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] overflow-hidden transition-all duration-300 hover:border-white/[0.14] hover:bg-white/[0.03] h-full">
                  <div className="p-5">
                    <div className="h-10 w-10 rounded-xl flex items-center justify-center mb-3 bg-white/[0.04] border border-white/[0.08]">
                      <Icon className="h-5 w-5 text-white/50" />
                    </div>
                    <h3
                      className="font-semibold text-sm mb-1.5 tracking-tight text-white/80"
                      style={FONT_DISPLAY}
                    >
                      {card.title}
                    </h3>
                    <p
                      className="text-[12px] text-white/40 leading-relaxed"
                      style={FONT_DISPLAY}
                    >
                      {card.description}
                    </p>
                  </div>
                </div>
              </motion.div>
            );
          })}

          {/* Wide card — Analytics */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6, delay: 0.45, ease: EASE }}
            className="col-span-2"
          >
            <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-5 transition-all duration-300 hover:border-white/[0.14] hover:bg-white/[0.03]">
              <div className="flex items-start gap-4">
                <div className="h-10 w-10 rounded-xl flex items-center justify-center flex-shrink-0 bg-white/[0.04] border border-white/[0.08]">
                  <BarChart3 className="h-5 w-5 text-white/50" />
                </div>
                <div>
                  <h3
                    className="font-semibold text-sm mb-1.5 tracking-tight text-white/80"
                    style={FONT_DISPLAY}
                  >
                    Enrollment Analytics & Reporting
                  </h3>
                  <p
                    className="text-[12px] text-white/40 leading-relaxed"
                    style={FONT_DISPLAY}
                  >
                    Track screening-to-enrollment conversion by trial, site, and
                    time period. Monitor recruitment bottlenecks and optimize
                    pipeline velocity.
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// STANDARDS & COMPLIANCE — static grid, no marquee
// ============================================================================
const standardsList = [
  "FHIR R4",
  "OMOP CDM",
  "ICD-10-CM",
  "SNOMED CT",
  "LOINC",
  "RxNorm",
  "CPT",
  "CDS Hooks",
  "SMART on FHIR",
];

function ComplianceSection() {
  return (
    <section className="py-20 md:py-32 px-6" style={{ background: "#09090B" }}>
      <Reveal className="max-w-5xl mx-auto">
        <div className="grid md:grid-cols-2 gap-12">
          {/* Standards — static flex-wrap grid */}
          <div>
            <p
              className="text-[10px] font-semibold uppercase tracking-[0.2em] text-white/35 mb-5"
              style={FONT_MONO}
            >
              Standards & Vocabularies
            </p>
            <div className="flex flex-wrap gap-2">
              {standardsList.map((standard) => (
                <span
                  key={standard}
                  className="px-3 py-1.5 text-[11px] rounded-lg bg-white/[0.03] text-white/45 border border-white/[0.06]"
                  style={FONT_MONO}
                >
                  {standard}
                </span>
              ))}
            </div>
          </div>

          {/* Compliance — monochromatic */}
          <div>
            <p
              className="text-[10px] font-semibold uppercase tracking-[0.2em] text-white/35 mb-5"
              style={FONT_MONO}
            >
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
                  className="flex items-center gap-3 rounded-xl p-3 border border-white/[0.06] bg-white/[0.02]"
                >
                  <div className="h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-white/[0.04] border border-white/[0.08]">
                    <Icon className="h-4 w-4 text-white/50" />
                  </div>
                  <span
                    className="text-[13px] text-white/50 font-medium"
                    style={FONT_DISPLAY}
                  >
                    {label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

// ============================================================================
// CTA — Clean, single button
// ============================================================================
function CTASection() {
  return (
    <section
      className="relative py-28 md:py-40 px-6"
      style={{ background: "#09090B" }}
    >
      <Reveal className="relative max-w-3xl mx-auto text-center">
        <h2
          className="text-3xl md:text-5xl font-bold leading-[1.05] tracking-[-0.02em] text-white/90"
          style={FONT_DISPLAY}
        >
          Ready to Accelerate
          <br />
          Regeneron Trial Enrollment?
        </h2>
        <p
          className="mt-5 text-white/45 text-base max-w-xl mx-auto"
          style={FONT_DISPLAY}
        >
          See how automated eligibility screening reduces time-to-enrollment and
          ensures no eligible patient is missed.
        </p>
        <div className="mt-10">
          <Link href="/trials">
            <Button
              size="lg"
              className="bg-[#D50057] hover:bg-[#B8004B] text-white font-semibold px-8 border-0 rounded-xl h-12 transition-all duration-300"
              style={FONT_DISPLAY}
            >
              <FlaskConical className="mr-2 h-4 w-4" />
              Explore Active Trials
            </Button>
          </Link>
        </div>
      </Reveal>
    </section>
  );
}

// ============================================================================
// FOOTER
// ============================================================================
function FooterSection() {
  return (
    <footer
      className="py-8 px-6"
      style={{ background: "#09090B" }}
    >
      <div className="h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent mb-8" />
      <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg flex items-center justify-center bg-white/[0.04] border border-white/[0.08]">
            <Microscope className="h-4 w-4 text-white/50" />
          </div>
          <div>
            <span
              className="font-semibold text-sm text-white/70"
              style={FONT_DISPLAY}
            >
              Clinical Ontology Normalizer
            </span>
            <span
              className="text-xs text-white/35 ml-2"
              style={FONT_DISPLAY}
            >
              for Regeneron
            </span>
          </div>
        </div>
        <div
          className="flex items-center gap-6 text-[11px] text-white/25 tracking-[0.15em]"
          style={FONT_MONO}
        >
          <span>HIPAA</span>
          <span>SOC 2</span>
          <span>21 CFR Part 11</span>
          <span>FHIR R4</span>
        </div>
        <p className="text-xs text-white/25" style={FONT_DISPLAY}>
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
  useEffect(() => {
    const prev = document.body.style.background;
    document.body.style.background = "#09090B";
    document.documentElement.style.background = "#09090B";
    return () => {
      document.body.style.background = prev;
      document.documentElement.style.background = "";
    };
  }, []);

  return (
    <div className="min-h-screen" style={{ background: "#09090B" }}>
      <FontLoader />
      <FloatingNav />
      <HeroSection />
      <SectionDivider />
      <TherapeuticPipelineSection />
      <SectionDivider />
      <EnrollmentPipelineSection />
      <SectionDivider />
      <HowItWorksSection />
      <SectionDivider />
      <CapabilitiesSection />
      <SectionDivider />
      <ComplianceSection />
      <SectionDivider />
      <CTASection />
      <FooterSection />
    </div>
  );
}
