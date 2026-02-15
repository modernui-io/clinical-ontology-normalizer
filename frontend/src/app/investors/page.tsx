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
  CheckCircle2,
  Zap,
  Lock,
  Globe,
  Activity,
  TrendingUp,
  Target,
  Users,
  Landmark,
  ChevronRight,
  Layers,
  Network,
  Calendar,
  DollarSign,
  Rocket,
  Building2,
  Microscope,
  Scale,
  CircleDot,
  ExternalLink,
  Menu,
  X,
} from "lucide-react";

// ============================================================================
// Design tokens (shared with landing page)
// ============================================================================
const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1];
const VIEWPORT = { once: true, margin: "-100px" as const };

// ============================================================================
// Animated counter — counts from 0 to target
// ============================================================================
function AnimatedCounter({ value, prefix = "", suffix = "", duration = 2 }: { value: number; prefix?: string; suffix?: string; duration?: number }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!inView) return;
    let start = 0;
    const end = value;
    const step = end / (duration * 60);
    const timer = setInterval(() => {
      start += step;
      if (start >= end) { setCount(end); clearInterval(timer); }
      else setCount(Math.floor(start));
    }, 1000 / 60);
    return () => clearInterval(timer);
  }, [inView, value, duration]);

  return <span ref={ref}>{prefix}{count.toLocaleString()}{suffix}</span>;
}

// ============================================================================
// Animated pipeline particle — flows along a path
// ============================================================================
function FlowParticle({ delay = 0, color = "rgba(129,140,248,0.6)" }: { delay?: number; color?: string }) {
  return (
    <motion.circle
      r="3"
      fill={color}
      initial={{ offsetDistance: "0%" }}
      animate={{ offsetDistance: "100%" }}
      transition={{ duration: 2.5, delay, repeat: Infinity, ease: "linear" }}
      style={{ offsetPath: "inherit" }}
    />
  );
}

// ============================================================================
// FLOATING PARTICLES — lightweight ambient effect
// ============================================================================
function FloatingParticles({ count = 18 }: { count?: number }) {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden="true">
      {Array.from({ length: count }).map((_, i) => {
        const size = 2 + (i % 3);
        const left = (i * 37 + 13) % 100;
        const top = (i * 53 + 7) % 100;
        const duration = 15 + (i % 7) * 3;
        const delay = (i % 5) * 2;
        const opacity = 0.15 + (i % 4) * 0.08;
        return (
          <div
            key={i}
            className="absolute rounded-full bg-indigo-400"
            style={{
              width: size,
              height: size,
              left: `${left}%`,
              top: `${top}%`,
              opacity,
              animation: `float-particle ${duration}s ${delay}s ease-in-out infinite`,
            }}
          />
        );
      })}
    </div>
  );
}

// ============================================================================
// TILT CARD — 3D perspective hover effect
// ============================================================================
function TiltCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [transform, setTransform] = useState("perspective(800px) rotateX(0deg) rotateY(0deg)");

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    setTransform(`perspective(800px) rotateY(${x * 6}deg) rotateX(${-y * 6}deg)`);
  };

  return (
    <div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => setTransform("perspective(800px) rotateX(0deg) rotateY(0deg)")}
      className={className}
      style={{ transform, transition: "transform 0.2s ease-out" }}
    >
      {children}
    </div>
  );
}

// ============================================================================
// MAGNETIC BUTTON — subtle cursor-follow on CTA buttons
// ============================================================================
function MagneticButton({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [translate, setTranslate] = useState({ x: 0, y: 0 });

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const x = (e.clientX - (rect.left + rect.width / 2)) * 0.15;
    const y = (e.clientY - (rect.top + rect.height / 2)) * 0.15;
    setTranslate({ x, y });
  };

  return (
    <div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => setTranslate({ x: 0, y: 0 })}
      className={className}
      style={{
        transform: `translate(${translate.x}px, ${translate.y}px)`,
        transition: "transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
      }}
    >
      {children}
    </div>
  );
}

// ============================================================================
// SECTION DIVIDER — premium gradient transition
// ============================================================================
function SectionDivider({ dark = false }: { dark?: boolean }) {
  return (
    <div className={`h-px ${dark ? "bg-gradient-to-r from-transparent via-white/[0.08] to-transparent" : "bg-gradient-to-r from-transparent via-neutral-200 to-transparent"}`} />
  );
}

// ============================================================================
// LIVE TRANSFORMATION DEMO — interactive before/after
// ============================================================================
function TransformationDemo() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });
  const [phase, setPhase] = useState<"idle" | "highlighting" | "extracting" | "structured">("idle");

  const clinicalNote = [
    { text: "Patient is a 67-year-old male presenting with ", type: "plain" },
    { text: "chest pain", type: "condition" },
    { text: " and ", type: "plain" },
    { text: "shortness of breath", type: "condition" },
    { text: ". Currently taking ", type: "plain" },
    { text: "metoprolol 50mg", type: "medication" },
    { text: " and ", type: "plain" },
    { text: "lisinopril 20mg", type: "medication" },
    { text: ". ", type: "plain" },
    { text: "BP 158/94", type: "measurement" },
    { text: ", ", type: "plain" },
    { text: "HR 92", type: "measurement" },
    { text: ". History of ", type: "plain" },
    { text: "coronary artery bypass", type: "procedure" },
    { text: " in 2019. ", type: "plain" },
    { text: "Diabetes type 2", type: "condition" },
    { text: " well-controlled.", type: "plain" },
  ];

  const outputRows = [
    { mention: "chest pain", conceptId: "29857009", vocab: "SNOMED", domain: "Condition", assertion: "Present", color: "text-blue-400" },
    { mention: "shortness of breath", conceptId: "267036007", vocab: "SNOMED", domain: "Condition", assertion: "Present", color: "text-blue-400" },
    { mention: "metoprolol 50mg", conceptId: "866924", vocab: "RxNorm", domain: "Drug", assertion: "Active", color: "text-emerald-400" },
    { mention: "lisinopril 20mg", conceptId: "314076", vocab: "RxNorm", domain: "Drug", assertion: "Active", color: "text-emerald-400" },
    { mention: "BP 158/94", conceptId: "85354-9", vocab: "LOINC", domain: "Measurement", assertion: "Recorded", color: "text-amber-400" },
    { mention: "HR 92", conceptId: "8867-4", vocab: "LOINC", domain: "Measurement", assertion: "Recorded", color: "text-amber-400" },
    { mention: "coronary artery bypass", conceptId: "232717009", vocab: "SNOMED", domain: "Procedure", assertion: "Historical", color: "text-purple-400" },
    { mention: "diabetes type 2", conceptId: "44054006", vocab: "SNOMED", domain: "Condition", assertion: "Present", color: "text-blue-400" },
  ];

  const highlightBg: Record<string, string> = {
    condition: "rgba(59,130,246,0.15)",
    medication: "rgba(16,185,129,0.15)",
    measurement: "rgba(245,158,11,0.15)",
    procedure: "rgba(168,85,247,0.15)",
  };

  const highlightText: Record<string, string> = {
    condition: "text-blue-300",
    medication: "text-emerald-300",
    measurement: "text-amber-300",
    procedure: "text-purple-300",
  };

  useEffect(() => {
    if (!inView) return;
    const t1 = setTimeout(() => setPhase("highlighting"), 400);
    const t2 = setTimeout(() => setPhase("extracting"), 2000);
    const t3 = setTimeout(() => setPhase("structured"), 3200);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, [inView]);

  return (
    <section ref={ref} className="py-32 md:py-44 px-6 bg-neutral-950 relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(99,102,241,0.05),transparent_70%)]" />
      <div className="max-w-[1200px] mx-auto relative">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
          className="text-center mb-16"
        >
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-indigo-400/60 mb-4">
            Live Demo
          </p>
          <h2 className="text-[2rem] md:text-[3.25rem] font-semibold tracking-[-0.04em] text-white leading-[1.05]">
            See the{" "}
            <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-indigo-400 bg-clip-text text-transparent">
              transformation.
            </span>
          </h2>
          <p className="mt-5 text-white/40 max-w-lg mx-auto text-[16px] leading-relaxed">
            Watch a real clinical note get parsed, extracted, and normalized into structured OMOP concepts — in real time.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-2 gap-6 items-stretch">
          {/* Left: Clinical Note */}
          <motion.div
            initial={{ opacity: 0, x: -20, filter: "blur(4px)" }}
            whileInView={{ opacity: 1, x: 0, filter: "blur(0px)" }}
            viewport={VIEWPORT}
            transition={{ duration: 0.6, ease: EASE }}
            className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-6 md:p-8"
          >
            <div className="flex items-center gap-2 mb-5">
              <FileText className="h-4 w-4 text-white/30" />
              <span className="text-[11px] font-semibold text-white/30 uppercase tracking-wider">Raw Clinical Note</span>
            </div>
            <div className="text-[14px] leading-[1.8] text-white/50 font-mono">
              {clinicalNote.map((segment, i) => {
                if (segment.type === "plain") {
                  return <span key={i}>{segment.text}</span>;
                }
                const isActive = phase !== "idle";
                const delay = i * 0.12;
                return (
                  <motion.span
                    key={i}
                    initial={{ backgroundColor: "transparent" }}
                    animate={isActive ? { backgroundColor: highlightBg[segment.type] || "transparent" } : {}}
                    transition={{ duration: 0.4, delay: isActive ? delay : 0 }}
                    className={`inline rounded px-0.5 py-0.5 ${isActive ? (highlightText[segment.type] || "") : ""}`}
                  >
                    {segment.text}
                  </motion.span>
                );
              })}
            </div>
            <div className="mt-5 flex items-center gap-3 flex-wrap">
              {[
                { label: "Conditions", color: "bg-blue-500" },
                { label: "Medications", color: "bg-emerald-500" },
                { label: "Measurements", color: "bg-amber-500" },
                { label: "Procedures", color: "bg-purple-500" },
              ].map((legend) => (
                <div key={legend.label} className="flex items-center gap-1.5">
                  <div className={`h-2 w-2 rounded-full ${legend.color}`} />
                  <span className="text-[10px] text-white/30">{legend.label}</span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Right: Structured Output */}
          <motion.div
            initial={{ opacity: 0, x: 20, filter: "blur(4px)" }}
            whileInView={{ opacity: 1, x: 0, filter: "blur(0px)" }}
            viewport={VIEWPORT}
            transition={{ duration: 0.6, delay: 0.1, ease: EASE }}
            className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-6 md:p-8"
          >
            <div className="flex items-center gap-2 mb-5">
              <Database className="h-4 w-4 text-white/30" />
              <span className="text-[11px] font-semibold text-white/30 uppercase tracking-wider">OMOP Normalized Output</span>
            </div>
            <div className="space-y-0">
              <div className="grid grid-cols-[1fr_72px_62px_76px_66px] gap-2 text-[10px] font-semibold text-white/20 uppercase tracking-wider pb-2 border-b border-white/[0.06]">
                <span>Mention</span>
                <span>Concept</span>
                <span>Vocab</span>
                <span>Domain</span>
                <span>Assert</span>
              </div>
              {outputRows.map((row, i) => (
                <motion.div
                  key={row.mention}
                  initial={{ opacity: 0, x: 10 }}
                  animate={phase === "structured" || phase === "extracting" ? { opacity: 1, x: 0 } : {}}
                  transition={{ duration: 0.3, delay: phase === "extracting" ? i * 0.15 : i * 0.08 }}
                  className="grid grid-cols-[1fr_72px_62px_76px_66px] gap-2 items-center py-1.5 text-[11px] border-b border-white/[0.03]"
                >
                  <span className={`font-medium ${row.color} truncate`}>{row.mention}</span>
                  <span className="font-mono text-white/40 text-[10px]">{row.conceptId}</span>
                  <span className="text-white/30">{row.vocab}</span>
                  <span className="text-white/30">{row.domain}</span>
                  <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                    row.assertion === "Present" ? "bg-blue-500/10 text-blue-400" :
                    row.assertion === "Active" ? "bg-emerald-500/10 text-emerald-400" :
                    row.assertion === "Recorded" ? "bg-amber-500/10 text-amber-400" :
                    "bg-purple-500/10 text-purple-400"
                  }`}>{row.assertion}</span>
                </motion.div>
              ))}
            </div>
            <div className="mt-4 flex items-center gap-2 text-[11px] text-white/20">
              <Zap className="h-3 w-3" />
              <span>Processed in ~200ms via Sulci API</span>
            </div>
          </motion.div>
        </div>

        {/* Connecting visual */}
        <div className="hidden md:flex items-center justify-center mt-8">
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={VIEWPORT}
            transition={{ duration: 0.5, delay: 0.3, ease: EASE }}
            className="flex items-center gap-3 px-5 py-2.5 rounded-full bg-gradient-to-r from-indigo-500/10 to-violet-500/10 border border-indigo-500/20"
          >
            <span className="text-[12px] text-white/40">Raw text</span>
            <ArrowRight className="h-3.5 w-3.5 text-indigo-400" />
            <span className="text-[12px] font-semibold text-indigo-300">Queryable knowledge</span>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// ANIMATED ARR GROWTH CHART — hockey-stick SVG
// ============================================================================
function ARRGrowthChart() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });

  const data = [
    { year: 0, arr: 0, label: "$0", stage: "Pre-Seed" },
    { year: 1, arr: 0.35, label: "$350K", stage: "Seed" },
    { year: 2, arr: 2.25, label: "$2.3M", stage: "Series A" },
    { year: 3, arr: 12, label: "$12M", stage: "Series B" },
    { year: 4, arr: 40, label: "$40M", stage: "Series C" },
    { year: 5, arr: 100, label: "$100M", stage: "Pre-Exit" },
  ];

  const w = 600, h = 300;
  const pad = { top: 30, right: 40, bottom: 50, left: 60 };
  const plotW = w - pad.left - pad.right;
  const plotH = h - pad.top - pad.bottom;

  const points = data.map((d, i) => ({
    x: pad.left + (i / (data.length - 1)) * plotW,
    y: pad.top + plotH - (d.arr / 100) * plotH,
    ...d,
  }));

  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${pad.top + plotH} L ${points[0].x} ${pad.top + plotH} Z`;
  const gridLines = [0, 25, 50, 75, 100];

  return (
    <div ref={ref} className="mb-16">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={VIEWPORT}
        transition={{ duration: 0.5, ease: EASE }}
        className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6 md:p-8"
      >
        <div className="text-[11px] font-semibold text-white/30 uppercase tracking-wider mb-1">
          Projected ARR Growth
        </div>
        <div className="text-[10px] text-white/20 mb-6">Based on Bessemer health AI benchmarks</div>
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
          <defs>
            <linearGradient id="arr-gradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(129,140,248,0.3)" />
              <stop offset="100%" stopColor="rgba(129,140,248,0)" />
            </linearGradient>
          </defs>
          {/* Grid */}
          {gridLines.map((val) => {
            const gy = pad.top + plotH - (val / 100) * plotH;
            return (
              <g key={val}>
                <line x1={pad.left} y1={gy} x2={w - pad.right} y2={gy} stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
                <text x={pad.left - 8} y={gy + 4} textAnchor="end" fill="rgba(255,255,255,0.2)" fontSize="10" fontFamily="monospace">
                  ${val}M
                </text>
              </g>
            );
          })}
          {/* Area */}
          <motion.path
            d={areaPath}
            fill="url(#arr-gradient)"
            initial={{ opacity: 0 }}
            animate={inView ? { opacity: 1 } : {}}
            transition={{ duration: 1, delay: 0.8 }}
          />
          {/* Line */}
          <motion.path
            d={linePath}
            fill="none"
            stroke="rgba(129,140,248,0.8)"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            animate={inView ? { pathLength: 1 } : {}}
            transition={{ duration: 1.5, delay: 0.3, ease: EASE }}
          />
          {/* Data points + labels */}
          {points.map((p, i) => (
            <motion.g key={i}>
              <motion.circle
                cx={p.x} cy={p.y} r="4"
                fill="rgb(129,140,248)" stroke="rgba(23,23,23,1)" strokeWidth="2"
                initial={{ opacity: 0, scale: 0 }}
                animate={inView ? { opacity: 1, scale: 1 } : {}}
                transition={{ duration: 0.3, delay: 0.3 + i * 0.25 }}
              />
              <motion.text
                x={p.x} y={p.y - 14} textAnchor="middle"
                fill="rgba(255,255,255,0.7)" fontSize="10" fontWeight="600" fontFamily="monospace"
                initial={{ opacity: 0 }}
                animate={inView ? { opacity: 1 } : {}}
                transition={{ duration: 0.3, delay: 0.5 + i * 0.25 }}
              >
                {p.label}
              </motion.text>
              <motion.text
                x={p.x} y={pad.top + plotH + 20} textAnchor="middle"
                fill="rgba(255,255,255,0.25)" fontSize="9" fontWeight="500"
                initial={{ opacity: 0 }}
                animate={inView ? { opacity: 1 } : {}}
                transition={{ duration: 0.3, delay: 0.6 + i * 0.2 }}
              >
                {p.stage}
              </motion.text>
              <motion.text
                x={p.x} y={pad.top + plotH + 35} textAnchor="middle"
                fill="rgba(255,255,255,0.15)" fontSize="10" fontFamily="monospace"
                initial={{ opacity: 0 }}
                animate={inView ? { opacity: 1 } : {}}
                transition={{ duration: 0.3, delay: 0.6 + i * 0.2 }}
              >
                Y{p.year}
              </motion.text>
            </motion.g>
          ))}
        </svg>
      </motion.div>
    </div>
  );
}

// ============================================================================
// COMPETITIVE RADAR CHART — pentagon SVG
// ============================================================================
function CompetitiveRadar() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });

  const axes = ["NLP Extraction", "Ontology Mapping", "Knowledge Graph", "E2E Pipeline", "FHIR/OMOP Export"];
  const sulciScores = [0.92, 0.95, 0.90, 0.95, 0.88];
  const competitorScores = [0.65, 0.55, 0.15, 0.20, 0.40];

  const cx = 150, cy = 150, r = 110;

  const getPoint = (index: number, value: number) => {
    const angle = (Math.PI * 2 * index) / axes.length - Math.PI / 2;
    return { x: cx + r * value * Math.cos(angle), y: cy + r * value * Math.sin(angle) };
  };

  const makePolygon = (values: number[]) =>
    values.map((v, i) => { const p = getPoint(i, v); return `${p.x},${p.y}`; }).join(" ");

  const gridLevels = [0.25, 0.5, 0.75, 1.0];

  return (
    <div ref={ref} className="mt-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={VIEWPORT}
        transition={{ duration: 0.5, ease: EASE }}
        className="rounded-2xl border border-neutral-200 bg-white p-6"
      >
        <div className="text-[13px] font-semibold text-neutral-900 mb-1">Capability Comparison</div>
        <div className="text-[12px] text-neutral-400 mb-4">Sulci vs. best-in-class competitor composite</div>
        <div className="flex justify-center">
          <svg viewBox="0 0 300 300" className="w-full max-w-[320px] h-auto">
            {/* Grid */}
            {gridLevels.map((level) => (
              <polygon
                key={level}
                points={axes.map((_, i) => { const p = getPoint(i, level); return `${p.x},${p.y}`; }).join(" ")}
                fill="none" stroke="rgba(0,0,0,0.06)" strokeWidth="1"
              />
            ))}
            {/* Axis lines */}
            {axes.map((_, i) => {
              const p = getPoint(i, 1);
              return <line key={i} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="rgba(0,0,0,0.06)" strokeWidth="1" />;
            })}
            {/* Competitor polygon */}
            <motion.polygon
              points={makePolygon(competitorScores)}
              fill="rgba(0,0,0,0.03)" stroke="rgba(0,0,0,0.15)" strokeWidth="1.5" strokeDasharray="4 3"
              initial={{ opacity: 0 }}
              animate={inView ? { opacity: 1 } : {}}
              transition={{ duration: 0.6, delay: 0.3 }}
            />
            {/* Sulci polygon */}
            <motion.polygon
              points={makePolygon(sulciScores)}
              fill="rgba(99,102,241,0.08)" stroke="rgba(99,102,241,0.6)" strokeWidth="2"
              initial={{ opacity: 0, scale: 0.3 }}
              animate={inView ? { opacity: 1, scale: 1 } : {}}
              transition={{ duration: 0.8, delay: 0.5, ease: EASE }}
              style={{ transformOrigin: `${cx}px ${cy}px` }}
            />
            {/* Sulci data points */}
            {sulciScores.map((v, i) => {
              const p = getPoint(i, v);
              return (
                <motion.circle
                  key={i} cx={p.x} cy={p.y} r="3.5" fill="rgb(99,102,241)"
                  initial={{ opacity: 0 }}
                  animate={inView ? { opacity: 1 } : {}}
                  transition={{ duration: 0.3, delay: 0.7 + i * 0.1 }}
                />
              );
            })}
            {/* Labels */}
            {axes.map((label, i) => {
              const p = getPoint(i, 1.22);
              return (
                <text key={label} x={p.x} y={p.y} textAnchor="middle" dominantBaseline="central"
                  fill="rgba(0,0,0,0.4)" fontSize="9" fontWeight="500"
                >
                  {label}
                </text>
              );
            })}
          </svg>
        </div>
        <div className="flex items-center justify-center gap-6 mt-4">
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full bg-indigo-500" />
            <span className="text-[11px] font-medium text-neutral-600">Sulci</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full border border-neutral-400 border-dashed bg-neutral-100" />
            <span className="text-[11px] font-medium text-neutral-400">Best Competitor</span>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

// ============================================================================
// NAV (investor variant — dark)
// ============================================================================
function InvestorNav() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);

  useEffect(() => {
    const fn = () => {
      setScrolled(window.scrollY > 20);
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      setScrollProgress(docHeight > 0 ? (window.scrollY / docHeight) * 100 : 0);
    };
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  return (
    <>
      <motion.nav
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5, ease: EASE }}
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          scrolled
            ? "bg-neutral-950/90 backdrop-blur-2xl border-b border-white/[0.06] shadow-[0_1px_3px_rgba(0,0,0,0.3)]"
            : "bg-transparent"
        }`}
      >
        <div className="max-w-[1200px] mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="h-7 w-7 rounded-lg bg-white flex items-center justify-center group-hover:scale-105 transition-transform">
              <Brain className="h-4 w-4 text-neutral-900" />
            </div>
            <span className="font-semibold text-[15px] tracking-[-0.02em] text-white">
              Sulci
            </span>
          </Link>
          <div className="hidden md:flex items-center gap-0.5 text-[13px]">
            <Link
              href="/"
              className="px-3 py-1.5 rounded-md text-white/40 hover:text-white hover:bg-white/[0.06] transition-all duration-150"
            >
              Product
            </Link>
            <Link
              href="/investors"
              className="px-3 py-1.5 rounded-md text-white bg-white/[0.08] transition-all duration-150"
            >
              Investors
            </Link>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/dashboard" className="hidden md:block">
              <Button
                size="sm"
                className="bg-white text-neutral-900 hover:bg-neutral-100 text-[13px] rounded-lg h-8 px-3.5 shadow-sm"
              >
                Request Demo <ArrowRight className="ml-1 h-3 w-3" />
              </Button>
            </Link>
            <button
              className="md:hidden p-1.5 rounded-lg hover:bg-white/[0.06] transition-colors"
              onClick={() => setMobileOpen(!mobileOpen)}
            >
              {mobileOpen ? (
                <X className="h-5 w-5 text-white/70" />
              ) : (
                <Menu className="h-5 w-5 text-white/70" />
              )}
            </button>
          </div>
        </div>
        {/* Scroll progress bar */}
        <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-transparent">
          <div
            className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-[width] duration-150 ease-out"
            style={{ width: `${scrollProgress}%` }}
          />
        </div>
      </motion.nav>

      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
              onClick={() => setMobileOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2, ease: EASE }}
              className="fixed top-16 left-0 right-0 z-50 md:hidden"
            >
              <div className="mx-4 mt-2 rounded-2xl border border-white/[0.08] bg-neutral-900/95 backdrop-blur-2xl shadow-[0_8px_40px_rgba(0,0,0,0.4)] p-4">
                <div className="space-y-1">
                  <Link
                    href="/"
                    onClick={() => setMobileOpen(false)}
                    className="flex items-center px-3 py-2.5 rounded-lg text-[15px] font-medium text-white/60 hover:bg-white/[0.06] hover:text-white transition-colors"
                  >
                    Product
                  </Link>
                  <Link
                    href="/investors"
                    onClick={() => setMobileOpen(false)}
                    className="flex items-center px-3 py-2.5 rounded-lg text-[15px] font-medium text-white hover:bg-white/[0.06] transition-colors"
                  >
                    Investors
                  </Link>
                </div>
                <div className="mt-3 pt-3 border-t border-white/[0.06]">
                  <Link
                    href="/dashboard"
                    onClick={() => setMobileOpen(false)}
                    className="block"
                  >
                    <Button className="w-full h-10 text-[14px] rounded-xl bg-white text-neutral-900 hover:bg-neutral-100">
                      Request Demo{" "}
                      <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
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
// HERO
// ============================================================================
function HeroSection() {
  const heroRef = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"],
  });
  const y = useTransform(scrollYProgress, [0, 1], [0, 80]);
  const opacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);

  return (
    <section ref={heroRef} className="relative pt-16 overflow-hidden bg-neutral-950">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(99,102,241,0.08),transparent_70%)]" />
      <FloatingParticles />
      <motion.div style={{ y, opacity }} className="relative">
        <div className="max-w-[1200px] mx-auto px-6 pt-32 md:pt-44 pb-32 md:pb-44">
          <motion.div
            variants={{
              hidden: {},
              visible: {
                transition: { staggerChildren: 0.06, delayChildren: 0.05 },
              },
            }}
            initial="hidden"
            animate="visible"
            className="text-center"
          >
            <motion.div
              variants={{
                hidden: { opacity: 0, y: 12 },
                visible: {
                  opacity: 1,
                  y: 0,
                  transition: { duration: 0.5, ease: EASE },
                },
              }}
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-indigo-500/20 bg-indigo-500/[0.08] text-[12px] font-medium text-indigo-300 mb-8"
            >
              <Landmark className="h-3 w-3" /> Investor Overview
            </motion.div>

            <motion.h1
              variants={{
                hidden: { opacity: 0, y: 12 },
                visible: {
                  opacity: 1,
                  y: 0,
                  transition: { duration: 0.5, ease: EASE },
                },
              }}
              className="text-[2.75rem] md:text-[4.5rem] lg:text-[5.5rem] font-semibold leading-[0.95] tracking-[-0.06em] text-white"
            >
              The clinical data
              <br />
              <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-indigo-400 bg-clip-text text-transparent">
                infrastructure layer.
              </span>
            </motion.h1>

            <motion.p
              variants={{
                hidden: { opacity: 0, y: 12 },
                visible: {
                  opacity: 1,
                  y: 0,
                  transition: { duration: 0.5, ease: EASE },
                },
              }}
              className="mt-8 text-[18px] md:text-[22px] text-white/40 max-w-[680px] mx-auto leading-[1.55] tracking-[-0.01em]"
            >
              AI agents are replacing healthcare apps — but they can&apos;t reason
              over raw physician notes. Sulci is the normalization layer that
              turns unstructured clinical data into queryable knowledge.
            </motion.p>

            <motion.div
              variants={{
                hidden: { opacity: 0, y: 12 },
                visible: {
                  opacity: 1,
                  y: 0,
                  transition: { duration: 0.5, ease: EASE },
                },
              }}
              className="mt-10 flex items-center justify-center gap-3 flex-wrap"
            >
              <MagneticButton>
                <Link href="/dashboard">
                  <Button className="group bg-white text-neutral-900 hover:bg-neutral-100 rounded-xl h-12 px-8 text-[15px] font-medium shadow-[0_1px_2px_rgba(255,255,255,0.1),0_4px_12px_rgba(255,255,255,0.06)] transition-all glow-button">
                    Try It Live <ArrowRight className="ml-1.5 h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
                  </Button>
                </Link>
              </MagneticButton>
              <MagneticButton>
                <a href="mailto:alex@sulci.ai">
                  <button className="group inline-flex items-center justify-center rounded-xl h-12 px-8 text-[15px] font-medium border border-white/[0.12] text-white/60 hover:text-white hover:border-white/[0.2] hover:bg-white/[0.04] transition-all">
                    Contact Founder <ChevronRight className="ml-1 h-4 w-4" />
                  </button>
                </a>
              </MagneticButton>
            </motion.div>

            <motion.div
              variants={{
                hidden: { opacity: 0, y: 12 },
                visible: {
                  opacity: 1,
                  y: 0,
                  transition: { duration: 0.5, ease: EASE },
                },
              }}
              className="mt-12 flex items-center justify-center gap-8 md:gap-12 flex-wrap"
            >
              <div className="text-center">
                <div className="text-[2rem] md:text-[2.5rem] font-bold tracking-[-0.04em] text-white tabular-nums">
                  <AnimatedCounter value={1000} suffix="x" />
                </div>
                <div className="text-[12px] text-white/30 mt-1">LLM cost decline in 3 years</div>
              </div>
              <div className="text-center">
                <div className="text-[2rem] md:text-[2.5rem] font-bold tracking-[-0.04em] text-white tabular-nums">
                  <AnimatedCounter value={155} prefix="$" suffix="B" />
                </div>
                <div className="text-[12px] text-white/30 mt-1">Healthcare AI agent TAM</div>
              </div>
              <div className="text-center">
                <div className="text-[2rem] md:text-[2.5rem] font-bold tracking-[-0.04em] text-white tabular-nums">
                  <AnimatedCounter value={80} suffix="%" />
                </div>
                <div className="text-[12px] text-white/30 mt-1">Clinical data is unstructured</div>
              </div>
            </motion.div>

            <motion.div
              variants={{
                hidden: { opacity: 0, y: 12 },
                visible: {
                  opacity: 1,
                  y: 0,
                  transition: { duration: 0.5, ease: EASE },
                },
              }}
              className="mt-14 flex items-center justify-center gap-6 flex-wrap"
            >
              {["OMOP CDM v5.4", "FHIR R4", "SNOMED CT", "RxNorm", "HL7 CDA", "HIPAA", "SOC 2"].map((badge) => (
                <span key={badge} className="text-[11px] font-medium tracking-[0.06em] uppercase text-white/20 border border-white/[0.06] rounded-md px-2.5 py-1">
                  {badge}
                </span>
              ))}
            </motion.div>
          </motion.div>
        </div>
      </motion.div>
      <div className="h-px bg-gradient-to-r from-transparent via-white/[0.08] to-transparent" />
    </section>
  );
}

// ============================================================================
// THE PROBLEM
// ============================================================================
function ProblemSection() {
  const stats = [
    {
      value: "80%",
      label: "of clinical data is unstructured",
      detail:
        "Trapped in free-text notes, discharge summaries, and pathology reports — invisible to analytics, AI, and research systems.",
      icon: FileText,
    },
    {
      value: "$504B",
      label: "in excess admin costs annually",
      detail:
        "The U.S. healthcare system spends $1,055 per capita on administration — 3.4x the next highest country. Manual abstraction is a major driver.",
      icon: DollarSign,
    },
    {
      value: "50%",
      label: "assertion accuracy from cloud NLP",
      detail:
        "AWS Comprehend Medical correctly identifies whether a diagnosis is confirmed vs. ruled out only half the time. Downstream analytics are built on sand.",
      icon: Target,
    },
    {
      value: "70%",
      label: "of abstractors report errors",
      detail:
        "Human chart abstractors are expensive, error-prone, and increasingly hard to retain — 3 out of 5 are dissatisfied in their roles.",
      icon: Users,
    },
  ];

  return (
    <section className="py-32 md:py-44 px-6 bg-white dot-grid">
      <div className="max-w-[1200px] mx-auto">
        <div className="grid md:grid-cols-5 gap-8 md:gap-16">
          <div className="md:col-span-2">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={VIEWPORT}
              transition={{ duration: 0.5, ease: EASE }}
            >
              <p className="text-[11px] font-semibold tracking-[0.1em] uppercase text-neutral-400 mb-4">
                The Problem
              </p>
              <h2 className="text-[2rem] md:text-[3rem] font-semibold tracking-[-0.035em] leading-[1.1]">
                <span className="bg-gradient-to-r from-neutral-900 via-neutral-800 to-neutral-900 bg-clip-text text-transparent">Clinical data is healthcare&apos;s biggest bottleneck.</span>
              </h2>
              <p className="mt-5 text-[15px] text-neutral-500 leading-relaxed">
                Every AI model, every clinical trial, every quality measure depends on structured clinical data. Today, that data is locked in free text — and the tools to extract it are broken.
              </p>
            </motion.div>
          </div>
          <div className="md:col-span-3 space-y-3">
            {stats.map((s, i) => {
              const Icon = s.icon;
              return (
                <motion.div
                  key={s.label}
                  initial={{ opacity: 0, y: 16 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={VIEWPORT}
                  transition={{
                    duration: 0.4,
                    delay: i * 0.06,
                    ease: EASE,
                  }}
                >
                  <div className="rounded-xl border border-neutral-200 bg-white p-5 hover:shadow-[0_4px_20px_rgba(0,0,0,0.04)] transition-shadow">
                    <div className="flex items-start gap-5">
                      <div className="flex-shrink-0 w-[110px] md:w-[140px]">
                        <div className="text-[2.2rem] md:text-[2.6rem] font-bold tracking-[-0.04em] text-neutral-900 leading-none">
                          {s.value}
                        </div>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Icon className="h-3.5 w-3.5 text-neutral-400" />
                          <div className="text-[14px] font-semibold text-neutral-900">
                            {s.label}
                          </div>
                        </div>
                        <p className="text-[13px] text-neutral-500 leading-relaxed">
                          {s.detail}
                        </p>
                      </div>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// MACRO THESIS — three converging forces (research-backed)
// ============================================================================
function MacroThesisSection() {
  const costData = [
    { year: "2022", cost: 20, label: "$20.00" },
    { year: "2023", cost: 6, label: "$6.00" },
    { year: "2024", cost: 1.2, label: "$1.20" },
    { year: "2025", cost: 0.4, label: "$0.40" },
    { year: "2026E", cost: 0.05, label: "$0.05" },
  ];
  const maxCost = 20;

  return (
    <section className="py-32 md:py-44 px-6 bg-neutral-950 relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(99,102,241,0.08),transparent_50%),radial-gradient(ellipse_at_bottom_right,rgba(168,85,247,0.06),transparent_50%)]" />
      <div className="max-w-[1200px] mx-auto relative">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
          className="text-center mb-6"
        >
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-indigo-400/60 mb-4">
            The Macro Thesis
          </p>
          <h2 className="text-[2rem] md:text-[3.25rem] font-semibold tracking-[-0.04em] text-white leading-[1.05]">
            Three forces creating an
            <br />
            <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-purple-400 bg-clip-text text-transparent">
              irreversible market shift.
            </span>
          </h2>
          <p className="mt-5 text-white/40 max-w-2xl mx-auto text-[16px] leading-relaxed">
            LLM costs are collapsing. Healthcare&apos;s walled gardens are cracking under legal and regulatory pressure. And AI agents are replacing traditional apps — but they need clean, normalized data to reason over.
          </p>
        </motion.div>

        {/* Force 1: Cost Collapse */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, delay: 0.1, ease: EASE }}
          className="mt-16 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8 md:p-10 gradient-border"
        >
          <div className="grid md:grid-cols-2 gap-10 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-emerald-500/20 bg-emerald-500/[0.08] text-[11px] font-semibold text-emerald-400 mb-5">
                <TrendingUp className="h-3 w-3" /> Force 1
              </div>
              <h3 className="text-[1.5rem] md:text-[2rem] font-semibold tracking-[-0.03em] text-white leading-[1.15] mb-4">
                AI inference costs are falling
                <br />
                <span className="text-emerald-400">1,000x in 3 years.</span>
              </h3>
              <p className="text-[14px] text-white/40 leading-relaxed mb-5">
                GPT-4 equivalent performance went from $20/M tokens to $0.40 — and the decline is accelerating. Post-2024, costs are dropping 200x per year. Processing an entire patient chart through NLP normalization is going from &ldquo;expensive enterprise project&rdquo; to pennies per document.
              </p>
              <div className="space-y-2">
                {[
                  "Makes it economically viable to normalize ALL legacy unstructured data",
                  "Healthcare NLP market: $5B → $16-37B by 2030 (25-35% CAGR)",
                  "Inference cost decline faster than Moore's Law, dotcom bandwidth, or cloud storage",
                ].map((item) => (
                  <div key={item} className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400/60 mt-0.5 flex-shrink-0" />
                    <span className="text-[12px] text-white/50 leading-snug">{item}</span>
                  </div>
                ))}
              </div>
            </div>
            {/* Animated cost chart */}
            <div className="bg-white/[0.03] rounded-xl border border-white/[0.06] p-6">
              <div className="text-[11px] font-semibold text-white/30 uppercase tracking-wider mb-1">
                Cost per Million Tokens (GPT-4 equivalent)
              </div>
              <div className="text-[10px] text-white/20 mb-6">Source: Epoch AI, a16z</div>
              <div className="space-y-3">
                {costData.map((d, i) => (
                  <div key={d.year} className="flex items-center gap-3">
                    <div className="w-[50px] text-[12px] font-mono text-white/40 text-right flex-shrink-0">{d.year}</div>
                    <div className="flex-1 h-7 bg-white/[0.04] rounded overflow-hidden relative">
                      <motion.div
                        initial={{ width: 0 }}
                        whileInView={{ width: `${Math.max((d.cost / maxCost) * 100, 2)}%` }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.8, delay: 0.3 + i * 0.12, ease: EASE }}
                        className={`h-full rounded ${
                          i === costData.length - 1
                            ? "bg-gradient-to-r from-emerald-500 to-emerald-400"
                            : i >= 3
                            ? "bg-gradient-to-r from-emerald-500/60 to-emerald-400/60"
                            : "bg-gradient-to-r from-white/20 to-white/10"
                        }`}
                      />
                    </div>
                    <div className={`w-[60px] text-[13px] font-semibold tabular-nums flex-shrink-0 ${
                      i >= 3 ? "text-emerald-400" : "text-white/50"
                    }`}>
                      {d.label}
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-5 pt-4 border-t border-white/[0.06] flex items-center justify-between">
                <span className="text-[11px] text-white/20">3-year decline</span>
                <span className="text-[18px] font-bold text-emerald-400">50x cheaper</span>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Force 2: Walled Gardens Cracking */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, delay: 0.15, ease: EASE }}
          className="mt-5 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8 md:p-10 gradient-border"
        >
          <div className="grid md:grid-cols-2 gap-10 items-center">
            {/* Visual: Epic's walled garden */}
            <div className="order-2 md:order-1 bg-white/[0.03] rounded-xl border border-white/[0.06] p-6">
              <div className="text-[11px] font-semibold text-white/30 uppercase tracking-wider mb-5">
                The Epic Bottleneck
              </div>
              <div className="grid grid-cols-2 gap-3 mb-5">
                {[
                  { value: "325M+", label: "Patient records", sub: "~90% of U.S. population" },
                  { value: "MUMPS", label: "Database language", sub: "Designed in 1966" },
                  { value: "$1M-500M", label: "Switching cost", sub: "Per health system" },
                  { value: "1 month", label: "Simple query time", sub: "e.g. 'Males with high BP'" },
                ].map((s) => (
                  <div key={s.label} className="rounded-lg bg-white/[0.04] border border-white/[0.06] p-3">
                    <div className="text-[16px] font-bold text-white tracking-tight">{s.value}</div>
                    <div className="text-[11px] text-white/40 mt-0.5">{s.label}</div>
                    <div className="text-[10px] text-white/20 mt-0.5">{s.sub}</div>
                  </div>
                ))}
              </div>
              <div className="rounded-lg bg-red-500/[0.08] border border-red-500/20 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <Scale className="h-3.5 w-3.5 text-red-400" />
                  <span className="text-[12px] font-semibold text-red-400">Dec 2025: Texas AG Antitrust Lawsuit</span>
                </div>
                <p className="text-[11px] text-white/40 leading-relaxed">
                  Alleging illegal monopoly, data access obstruction, and penalizing hospitals that use competing apps.
                </p>
              </div>
            </div>
            <div className="order-1 md:order-2">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-red-500/20 bg-red-500/[0.08] text-[11px] font-semibold text-red-400 mb-5">
                <Lock className="h-3 w-3" /> Force 2
              </div>
              <h3 className="text-[1.5rem] md:text-[2rem] font-semibold tracking-[-0.03em] text-white leading-[1.15] mb-4">
                Healthcare&apos;s walled gardens
                <br />
                <span className="text-red-400">are cracking open.</span>
              </h3>
              <p className="text-[14px] text-white/40 leading-relaxed mb-5">
                Epic stores records for 325M+ patients on a 1960s-era database architecture. Even Epic-to-Epic transfers aren&apos;t seamless. The Texas AG just sued them for antitrust. TEFCA mandates nationwide interoperability. Decades of trapped clinical data is about to need normalization.
              </p>
              <div className="space-y-2">
                {[
                  "Enormous pent-up demand to get data OUT into standardized, queryable formats",
                  "Regulatory + legal pressure forcing interoperability (TEFCA, CMS FHIR mandates)",
                  "EHR vendors optimize within their ecosystem — not cross-platform",
                ].map((item) => (
                  <div key={item} className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-red-400/60 mt-0.5 flex-shrink-0" />
                    <span className="text-[12px] text-white/50 leading-snug">{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </motion.div>

        {/* Force 3: Agentic AI Shift */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, delay: 0.2, ease: EASE }}
          className="mt-5 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8 md:p-10 gradient-border"
        >
          <div className="grid md:grid-cols-2 gap-10 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-violet-500/20 bg-violet-500/[0.08] text-[11px] font-semibold text-violet-400 mb-5">
                <Zap className="h-3 w-3" /> Force 3
              </div>
              <h3 className="text-[1.5rem] md:text-[2rem] font-semibold tracking-[-0.03em] text-white leading-[1.15] mb-4">
                Apps are becoming agents.
                <br />
                <span className="text-violet-400">Agents need clean data.</span>
              </h3>
              <p className="text-[14px] text-white/40 leading-relaxed mb-5">
                PitchBook calls healthcare AI agents a $155B annual revenue opportunity. The pattern is clear: small AI agents that plan, fetch, draft, and verify — replacing traditional app UIs. But an agent can&apos;t reason over a MUMPS database or raw physician notes. It needs OMOP/FHIR-normalized, concept-mapped data.
              </p>
              <div className="space-y-2">
                {[
                  "Agentic AI in healthcare: 40-45% annual growth, $10.8B by 2032",
                  "Multi-agent systems posting highest growth at 45.3% CAGR",
                  "The missing piece: a normalization layer between raw data and AI agents",
                ].map((item) => (
                  <div key={item} className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-violet-400/60 mt-0.5 flex-shrink-0" />
                    <span className="text-[12px] text-white/50 leading-snug">{item}</span>
                  </div>
                ))}
              </div>
            </div>
            {/* Visual: App → Agent → Data flow */}
            <div className="bg-white/[0.03] rounded-xl border border-white/[0.06] p-6">
              <div className="text-[11px] font-semibold text-white/30 uppercase tracking-wider mb-6">
                The Architecture Shift
              </div>
              <div className="space-y-4">
                {/* Old: Traditional */}
                <div className="rounded-lg bg-white/[0.04] border border-white/[0.06] p-4">
                  <div className="text-[10px] font-semibold text-white/20 uppercase tracking-wider mb-3">Yesterday</div>
                  <div className="flex items-center gap-2 text-[12px]">
                    <div className="px-3 py-1.5 rounded bg-white/[0.06] text-white/30 font-mono">User</div>
                    <ArrowRight className="h-3 w-3 text-white/15" />
                    <div className="px-3 py-1.5 rounded bg-white/[0.06] text-white/30 font-mono">App UI</div>
                    <ArrowRight className="h-3 w-3 text-white/15" />
                    <div className="px-3 py-1.5 rounded bg-white/[0.06] text-white/30 font-mono">Database</div>
                  </div>
                </div>
                {/* New: Agentic */}
                <div className="rounded-lg bg-violet-500/[0.08] border border-violet-500/20 p-4">
                  <div className="text-[10px] font-semibold text-violet-400/60 uppercase tracking-wider mb-3">Tomorrow</div>
                  <div className="flex items-center gap-2 text-[12px]">
                    <div className="px-3 py-1.5 rounded bg-violet-500/10 border border-violet-500/20 text-violet-300 font-mono">User</div>
                    <ArrowRight className="h-3 w-3 text-violet-400/40" />
                    <div className="px-3 py-1.5 rounded bg-violet-500/10 border border-violet-500/20 text-violet-300 font-mono">AI Agent</div>
                    <ArrowRight className="h-3 w-3 text-violet-400/40" />
                    <div className="px-3 py-1.5 rounded bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 font-mono font-bold">Normalized Data</div>
                  </div>
                </div>
                {/* Sulci layer */}
                <div className="mt-2 flex items-center justify-center">
                  <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-indigo-500/20 to-violet-500/20 border border-indigo-500/30">
                    <Brain className="h-3.5 w-3.5 text-indigo-400" />
                    <span className="text-[12px] font-semibold text-indigo-300">Sulci = the normalization layer agents need</span>
                  </div>
                </div>
              </div>
              <div className="mt-5 pt-4 border-t border-white/[0.06] flex items-center justify-between">
                <span className="text-[11px] text-white/20">Source: PitchBook</span>
                <span className="text-[16px] font-bold text-violet-400">$155B opportunity</span>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Bottom connector — the implication */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, delay: 0.25, ease: EASE }}
          className="mt-10 text-center"
        >
          <div className="inline-flex items-center gap-3 px-6 py-3 rounded-full border border-white/[0.08] bg-white/[0.03]">
            <span className="text-[14px] text-white/50">
              All three forces point to the same need →
            </span>
            <span className="text-[14px] font-semibold text-white">
              A clinical data normalization layer.
            </span>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ============================================================================
// MARKET OPPORTUNITY
// ============================================================================
function MarketSection() {
  const markets = [
    {
      label: "Healthcare AI Agents",
      now: "$538M",
      future: "$10.8B+",
      year: "2032",
      cagr: "45.6%",
      color: "from-indigo-500 to-violet-500",
      width: "w-full",
    },
    {
      label: "Clinical NLP / Unstructured Data",
      now: "$5-7B",
      future: "$16-37B",
      year: "2030",
      cagr: "25-35%",
      color: "from-violet-500 to-purple-500",
      width: "w-[75%]",
    },
    {
      label: "AI in Healthcare (Total)",
      now: "$17.2B",
      future: "$77B+",
      year: "2035",
      cagr: "16.2%",
      color: "from-purple-500 to-fuchsia-500",
      width: "w-[60%]",
    },
    {
      label: "Knowledge Graphs in Healthcare",
      now: "$2B",
      future: "$8B",
      year: "2033",
      cagr: "~25%",
      color: "from-fuchsia-500 to-pink-500",
      width: "w-[40%]",
    },
  ];

  return (
    <section className="py-32 md:py-44 px-6 bg-neutral-50 dot-grid">
      <div className="max-w-[1200px] mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
          className="mb-16"
        >
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-4">
            Market Opportunity
          </p>
          <h2 className="text-[2rem] md:text-[3rem] font-semibold tracking-[-0.04em] text-neutral-900 leading-[1.05]">
            Infrastructure for a $155B market.
          </h2>
          <p className="mt-4 text-neutral-500 max-w-lg text-[16px] leading-relaxed">
            Every AI agent, every clinical trial, every quality measure depends on normalized clinical data. Agents are the $155B opportunity — we are the substrate they require.
          </p>
        </motion.div>

        <div className="space-y-4 mb-16">
          {markets.map((m, i) => (
            <motion.div
              key={m.label}
              initial={{ opacity: 0, x: -20, filter: "blur(4px)" }}
              whileInView={{ opacity: 1, x: 0, filter: "blur(0px)" }}
              viewport={VIEWPORT}
              transition={{ duration: 0.5, delay: i * 0.08, ease: EASE }}
            >
              <div className="rounded-xl border border-neutral-200 bg-white p-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[14px] font-semibold text-neutral-900">
                    {m.label}
                  </span>
                  <div className="flex items-center gap-3 text-[13px]">
                    <span className="text-neutral-400">{m.now}</span>
                    {m.future && m.year && (
                      <>
                        <ArrowRight className="h-3 w-3 text-neutral-300" />
                        <span className="font-semibold text-neutral-900">
                          {m.future}
                        </span>
                        <span className="text-neutral-400">by {m.year}</span>
                      </>
                    )}
                    {!m.year && (
                      <span className="text-neutral-400">{m.future}</span>
                    )}
                    {m.cagr && (
                      <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 text-[11px] font-semibold">
                        {m.cagr} CAGR
                      </span>
                    )}
                  </div>
                </div>
                <div className="h-2 rounded-full bg-neutral-100 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    whileInView={{ width: "100%" }}
                    viewport={{ once: true }}
                    transition={{
                      duration: 1,
                      delay: 0.3 + i * 0.1,
                      ease: EASE,
                    }}
                    className={`h-full rounded-full bg-gradient-to-r ${m.color} ${m.width}`}
                  />
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        <div className="grid md:grid-cols-3 gap-5">
          {[
            {
              icon: TrendingUp,
              value: "1,000x",
              label: "LLM cost decline in 3 years",
              detail: "GPT-4 equivalent: $20/M tokens → $0.40. Accelerating to 200x/yr post-2024",
            },
            {
              icon: DollarSign,
              value: "$155B",
              label: "Healthcare AI agent opportunity",
              detail: "PitchBook 2025 — poised to alleviate $300B+ in annual admin waste",
            },
            {
              icon: Rocket,
              value: "80%",
              label: "Clinical data is unstructured",
              detail: "Physician notes, radiology reports, path reports — invisible to AI until normalized",
            },
          ].map((stat, i) => {
            const Icon = stat.icon;
            return (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={VIEWPORT}
                transition={{
                  duration: 0.5,
                  delay: i * 0.08,
                  ease: EASE,
                }}
              >
                <div className="h-full rounded-2xl border border-neutral-200 bg-white p-7">
                  <div className="h-10 w-10 rounded-xl bg-neutral-100 flex items-center justify-center mb-4">
                    <Icon className="h-5 w-5 text-neutral-600" />
                  </div>
                  <div className="text-[2rem] font-bold tracking-[-0.04em] text-neutral-900 mb-1">
                    {stat.value}
                  </div>
                  <div className="text-[14px] font-semibold text-neutral-900 mb-2">
                    {stat.label}
                  </div>
                  <p className="text-[13px] text-neutral-500">{stat.detail}</p>
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
// WHY NOW — converging forces
// ============================================================================
function WhyNowSection() {
  const forces = [
    {
      icon: Scale,
      title: "Regulatory Mandate",
      items: [
        "Texas AG sues Epic (Dec 2025) — alleging illegal monopoly over health data",
        "TEFCA enforcement started Jan 2025 — nationwide interoperability floor",
        "CMS mandating FHIR-based patient access APIs across all payers",
        "ONC requiring USCDI v3 — EHR vendors must open data or face penalties",
      ],
    },
    {
      icon: Brain,
      title: "AI Cost + Capability Inflection",
      items: [
        "LLM inference costs: 1,000x cheaper in 3 years (200x/yr post-2024)",
        "Processing a full patient chart: enterprise project → pennies per doc",
        "NLP in healthcare: $5B → $16-37B by 2030 (25-35% CAGR)",
        "First time it's economically viable to normalize ALL legacy clinical data",
      ],
    },
    {
      icon: Building2,
      title: "Agentic AI Demand",
      items: [
        "PitchBook: healthcare AI agents = $155B annual revenue opportunity",
        "Agentic AI in healthcare growing 40-45% annually, $10.8B by 2032",
        "Microsoft, Oracle, IQVIA all building agentic healthcare layers",
        "Every agent needs clean, normalized data — that's the bottleneck",
      ],
    },
  ];

  return (
    <section className="py-32 md:py-44 px-6 bg-white dot-grid">
      <div className="max-w-[1200px] mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
          className="text-center mb-20"
        >
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-4">
            Why Now
          </p>
          <h2 className="text-[2rem] md:text-[3.25rem] font-semibold tracking-[-0.04em] text-neutral-900 leading-[1.05]">
            Three forces converging.
          </h2>
          <p className="mt-5 text-neutral-500 max-w-lg mx-auto text-[16px] leading-relaxed">
            Regulatory mandates, AI maturity, and enterprise demand are creating an unprecedented window for clinical data infrastructure.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-5">
          {forces.map((force, i) => {
            const Icon = force.icon;
            return (
              <motion.div
                key={force.title}
                initial={{ opacity: 0, y: 24, filter: "blur(4px)" }}
                whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                viewport={VIEWPORT}
                transition={{
                  duration: 0.5,
                  delay: i * 0.08,
                  ease: EASE,
                }}
              >
                <TiltCard>
                  <div className="h-full rounded-2xl border border-neutral-200 bg-white p-7 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] transition-shadow">
                    <div className="h-10 w-10 rounded-xl bg-neutral-900 flex items-center justify-center mb-6">
                      <Icon className="h-5 w-5 text-white" />
                    </div>
                    <h3 className="font-semibold text-[18px] tracking-[-0.02em] text-neutral-900 mb-5">
                      {force.title}
                    </h3>
                    <div className="space-y-3">
                      {force.items.map((item) => (
                        <div key={item} className="flex items-start gap-2.5">
                          <CheckCircle2 className="h-3.5 w-3.5 text-indigo-500 mt-0.5 flex-shrink-0" />
                          <span className="text-[13px] text-neutral-600 leading-snug">
                            {item}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </TiltCard>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// WHAT WE BUILT — the pipeline
// ============================================================================
function SolutionSection() {
  const steps = [
    {
      num: "01",
      icon: FileText,
      title: "Ingest",
      description: "Raw clinical notes, discharge summaries, pathology reports — any unstructured clinical text.",
    },
    {
      num: "02",
      icon: Brain,
      title: "Extract",
      description: "Clinical NLP with assertion detection, negation, temporality, and experiencer classification.",
    },
    {
      num: "03",
      icon: Database,
      title: "Normalize",
      description: "Map to UMLS, OMOP CDM, SNOMED, ICD-10, RxNorm, LOINC — full Metathesaurus coverage.",
    },
    {
      num: "04",
      icon: GitBranch,
      title: "Connect",
      description: "Build patient-centric knowledge graphs with clinical relationships, drug interactions, and lab trajectories.",
    },
    {
      num: "05",
      icon: Globe,
      title: "Export",
      description: "Query via API, export as FHIR R4 bundles, or feed directly into analytics and AI systems.",
    },
  ];

  return (
    <section className="py-32 md:py-44 px-6 bg-neutral-950 relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(99,102,241,0.06),transparent_70%)]" />
      <div className="max-w-[1200px] mx-auto relative">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
          className="text-center mb-20"
        >
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-500 mb-4">
            What We Built
          </p>
          <h2 className="text-[2rem] md:text-[3.25rem] font-semibold tracking-[-0.04em] text-white leading-[1.05]">
            Raw text in. Knowledge graph out.
          </h2>
          <p className="mt-5 text-neutral-400 max-w-lg mx-auto text-[16px] leading-relaxed">
            The first end-to-end clinical ontology normalization platform. One API call from unstructured clinical text to a queryable, OMOP-normalized knowledge graph.
          </p>
        </motion.div>

        <div className="relative">
          {/* Animated connecting line with flowing dots */}
          <div className="hidden md:block absolute top-[52px] left-[10%] right-[10%] h-[2px] z-0">
            <div className="absolute inset-0 bg-gradient-to-r from-indigo-500/20 via-violet-500/20 to-purple-500/20 rounded-full" />
            {[0, 0.8, 1.6].map((delay, di) => (
              <motion.div
                key={di}
                className="absolute top-[-2px] h-[6px] w-[6px] rounded-full bg-indigo-400 shadow-[0_0_8px_rgba(129,140,248,0.6)]"
                initial={{ left: "0%", opacity: 0 }}
                animate={{ left: ["0%", "100%"], opacity: [0, 1, 1, 0] }}
                transition={{ duration: 3, delay, repeat: Infinity, ease: "linear" }}
              />
            ))}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 relative z-10">
            {steps.map((step, i) => {
              const Icon = step.icon;
              const colors = [
                "from-indigo-500/20 to-indigo-500/5",
                "from-violet-500/20 to-violet-500/5",
                "from-purple-500/20 to-purple-500/5",
                "from-fuchsia-500/20 to-fuchsia-500/5",
                "from-pink-500/20 to-pink-500/5",
              ];
              const iconColors = [
                "text-indigo-400",
                "text-violet-400",
                "text-purple-400",
                "text-fuchsia-400",
                "text-pink-400",
              ];
              return (
                <motion.div
                  key={step.title}
                  initial={{ opacity: 0, y: 24, filter: "blur(4px)" }}
                  whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                  viewport={VIEWPORT}
                  transition={{
                    duration: 0.5,
                    delay: i * 0.1,
                    ease: EASE,
                  }}
                >
                  <TiltCard className="h-full">
                    <div className="relative rounded-xl border border-white/[0.08] bg-gradient-to-b bg-white/[0.02] p-5 hover:bg-white/[0.05] transition-all hover:border-white/[0.12] h-full group gradient-border">
                      <div className="text-[10px] font-mono text-indigo-400/40 mb-3">
                        {step.num}
                      </div>
                      <div className={`h-10 w-10 rounded-xl bg-gradient-to-br ${colors[i]} flex items-center justify-center mb-3 group-hover:scale-110 transition-transform`}>
                        <Icon className={`h-5 w-5 ${iconColors[i]}`} />
                      </div>
                      <h3 className="text-[15px] font-semibold text-white mb-2">
                        {step.title}
                      </h3>
                      <p className="text-[12px] text-white/40 leading-relaxed">
                        {step.description}
                      </p>
                    </div>
                  </TiltCard>
                </motion.div>
              );
            })}
          </div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, delay: 0.3, ease: EASE }}
          className="mt-16 text-center"
        >
          <p className="text-[14px] text-white/30 max-w-[600px] mx-auto">
            No existing product does this end-to-end. AWS and Google stop at extraction. John Snow Labs gives you components to assemble. We productize the entire pipeline.
          </p>
        </motion.div>
      </div>
    </section>
  );
}

// ============================================================================
// PRODUCT IN PRODUCTION — screenshot showcase + demo video
// ============================================================================
function ProductShowcase() {
  const heroScreenshots = [
    {
      src: "/investors/extraction-demo.png",
      title: "NLP Entity Extraction",
      stat: "828 entities extracted",
      description: "Raw clinical note in, structured entities out — diagnoses, medications, procedures, measurements mapped to OMOP, SNOMED, and RxNorm at 90%+ confidence.",
    },
    {
      src: "/investors/kg-demo.png",
      title: "Patient Knowledge Graph",
      stat: "298 nodes · 1,011 edges",
      description: "Interactive D3.js visualization with temporal filtering, node provenance, assertion tracking, and multi-hop relationship traversal.",
    },
    {
      src: "/investors/agent-demo.png",
      title: "Clinical Q&A Agent",
      stat: "Multi-step reasoning in <300ms",
      description: "Knowledge graph retrieval → LLM reasoning → RAG guideline search → multi-agent deliberation — clinical intelligence on demand.",
    },
  ];

  const productGrid = [
    { src: "/investors/vocab.png", title: "10 Vocabularies", subtitle: "5M+ concepts with auto-update scheduling", stat: "5,432,246 concepts" },
    { src: "/investors/calculators.png", title: "210 Calculators", subtitle: "Validated clinical tools across 15 domains", stat: "15 clinical domains" },
    { src: "/investors/guidelines.png", title: "733 Guidelines", subtitle: "Evidence-graded with semantic search", stat: "875 Grade A evidence" },
    { src: "/investors/pathways.png", title: "Care Pathways", subtitle: "Drug-gene-protein-disease relationships", stat: "95% confidence scoring" },
  ];

  return (
    <section className="py-32 md:py-44 px-6 bg-neutral-950 relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(99,102,241,0.06),transparent_50%),radial-gradient(ellipse_at_bottom_right,rgba(168,85,247,0.04),transparent_50%)]" />
      <div className="max-w-[1200px] mx-auto relative">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
          className="text-center mb-20"
        >
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-indigo-400/60 mb-4">
            Product in Production
          </p>
          <h2 className="text-[2rem] md:text-[3.25rem] font-semibold tracking-[-0.04em] text-white leading-[1.05]">
            Not a prototype.{" "}
            <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-indigo-400 bg-clip-text text-transparent">
              Not a slide deck.
            </span>
          </h2>
          <p className="mt-5 text-white/40 max-w-lg mx-auto text-[16px] leading-relaxed">
            Everything below is running today — built, shipped, and processing real clinical data. One engineer. Six months.
          </p>
        </motion.div>

        {/* Demo video embed */}
        <motion.div
          initial={{ opacity: 0, y: 24, filter: "blur(4px)" }}
          whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          viewport={VIEWPORT}
          transition={{ duration: 0.6, ease: EASE }}
          className="mb-20"
        >
          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] overflow-hidden gradient-border">
            {/* Browser chrome */}
            <div className="flex items-center gap-2 px-4 py-3 border-b border-white/[0.06] bg-white/[0.02]">
              <div className="flex gap-1.5">
                <div className="h-2.5 w-2.5 rounded-full bg-white/[0.08]" />
                <div className="h-2.5 w-2.5 rounded-full bg-white/[0.08]" />
                <div className="h-2.5 w-2.5 rounded-full bg-white/[0.08]" />
              </div>
              <div className="flex-1 mx-4">
                <div className="h-6 rounded-md bg-white/[0.04] flex items-center px-3">
                  <span className="text-[11px] text-white/20 font-mono">localhost:3000</span>
                </div>
              </div>
            </div>
            {/* Video */}
            <div className="relative aspect-video bg-neutral-900">
              <video
                autoPlay
                loop
                muted
                playsInline
                className="w-full h-full object-cover"
              >
                <source src="/demo.mp4" type="video/mp4" />
              </video>
            </div>
          </div>
          <div className="mt-6 flex items-center justify-center gap-4">
            <a
              href="#"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/[0.06] border border-white/[0.08] text-[13px] font-medium text-white/60 hover:text-white hover:bg-white/[0.1] transition-all"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3" /></svg>
              Watch Full Walkthrough
            </a>
            <span className="text-[12px] text-white/20">4 min · Product demo</span>
          </div>
        </motion.div>

        {/* Hero screenshots — walkthrough series */}
        <div className="space-y-8 mb-20">
          {heroScreenshots.map((item, i) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 24, filter: "blur(4px)" }}
              whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              viewport={VIEWPORT}
              transition={{ duration: 0.6, delay: i * 0.08, ease: EASE }}
            >
              <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] overflow-hidden hover:border-white/[0.12] transition-colors">
                {/* Browser chrome */}
                <div className="flex items-center gap-2 px-4 py-3 border-b border-white/[0.06] bg-white/[0.02]">
                  <div className="flex gap-1.5">
                    <div className="h-2.5 w-2.5 rounded-full bg-white/[0.08]" />
                    <div className="h-2.5 w-2.5 rounded-full bg-white/[0.08]" />
                    <div className="h-2.5 w-2.5 rounded-full bg-white/[0.08]" />
                  </div>
                  <div className="flex-1 mx-4">
                    <div className="h-6 rounded-md bg-white/[0.04] flex items-center px-3">
                      <span className="text-[11px] text-white/20 font-mono">Clinical ONT — {item.title}</span>
                    </div>
                  </div>
                </div>
                {/* Screenshot */}
                <div className="relative bg-neutral-900">
                  <img
                    src={item.src}
                    alt={item.title}
                    className="w-full h-auto block"
                    loading="lazy"
                  />
                </div>
                {/* Caption bar */}
                <div className="px-6 py-5 border-t border-white/[0.06] bg-white/[0.02]">
                  <div className="flex flex-col md:flex-row md:items-center gap-3 md:gap-6">
                    <div className="flex-1">
                      <h3 className="text-[16px] font-semibold text-white mb-1">{item.title}</h3>
                      <p className="text-[13px] text-white/40 leading-relaxed">{item.description}</p>
                    </div>
                    <div className="flex-shrink-0">
                      <span className="inline-flex items-center px-3 py-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-[12px] font-semibold text-indigo-300">
                        {item.stat}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Product feature grid */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
          className="mb-8"
        >
          <h3 className="text-[18px] font-semibold text-white text-center mb-2">Platform depth</h3>
          <p className="text-[14px] text-white/30 text-center mb-10">Built-in clinical intelligence, not bolted on.</p>
        </motion.div>

        <div className="grid md:grid-cols-2 gap-4">
          {productGrid.map((feature, i) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 20, filter: "blur(4px)" }}
              whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              viewport={VIEWPORT}
              transition={{ duration: 0.5, delay: i * 0.06, ease: EASE }}
            >
              <TiltCard className="h-full">
                <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] overflow-hidden hover:border-white/[0.12] transition-colors h-full">
                  {/* Mini browser chrome */}
                  <div className="flex items-center gap-1.5 px-3 py-2 border-b border-white/[0.06] bg-white/[0.02]">
                    <div className="flex gap-1">
                      <div className="h-2 w-2 rounded-full bg-white/[0.06]" />
                      <div className="h-2 w-2 rounded-full bg-white/[0.06]" />
                      <div className="h-2 w-2 rounded-full bg-white/[0.06]" />
                    </div>
                  </div>
                  {/* Screenshot */}
                  <div className="relative bg-neutral-900">
                    <img
                      src={feature.src}
                      alt={feature.title}
                      className="w-full h-auto block"
                      loading="lazy"
                    />
                  </div>
                  {/* Caption */}
                  <div className="px-5 py-4 border-t border-white/[0.06]">
                    <div className="flex items-center justify-between mb-1">
                      <h4 className="text-[14px] font-semibold text-white">{feature.title}</h4>
                      <span className="text-[11px] font-medium text-indigo-400">{feature.stat}</span>
                    </div>
                    <p className="text-[12px] text-white/35">{feature.subtitle}</p>
                  </div>
                </div>
              </TiltCard>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// COMPETITIVE LANDSCAPE — the gap
// ============================================================================
function CompetitiveLandscape() {
  const competitors = [
    { name: "AWS Comprehend Medical", extract: "partial", normalize: "partial", graph: false, e2e: false },
    { name: "Google Cloud Healthcare", extract: "partial", normalize: "partial", graph: false, e2e: false },
    { name: "John Snow Labs", extract: true, normalize: "partial", graph: false, e2e: false },
    { name: "IMO Health", extract: "partial", normalize: true, graph: false, e2e: false },
    { name: "Tempus / Flatiron", extract: "internal", normalize: "internal", graph: false, e2e: false },
    { name: "Sulci", extract: true, normalize: true, graph: true, e2e: true },
  ];

  const renderCell = (val: boolean | string) => {
    if (val === true)
      return (
        <div className="h-5 w-5 rounded-full bg-emerald-50 flex items-center justify-center">
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
        </div>
      );
    if (val === "partial")
      return (
        <div className="h-5 w-5 rounded-full bg-amber-50 flex items-center justify-center">
          <CircleDot className="h-3 w-3 text-amber-500" />
        </div>
      );
    if (val === "internal")
      return (
        <span className="text-[10px] font-medium text-neutral-400 bg-neutral-100 px-1.5 py-0.5 rounded">
          Internal
        </span>
      );
    return (
      <div className="h-5 w-5 rounded-full bg-neutral-100 flex items-center justify-center">
        <X className="h-3 w-3 text-neutral-300" />
      </div>
    );
  };

  return (
    <section className="py-32 md:py-44 px-6 bg-neutral-50 dot-grid">
      <div className="max-w-[1000px] mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
          className="mb-16"
        >
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-4">
            Competitive Landscape
          </p>
          <h2 className="text-[2rem] md:text-[3rem] font-semibold tracking-[-0.04em] text-neutral-900 leading-[1.05]">
            Nobody does end-to-end.
          </h2>
          <p className="mt-4 text-neutral-500 max-w-lg text-[16px] leading-relaxed">
            Cloud providers stop at extraction. Terminology companies stop at mapping. Data platforms rely on manual curation. Sulci is the first to productize the full pipeline.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
        >
          <div className="rounded-2xl border border-neutral-200 bg-white overflow-hidden shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-neutral-100">
                    <th className="text-left px-5 py-4 text-[12px] font-semibold text-neutral-400 uppercase tracking-wider">
                      Platform
                    </th>
                    <th className="px-5 py-4 text-[12px] font-semibold text-neutral-400 uppercase tracking-wider text-center">
                      NLP Extract
                    </th>
                    <th className="px-5 py-4 text-[12px] font-semibold text-neutral-400 uppercase tracking-wider text-center">
                      Ontology Map
                    </th>
                    <th className="px-5 py-4 text-[12px] font-semibold text-neutral-400 uppercase tracking-wider text-center">
                      Knowledge Graph
                    </th>
                    <th className="px-5 py-4 text-[12px] font-semibold text-neutral-400 uppercase tracking-wider text-center">
                      End-to-End
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {competitors.map((c, i) => (
                    <tr
                      key={c.name}
                      className={`border-b border-neutral-50 ${
                        c.name === "Sulci"
                          ? "bg-indigo-50/50"
                          : i % 2 === 0
                          ? "bg-white"
                          : "bg-neutral-50/30"
                      }`}
                    >
                      <td className="px-5 py-3.5">
                        <span
                          className={`font-medium ${
                            c.name === "Sulci"
                              ? "text-indigo-600"
                              : "text-neutral-900"
                          }`}
                        >
                          {c.name}
                        </span>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex justify-center">
                          {renderCell(c.extract)}
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex justify-center">
                          {renderCell(c.normalize)}
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex justify-center">
                          {renderCell(c.graph)}
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex justify-center">
                          {renderCell(c.e2e)}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, delay: 0.2, ease: EASE }}
          className="mt-8 grid md:grid-cols-2 gap-4"
        >
          <div className="rounded-xl border border-neutral-200 bg-white p-5">
            <div className="text-[13px] font-semibold text-neutral-900 mb-2">
              The Snowflake analogy
            </div>
            <p className="text-[13px] text-neutral-500 leading-relaxed">
              Snowflake didn&apos;t compete with AWS S3 — it built the data warehouse on top. Sulci builds the clinical intelligence layer on top of cloud infrastructure. Partners, not competitors.
            </p>
          </div>
          <div className="rounded-xl border border-neutral-200 bg-white p-5">
            <div className="text-[13px] font-semibold text-neutral-900 mb-2">
              Why EHRs won&apos;t build this
            </div>
            <p className="text-[13px] text-neutral-500 leading-relaxed">
              EHR vendors optimize within their ecosystem — not cross-platform. Veradigm acquired ScienceIO for $140M because even EHR companies recognize they can&apos;t build clinical NLP internally.
            </p>
          </div>
        </motion.div>

        <CompetitiveRadar />
      </div>
    </section>
  );
}

// ============================================================================
// GO-TO-MARKET WEDGE
// ============================================================================
function WedgeSection() {
  return (
    <section className="py-32 md:py-44 px-6 bg-white dot-grid">
      <div className="max-w-[1200px] mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
          className="mb-16"
        >
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-4">
            Go-to-Market
          </p>
          <h2 className="text-[2rem] md:text-[3rem] font-semibold tracking-[-0.04em] text-neutral-900 leading-[1.05]">
            Wedge in, expand out.
          </h2>
        </motion.div>

        <div className="grid md:grid-cols-2 gap-8 md:gap-12">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={VIEWPORT}
            transition={{ duration: 0.5, ease: EASE }}
          >
            <div className="space-y-5">
              <div className="rounded-2xl border-2 border-indigo-200 bg-indigo-50/30 p-7">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-10 w-10 rounded-xl bg-indigo-600 flex items-center justify-center">
                    <Microscope className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-[16px] text-neutral-900">
                      Primary: Life Sciences / Pharma
                    </h3>
                    <p className="text-[12px] text-neutral-500">
                      Highest urgency, clearest ROI
                    </p>
                  </div>
                </div>
                <div className="space-y-2 text-[13px] text-neutral-600">
                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-indigo-500 mt-0.5 flex-shrink-0" />
                    <span>$1-5M per study on manual chart abstraction</span>
                  </div>
                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-indigo-500 mt-0.5 flex-shrink-0" />
                    <span>Need OMOP-normalized data for FDA real-world evidence submissions</span>
                  </div>
                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-indigo-500 mt-0.5 flex-shrink-0" />
                    <span>Shorter sales cycles than health systems (months, not years)</span>
                  </div>
                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-indigo-500 mt-0.5 flex-shrink-0" />
                    <span>CROs, HEOR teams, mid-size pharma (top 20-50)</span>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-neutral-200 bg-white p-7">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-10 w-10 rounded-xl bg-neutral-900 flex items-center justify-center">
                    <Building2 className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-[16px] text-neutral-900">
                      Secondary: OHDSI / OMOP Health Systems
                    </h3>
                    <p className="text-[12px] text-neutral-500">
                      Growing network, strong pull
                    </p>
                  </div>
                </div>
                <div className="space-y-2 text-[13px] text-neutral-600">
                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-neutral-400 mt-0.5 flex-shrink-0" />
                    <span>4,200+ OHDSI collaborators across 83 countries</span>
                  </div>
                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-neutral-400 mt-0.5 flex-shrink-0" />
                    <span>Multi-year, multi-million dollar OMOP conversion challenges</span>
                  </div>
                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-neutral-400 mt-0.5 flex-shrink-0" />
                    <span>Academic medical centers with active research mandates</span>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={VIEWPORT}
            transition={{ duration: 0.5, delay: 0.1, ease: EASE }}
          >
            <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-7 h-full">
              <h3 className="font-semibold text-[16px] text-neutral-900 mb-6">
                Land-and-Expand Model
              </h3>
              <div className="space-y-6">
                {[
                  {
                    stage: "Land",
                    value: "$50-100K",
                    detail: "Single-indication pilot — e.g., normalize oncology notes for an RWE study",
                  },
                  {
                    stage: "Expand Horizontal",
                    value: "$200-500K",
                    detail: "Multi-department: cardiology, neurology, endocrinology — one therapeutic area at a time",
                  },
                  {
                    stage: "Expand Vertical",
                    value: "$500K-1M+",
                    detail: "Knowledge graph layer for patient journey analytics, cohort discovery, clinical decision support",
                  },
                  {
                    stage: "Platform",
                    value: "$1M+",
                    detail: "Normalization middleware between EHRs and analytics — integrated via FHIR and OMOP APIs",
                  },
                ].map((s, i) => (
                  <div key={s.stage} className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className="h-8 w-8 rounded-full bg-white border-2 border-neutral-300 flex items-center justify-center text-[11px] font-bold text-neutral-600 flex-shrink-0">
                        {i + 1}
                      </div>
                      {i < 3 && (
                        <div className="w-px flex-1 bg-neutral-200 mt-2" />
                      )}
                    </div>
                    <div className="pb-4">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[14px] font-semibold text-neutral-900">
                          {s.stage}
                        </span>
                        <span className="text-[12px] font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">
                          {s.value}
                        </span>
                      </div>
                      <p className="text-[13px] text-neutral-500 leading-relaxed">
                        {s.detail}
                      </p>
                    </div>
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
// 5-YEAR ROADMAP
// ============================================================================
function RoadmapSection() {
  const years = [
    {
      year: "Year 1",
      stage: "Seed",
      color: "bg-indigo-500",
      arr: "$200-500K",
      customers: "3-5 pilots",
      team: "5-10",
      milestones: [
        "Core NLP + OMOP mapping pipeline production-ready",
        "API documented, first integrations live",
        "SOC 2 Type II initiated",
        "2-3 published case studies with measurable ROI",
      ],
    },
    {
      year: "Year 2",
      stage: "Series A",
      color: "bg-violet-500",
      arr: "$1.5-3M",
      customers: "10-20 paid",
      team: "20-30",
      milestones: [
        "Full OMOP CDM coverage across major clinical domains",
        "Knowledge graph operational with queryable API",
        "FHIR R4 bidirectional, first EHR integration (Epic)",
        "NRR >120%, pilot-to-paid >60%",
      ],
    },
    {
      year: "Year 3",
      stage: "Series B",
      color: "bg-purple-500",
      arr: "$8-15M",
      customers: "50+",
      team: "60-100",
      milestones: [
        "Pharma RWE data product launched",
        "Clinical trial matching module",
        "GraphRAG and clinical decision support layers",
        "FDA pre-submission (Q-Sub) if pursuing regulated pathway",
      ],
    },
    {
      year: "Year 4",
      stage: "Series C",
      color: "bg-fuchsia-500",
      arr: "$30-50M",
      customers: "150+",
      team: "100-150",
      milestones: [
        "International expansion (EU MDR, GDPR)",
        "Modular product suite — platform play",
        "Continuous learning / federated capabilities",
        "Path to profitability visible",
      ],
    },
    {
      year: "Year 5",
      stage: "Pre-Exit",
      color: "bg-pink-500",
      arr: "$80-100M+",
      customers: "200+",
      team: "150-200",
      milestones: [
        "Platform dominance in clinical data normalization",
        "Gross margins 75%+, Rule of 40 score >60",
        "Exit path: IPO or strategic acquisition",
        "Comparables: Flatiron ($1.9B), Tempus ($6B+), Commure ($6B)",
      ],
    },
  ];

  return (
    <section className="py-32 md:py-44 px-6 bg-neutral-950 relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom,rgba(99,102,241,0.06),transparent_70%)]" />
      <div className="max-w-[1200px] mx-auto relative">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
          className="text-center mb-20"
        >
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-500 mb-4">
            5-Year Roadmap
          </p>
          <h2 className="text-[2rem] md:text-[3.25rem] font-semibold tracking-[-0.04em] text-white leading-[1.05]">
            Seed to $100M ARR.
          </h2>
          <p className="mt-5 text-neutral-400 max-w-lg mx-auto text-[16px] leading-relaxed">
            Bessemer documents that health AI companies are hitting $100M ARR in under 5 years. Here&apos;s our path.
          </p>
        </motion.div>

        <ARRGrowthChart />

        <div className="space-y-4">
          {years.map((yr, i) => (
            <motion.div
              key={yr.year}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={VIEWPORT}
              transition={{ duration: 0.5, delay: i * 0.06, ease: EASE }}
            >
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04] transition-colors overflow-hidden">
                <div className="p-6 md:p-7">
                  <div className="flex flex-col md:flex-row md:items-start gap-5">
                    <div className="flex items-center gap-3 md:w-[160px] flex-shrink-0">
                      <div
                        className={`h-3 w-3 rounded-full ${yr.color}`}
                      />
                      <div>
                        <div className="text-[16px] font-semibold text-white">
                          {yr.year}
                        </div>
                        <div className="text-[12px] text-white/30">
                          {yr.stage}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 md:gap-6 md:w-[240px] flex-shrink-0">
                      <div>
                        <div className="text-[11px] text-white/20 uppercase tracking-wider mb-0.5">
                          ARR
                        </div>
                        <div className="text-[15px] font-semibold text-white tabular-nums">
                          {yr.arr}
                        </div>
                      </div>
                      <div>
                        <div className="text-[11px] text-white/20 uppercase tracking-wider mb-0.5">
                          Customers
                        </div>
                        <div className="text-[15px] font-semibold text-white tabular-nums">
                          {yr.customers}
                        </div>
                      </div>
                      <div>
                        <div className="text-[11px] text-white/20 uppercase tracking-wider mb-0.5">
                          Team
                        </div>
                        <div className="text-[15px] font-semibold text-white tabular-nums">
                          {yr.team}
                        </div>
                      </div>
                    </div>

                    <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {yr.milestones.map((m) => (
                        <div
                          key={m}
                          className="flex items-start gap-2"
                        >
                          <ChevronRight className="h-3 w-3 text-white/20 mt-0.5 flex-shrink-0" />
                          <span className="text-[12px] text-white/50 leading-snug">
                            {m}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
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
// DEFENSIBILITY
// ============================================================================
function DefensibilitySection() {
  const moats = [
    {
      icon: Layers,
      title: "Ontology Coverage",
      description:
        "Comprehensive mappings across UMLS, OMOP, SNOMED, ICD-10, RxNorm, LOINC. Each deployment surfaces edge cases that improve quality. Compounding advantage over time.",
    },
    {
      icon: Activity,
      title: "Data Flywheel",
      description:
        "Every document processed trains better extraction models. Every new clinical domain mapped compounds the ontology. More customers = better accuracy = more customers.",
    },
    {
      icon: Network,
      title: "Integration Moat",
      description:
        "Once embedded in a customer's data pipeline — EHR connectors, FHIR endpoints, OMOP CDM — switching costs are high. Downstream analytics depend on our mappings.",
    },
    {
      icon: Shield,
      title: "Regulatory Moat",
      description:
        "Validated pipelines for FDA submissions take 6-12 months to re-validate. SOC 2, HIPAA, BAA, 21 CFR Part 11 — each certification is a barrier competitors must clear.",
    },
    {
      icon: GitBranch,
      title: "Knowledge Graph Architecture",
      description:
        "The end-to-end pipeline from text to knowledge graph is architecturally novel. No competitor offers this today. The graph schema and clinical reasoning capabilities are the product.",
    },
  ];

  return (
    <section className="py-32 md:py-44 px-6 bg-white dot-grid">
      <div className="max-w-[1200px] mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
          className="text-center mb-20"
        >
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-4">
            Defensibility
          </p>
          <h2 className="text-[2rem] md:text-[3.25rem] font-semibold tracking-[-0.04em] leading-[1.05]">
            <span className="bg-gradient-to-r from-neutral-900 via-neutral-800 to-neutral-900 bg-clip-text text-transparent">Five compounding moats.</span>
          </h2>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-5">
          {moats.slice(0, 3).map((moat, i) => {
            const Icon = moat.icon;
            return (
              <motion.div
                key={moat.title}
                initial={{ opacity: 0, y: 24, filter: "blur(4px)" }}
                whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                viewport={VIEWPORT}
                transition={{
                  duration: 0.5,
                  delay: i * 0.08,
                  ease: EASE,
                }}
              >
                <TiltCard>
                  <div className="h-full rounded-2xl border border-neutral-200 bg-white p-7 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] transition-shadow">
                    <div className="h-10 w-10 rounded-xl bg-neutral-900 flex items-center justify-center mb-5">
                      <Icon className="h-5 w-5 text-white" />
                    </div>
                    <h3 className="font-semibold text-[16px] tracking-[-0.01em] text-neutral-900 mb-3">
                      {moat.title}
                    </h3>
                    <p className="text-[14px] text-neutral-500 leading-relaxed">
                      {moat.description}
                    </p>
                  </div>
                </TiltCard>
              </motion.div>
            );
          })}
        </div>
        <div className="grid md:grid-cols-2 gap-5 mt-5">
          {moats.slice(3).map((moat, i) => {
            const Icon = moat.icon;
            return (
              <motion.div
                key={moat.title}
                initial={{ opacity: 0, y: 24, filter: "blur(4px)" }}
                whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                viewport={VIEWPORT}
                transition={{
                  duration: 0.5,
                  delay: (i + 3) * 0.08,
                  ease: EASE,
                }}
              >
                <TiltCard>
                  <div className="h-full rounded-2xl border border-neutral-200 bg-white p-7 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] transition-shadow">
                    <div className="h-10 w-10 rounded-xl bg-neutral-900 flex items-center justify-center mb-5">
                      <Icon className="h-5 w-5 text-white" />
                    </div>
                    <h3 className="font-semibold text-[16px] tracking-[-0.01em] text-neutral-900 mb-3">
                      {moat.title}
                    </h3>
                    <p className="text-[14px] text-neutral-500 leading-relaxed">
                      {moat.description}
                    </p>
                  </div>
                </TiltCard>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// DATA FLYWHEEL — compound advantage
// ============================================================================
function FlywheelSection() {
  const stages = [
    { label: "More Data\nNormalized", icon: Database, color: "text-indigo-400", bg: "bg-indigo-500/15", border: "border-indigo-500/30" },
    { label: "Better NLP\nModels", icon: Brain, color: "text-violet-400", bg: "bg-violet-500/15", border: "border-violet-500/30" },
    { label: "Higher Accuracy\nMapping", icon: Target, color: "text-purple-400", bg: "bg-purple-500/15", border: "border-purple-500/30" },
    { label: "More Clinical\nInsights", icon: Activity, color: "text-fuchsia-400", bg: "bg-fuchsia-500/15", border: "border-fuchsia-500/30" },
    { label: "More\nCustomers", icon: Users, color: "text-pink-400", bg: "bg-pink-500/15", border: "border-pink-500/30" },
  ];

  return (
    <section className="py-32 md:py-44 px-6 bg-neutral-950 relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(139,92,246,0.08),transparent_60%)]" />
      <FloatingParticles count={12} />
      <div className="max-w-[1200px] mx-auto relative">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
          className="text-center mb-16"
        >
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-violet-400/60 mb-4">
            The Flywheel
          </p>
          <h2 className="text-[2rem] md:text-[3.25rem] font-semibold tracking-[-0.04em] text-white leading-[1.05]">
            Data compounds.
            <br />
            <span className="bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent">
              So does the moat.
            </span>
          </h2>
          <p className="mt-5 text-white/40 max-w-xl mx-auto text-[16px] leading-relaxed">
            Every document normalized improves the models. Every clinical domain mapped compounds the ontology. Each customer makes the system smarter for all customers.
          </p>
        </motion.div>

        {/* Flywheel diagram */}
        <div className="max-w-[700px] mx-auto mb-16">
          <div className="relative">
            {/* Center hub */}
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, ease: EASE }}
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10"
            >
              <div className="h-24 w-24 md:h-28 md:w-28 rounded-full bg-gradient-to-br from-indigo-500/20 to-violet-500/20 border border-white/[0.12] flex items-center justify-center backdrop-blur-sm gradient-border">
                <div className="text-center">
                  <Brain className="h-6 w-6 text-white mx-auto mb-1" />
                  <span className="text-[10px] font-bold text-white/70 uppercase tracking-wider">Sulci</span>
                </div>
              </div>
            </motion.div>

            {/* Ring of stages */}
            <div className="relative w-full aspect-square max-w-[500px] mx-auto">
              {stages.map((stage, i) => {
                const angle = (i * 360) / stages.length - 90;
                const rad = (angle * Math.PI) / 180;
                const radius = 42;
                const x = 50 + radius * Math.cos(rad);
                const y = 50 + radius * Math.sin(rad);
                const Icon = stage.icon;
                return (
                  <motion.div
                    key={stage.label}
                    initial={{ opacity: 0, scale: 0.5 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.4, delay: 0.2 + i * 0.1, ease: EASE }}
                    className="absolute -translate-x-1/2 -translate-y-1/2"
                    style={{ left: `${x}%`, top: `${y}%` }}
                  >
                    <div className={`flex flex-col items-center gap-2 px-3 py-3 md:px-5 md:py-4 rounded-xl ${stage.bg} border ${stage.border} backdrop-blur-sm`}>
                      <Icon className={`h-5 w-5 ${stage.color}`} />
                      <span className={`text-[10px] md:text-[11px] font-semibold ${stage.color} text-center whitespace-pre-line leading-tight`}>
                        {stage.label}
                      </span>
                    </div>
                  </motion.div>
                );
              })}

              {/* Animated rotating ring */}
              <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100">
                <motion.circle
                  cx="50" cy="50" r="32"
                  fill="none"
                  stroke="url(#flywheel-gradient)"
                  strokeWidth="0.3"
                  strokeDasharray="8 4"
                  initial={{ rotate: 0 }}
                  animate={{ rotate: 360 }}
                  transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                  style={{ transformOrigin: "50px 50px" }}
                />
                <defs>
                  <linearGradient id="flywheel-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="rgba(129,140,248,0.5)" />
                    <stop offset="50%" stopColor="rgba(168,85,247,0.5)" />
                    <stop offset="100%" stopColor="rgba(232,121,249,0.5)" />
                  </linearGradient>
                </defs>
              </svg>
            </div>
          </div>
        </div>

        {/* The Snowflake Moment callout */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, delay: 0.2, ease: EASE }}
          className="grid md:grid-cols-2 gap-5"
        >
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-7">
            <div className="text-[14px] font-semibold text-white mb-3">
              The Snowflake Moment for Healthcare
            </div>
            <p className="text-[13px] text-white/40 leading-relaxed mb-4">
              Snowflake didn&apos;t compete with AWS S3 — it built the data warehouse on top. Sulci builds the clinical intelligence layer on top of cloud infrastructure. Not the storage. Not the compute. The normalization layer that makes raw clinical data computable, queryable, and AI-ready.
            </p>
            <div className="flex items-center gap-3">
              <div className="text-[22px] font-bold text-white">$70B+</div>
              <div className="text-[11px] text-white/30">Snowflake market cap — from building the data layer</div>
            </div>
          </div>
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-7">
            <div className="text-[14px] font-semibold text-white mb-3">
              Why This Flywheel Is Especially Sticky
            </div>
            <div className="space-y-3">
              {[
                { label: "Domain-specific", detail: "Clinical ontologies are hard to replicate — years of medical knowledge encoded" },
                { label: "Safety-critical", detail: "Accuracy matters (patient safety = regulatory requirement), not just speed" },
                { label: "Network effects", detail: "Each customer's data improves mapping models for all customers" },
                { label: "Compounding graph", detail: "Switching costs increase with every document and relationship processed" },
              ].map((item) => (
                <div key={item.label} className="flex items-start gap-2.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-violet-400/60 mt-0.5 flex-shrink-0" />
                  <div>
                    <span className="text-[12px] font-semibold text-white/60">{item.label}: </span>
                    <span className="text-[12px] text-white/40">{item.detail}</span>
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
// TEAM WE NEED TO BUILD
// ============================================================================
function TeamSection() {
  const stages = [
    {
      stage: "Now → Seed",
      headcount: "5-10",
      roles: [
        "Founder / CEO (physician-engineer)",
        "2-3 senior ML/NLP engineers",
        "Clinical informaticist",
        "Business development lead",
      ],
      advisory: "2-3 health system CIOs/CMIOs, 1 pharma data leader",
    },
    {
      stage: "Series A",
      headcount: "20-30",
      roles: [
        "VP Engineering (distributed systems)",
        "Head of Sales (enterprise health IT)",
        "Clinical Lead / Medical Director",
        "Product Manager (healthcare workflows)",
        "DevOps / Security (HIPAA, SOC 2)",
        "Customer Success lead",
      ],
    },
    {
      stage: "Series B",
      headcount: "60-100",
      roles: [
        "Chief Medical Officer (former CMIO)",
        "VP Product + VP Sales",
        "4-6 enterprise AEs",
        "Data science research team (3-5)",
        "Regulatory / compliance officer",
        "Marketing (conferences, thought leadership)",
      ],
    },
    {
      stage: "Series C+",
      headcount: "100-200",
      roles: [
        "CFO (IPO-ready)",
        "Chief Commercial Officer",
        "International expansion leads",
        "Full go-to-market organization",
      ],
    },
  ];

  return (
    <section className="py-32 md:py-44 px-6 bg-neutral-50 dot-grid">
      <div className="max-w-[1200px] mx-auto">
        <div className="grid md:grid-cols-2 gap-12 md:gap-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={VIEWPORT}
            transition={{ duration: 0.5, ease: EASE }}
          >
            <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-4">
              Team
            </p>
            <h2 className="text-[2rem] md:text-[3rem] font-semibold tracking-[-0.04em] text-neutral-900 leading-[1.05] mb-5">
              Building the team to win.
            </h2>

            <div className="rounded-2xl border border-neutral-200 bg-white p-7 mb-5">
              <div className="flex items-start gap-4">
                <div className="h-14 w-14 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center flex-shrink-0 shadow-sm">
                  <span className="text-[16px] font-bold text-white">AS</span>
                </div>
                <div>
                  <h3 className="text-[16px] font-semibold text-neutral-900">
                    Alex Stinard, M.D.
                  </h3>
                  <p className="text-[13px] text-neutral-500 mb-3">
                    Founder & CEO
                  </p>
                  <div className="space-y-1.5 text-[13px] text-neutral-600">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-1.5 rounded-full bg-neutral-400" />
                      <span>
                        <strong>Commure</strong> — Clinical AI Architect, agentic ambient scribing at ~1% of U.S. visits
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-1.5 rounded-full bg-neutral-400" />
                      <span>
                        <strong>HCA Healthcare</strong> — Enterprise SME, Clinical Documentation (millions of ED visits)
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-1.5 rounded-full bg-neutral-400" />
                      <span>
                        <strong>Lake Monroe Hospital</strong> — Vice Chair of the Board
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-1.5 rounded-full bg-neutral-400" />
                      <span>
                        <strong>UCF</strong> — Asst. Professor, Emergency Medicine
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <p className="text-[14px] text-neutral-500 leading-relaxed">
              VCs cite the ideal founding profile as: practicing physician + technical AI depth + enterprise healthcare experience. Our founder checks all three — clinical authority from the ER, infrastructure expertise from Commure, and enterprise scale from HCA.
            </p>

            <div className="mt-5 flex flex-wrap gap-2">
              {[
                "Multi-Agent Systems",
                "Knowledge Graphs",
                "Ontology Design",
                "FHIR/HL7",
                "Safety & Red-Teaming",
                "CDI/DRG",
              ].map((tag) => (
                <span
                  key={tag}
                  className="px-2.5 py-1 text-[11px] font-medium rounded-lg bg-neutral-100 text-neutral-600 border border-neutral-200"
                >
                  {tag}
                </span>
              ))}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={VIEWPORT}
            transition={{ duration: 0.5, delay: 0.1, ease: EASE }}
          >
            <div className="space-y-4">
              {stages.map((s, i) => (
                <motion.div
                  key={s.stage}
                  initial={{ opacity: 0, y: 12 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={VIEWPORT}
                  transition={{
                    duration: 0.4,
                    delay: 0.15 + i * 0.06,
                    ease: EASE,
                  }}
                >
                  <div className="rounded-xl border border-neutral-200 bg-white p-5">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-[14px] font-semibold text-neutral-900">
                        {s.stage}
                      </span>
                      <span className="text-[12px] font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">
                        {s.headcount} people
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      {s.roles.map((role) => (
                        <div
                          key={role}
                          className="flex items-start gap-2"
                        >
                          <Users className="h-3 w-3 text-neutral-300 mt-0.5 flex-shrink-0" />
                          <span className="text-[13px] text-neutral-600">
                            {role}
                          </span>
                        </div>
                      ))}
                    </div>
                    {s.advisory && (
                      <div className="mt-3 pt-3 border-t border-neutral-100">
                        <span className="text-[11px] text-neutral-400">
                          Advisory: {s.advisory}
                        </span>
                      </div>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// UNIT ECONOMICS
// ============================================================================
function MetricsSection() {
  return (
    <section className="py-32 md:py-44 px-6 bg-white dot-grid">
      <div className="max-w-[1000px] mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
          className="text-center mb-16"
        >
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-neutral-400 mb-4">
            Target Metrics
          </p>
          <h2 className="text-[2rem] md:text-[3rem] font-semibold tracking-[-0.04em] text-neutral-900 leading-[1.05]">
            Built for software economics.
          </h2>
          <p className="mt-4 text-neutral-500 text-[16px] leading-relaxed">
            AI-services-as-software: service-level outcomes, software-level margins.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
        >
          <div className="rounded-2xl border border-neutral-200 bg-white overflow-hidden shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-neutral-100 bg-neutral-50/50">
                    <th className="text-left px-5 py-4 text-[12px] font-semibold text-neutral-400 uppercase tracking-wider">
                      Metric
                    </th>
                    <th className="px-5 py-4 text-[12px] font-semibold text-neutral-400 uppercase tracking-wider text-center">
                      Series A
                    </th>
                    <th className="px-5 py-4 text-[12px] font-semibold text-neutral-400 uppercase tracking-wider text-center">
                      Series B
                    </th>
                    <th className="px-5 py-4 text-[12px] font-semibold text-neutral-400 uppercase tracking-wider text-center">
                      Series C
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { metric: "ARR", a: "$1.5-3M", b: "$8-15M", c: "$30-50M" },
                    { metric: "Growth Rate", a: "3x+ YoY", b: "2-3x YoY", c: "80-100% YoY" },
                    { metric: "Customers", a: "10-20", b: "50+", c: "150+" },
                    { metric: "ACV", a: "$75-200K", b: "$200-500K", c: "$300K-1M" },
                    { metric: "NRR", a: ">110%", b: ">120-130%", c: ">130-140%" },
                    { metric: "Gross Margin", a: ">65%", b: ">70%", c: ">75%" },
                    { metric: "Burn Multiple", a: "<2x", b: "<1.5x", c: "<1.2x" },
                    { metric: "CAC Payback", a: "<18 mo", b: "<15 mo", c: "<12 mo" },
                  ].map((row, i) => (
                    <tr
                      key={row.metric}
                      className={`border-b border-neutral-50 ${
                        i % 2 === 0 ? "bg-white" : "bg-neutral-50/30"
                      }`}
                    >
                      <td className="px-5 py-3 font-medium text-neutral-900">
                        {row.metric}
                      </td>
                      <td className="px-5 py-3 text-center text-neutral-600 tabular-nums">
                        {row.a}
                      </td>
                      <td className="px-5 py-3 text-center text-neutral-600 tabular-nums">
                        {row.b}
                      </td>
                      <td className="px-5 py-3 text-center text-neutral-600 tabular-nums">
                        {row.c}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, delay: 0.2, ease: EASE }}
          className="mt-6 grid md:grid-cols-3 gap-4"
        >
          {[
            {
              label: "Comparable: Hinge Health (IPO)",
              detail: "72% growth, 26% FCF margin, 5.7x EV/Revenue",
            },
            {
              label: "Comparable: Tempus (IPO)",
              detail: "85% growth, 9.3x EV/Revenue",
            },
            {
              label: "Health Tech 2.0 Avg",
              detail: "67% revenue growth, Rule of 40 score of 65",
            },
          ].map((comp) => (
            <div
              key={comp.label}
              className="rounded-xl border border-neutral-200 bg-neutral-50 p-4"
            >
              <div className="text-[12px] font-semibold text-neutral-900 mb-1">
                {comp.label}
              </div>
              <p className="text-[12px] text-neutral-500">{comp.detail}</p>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

// ============================================================================
// THE ASK — use of funds
// ============================================================================
function TheAskSection() {
  const allocations = [
    { label: "Engineering (ML/NLP + Platform)", pct: 50, color: "bg-indigo-500" },
    { label: "Clinical Validation & Pilots", pct: 20, color: "bg-violet-500" },
    { label: "Go-to-Market & BD", pct: 15, color: "bg-emerald-500" },
    { label: "Compliance (HIPAA, SOC 2)", pct: 10, color: "bg-amber-500" },
    { label: "Operations", pct: 5, color: "bg-neutral-400" },
  ];

  return (
    <section className="py-32 md:py-44 px-6 bg-neutral-950 relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom,rgba(99,102,241,0.06),transparent_60%)]" />
      <div className="max-w-[900px] mx-auto relative">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
          className="text-center mb-16"
        >
          <p className="text-[11px] font-semibold tracking-[0.15em] uppercase text-indigo-400/60 mb-4">
            The Ask
          </p>
          <h2 className="text-[2rem] md:text-[3rem] font-semibold tracking-[-0.04em] text-white leading-[1.05]">
            Raising a{" "}
            <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-indigo-400 bg-clip-text text-transparent">
              seed round
            </span>{" "}
            to scale.
          </h2>
          <p className="mt-5 text-white/40 max-w-lg mx-auto text-[16px] leading-relaxed">
            18 months of runway to land 5-10 design partners, hire the core engineering team, and reach $1M+ ARR.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
        >
          {/* Allocation bar */}
          <div className="flex h-3 rounded-full overflow-hidden mb-8">
            {allocations.map((a) => (
              <div key={a.label} className={`${a.color} transition-all`} style={{ width: `${a.pct}%` }} />
            ))}
          </div>

          {/* Legend */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {allocations.map((a) => (
              <div key={a.label} className="flex items-center gap-3">
                <div className={`h-2.5 w-2.5 rounded-full ${a.color} flex-shrink-0`} />
                <div>
                  <div className="text-[13px] font-medium text-white/70">{a.label}</div>
                  <div className="text-[12px] text-white/30">{a.pct}%</div>
                </div>
              </div>
            ))}
          </div>

          {/* Key milestones */}
          <div className="mt-12 grid md:grid-cols-3 gap-4">
            {[
              { milestone: "5-10 Design Partners", timeline: "Months 1-6", detail: "Health systems & pharma" },
              { milestone: "$1M+ ARR", timeline: "Months 6-12", detail: "Convert pilots to contracts" },
              { milestone: "Series A Ready", timeline: "Months 12-18", detail: "Repeatable GTM motion" },
            ].map((m) => (
              <div key={m.milestone} className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-5 text-center">
                <div className="text-[11px] font-semibold text-indigo-400 mb-1">{m.timeline}</div>
                <div className="text-[15px] font-semibold text-white mb-1">{m.milestone}</div>
                <div className="text-[12px] text-white/30">{m.detail}</div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ============================================================================
// CTA — the ask
// ============================================================================
function CTASection() {
  return (
    <section className="py-32 md:py-44 px-6 bg-neutral-950 relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(99,102,241,0.08),transparent_60%)]" />
      <div className="max-w-[800px] mx-auto text-center relative">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={VIEWPORT}
          transition={{ duration: 0.5, ease: EASE }}
        >
          <h2 className="text-[2rem] md:text-[3.25rem] font-semibold tracking-[-0.04em] leading-[1.05]">
            <span className="bg-gradient-to-r from-white via-indigo-200 to-white bg-clip-text text-transparent">
              Let&apos;s talk.
            </span>
          </h2>
          <p className="mt-5 text-neutral-400 max-w-md mx-auto text-[16px] leading-relaxed">
            We&apos;re building the clinical data infrastructure layer for the next decade of health AI. If that thesis resonates, we should connect.
          </p>
          <div className="mt-10 flex items-center justify-center gap-4 flex-wrap">
            <MagneticButton>
              <a href="mailto:alex@sulci.ai">
                <Button className="group bg-white text-neutral-900 hover:bg-neutral-100 rounded-xl h-14 px-10 text-[16px] font-medium shadow-[0_1px_2px_rgba(255,255,255,0.1),0_4px_12px_rgba(255,255,255,0.06)] transition-all glow-button">
                  alex@sulci.ai{" "}
                  <ArrowRight className="ml-1.5 h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
                </Button>
              </a>
            </MagneticButton>
            <MagneticButton>
              <Link href="/dashboard">
                <button
                  className="group inline-flex items-center justify-center rounded-xl h-14 px-10 text-[16px] font-medium border border-white/[0.12] text-white/60 hover:text-white hover:border-white/[0.2] hover:bg-white/[0.04] transition-all"
                >
                  See the Product{" "}
                  <ExternalLink className="ml-1.5 h-4 w-4" />
                </button>
              </Link>
            </MagneticButton>
          </div>
          <div className="mt-8 flex items-center justify-center gap-3 text-[12px] text-white/20">
            <span>HIPAA</span>
            <span>&middot;</span>
            <span>SOC 2</span>
            <span>&middot;</span>
            <span>BAA Available</span>
            <span>&middot;</span>
            <span>FHIR R4</span>
            <span>&middot;</span>
            <span>OMOP CDM v5.4</span>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ============================================================================
// FOOTER
// ============================================================================
function FooterSection() {
  return (
    <footer className="border-t border-white/[0.06] bg-neutral-950">
      <div className="max-w-[1200px] mx-auto px-6 py-10">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="h-6 w-6 rounded-md bg-white flex items-center justify-center">
              <Brain className="h-3.5 w-3.5 text-neutral-900" />
            </div>
            <span className="font-semibold text-[14px] text-white/60">
              Sulci AI
            </span>
          </div>
          <p className="text-[12px] text-white/20">
            &copy; 2026 Sulci AI, Inc. All rights reserved. &middot;
            Confidential — for investor use only.
          </p>
          <Link
            href="/"
            className="text-[12px] text-white/30 hover:text-white/50 transition-colors"
          >
            Back to product &rarr;
          </Link>
        </div>
      </div>
    </footer>
  );
}

// ============================================================================
// PAGE
// ============================================================================
export default function InvestorsPage() {
  return (
    <div className="min-h-screen bg-neutral-950 selection:bg-indigo-900/30 overflow-x-hidden scroll-smooth noise-overlay">
      <InvestorNav />
      <HeroSection />
      <TransformationDemo />
      <SectionDivider dark />
      <ProblemSection />
      <MacroThesisSection />
      <MarketSection />
      <WhyNowSection />
      <SolutionSection />
      <ProductShowcase />
      <FlywheelSection />
      <CompetitiveLandscape />
      <WedgeSection />
      <RoadmapSection />
      <DefensibilitySection />
      <TeamSection />
      <MetricsSection />
      <TheAskSection />
      <CTASection />
      <FooterSection />
    </div>
  );
}
