"use client";

import { useRef, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  motion,
  useInView,
  useMotionValue,
  useTransform,
  useScroll,
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
  ChevronRight,
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
// Animation Variants
// ============================================================================
const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1];

const stagger = {
  container: {
    hidden: {},
    visible: {
      transition: { staggerChildren: 0.08, delayChildren: 0.15 },
    },
  },
  item: {
    hidden: { opacity: 0, y: 28, filter: "blur(8px)" },
    visible: {
      opacity: 1,
      y: 0,
      filter: "blur(0px)",
      transition: { duration: 0.7, ease: EASE },
    },
  },
};

// ============================================================================
// Section wrapper with scroll-triggered reveal (blur-to-sharp)
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
      initial={{ opacity: 0, y: 48, filter: "blur(12px)" }}
      animate={isInView ? { opacity: 1, y: 0, filter: "blur(0px)" } : {}}
      transition={{ duration: 0.8, delay, ease: EASE }}
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

// rgba helper — converts hex + alpha fraction to rgba string
function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

// Section label component
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 mb-6 justify-center">
      <div className="h-px w-8 bg-gradient-to-r from-transparent to-[#045AA9]/40" />
      <span
        className="text-[10px] font-semibold tracking-[0.25em] uppercase text-[#5B9BD5]"
        style={FONT_MONO}
      >
        {children}
      </span>
      <div className="h-px w-8 bg-gradient-to-l from-transparent to-[#045AA9]/40" />
    </div>
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
              background: "rgba(10,15,28,0.75)",
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
// PARTICLE FIELD (Hero background)
// ============================================================================
function ParticleField() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animFrame: number;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);
    };
    resize();
    window.addEventListener("resize", resize);

    // Particles
    const particles: {
      x: number;
      y: number;
      vx: number;
      vy: number;
      size: number;
      alpha: number;
    }[] = [];
    const count = 60;
    const rect = canvas.getBoundingClientRect();
    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * rect.width,
        y: Math.random() * rect.height,
        vx: (Math.random() - 0.5) * 0.15,
        vy: (Math.random() - 0.5) * 0.15,
        size: Math.random() * 1.5 + 0.5,
        alpha: Math.random() * 0.3 + 0.05,
      });
    }

    const draw = () => {
      const w = rect.width;
      const h = rect.height;
      ctx.clearRect(0, 0, w, h);

      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = w;
        if (p.x > w) p.x = 0;
        if (p.y < 0) p.y = h;
        if (p.y > h) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(91, 155, 213, ${p.alpha})`;
        ctx.fill();
      }

      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(91, 155, 213, ${0.04 * (1 - dist / 120)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      animFrame = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(animFrame);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none"
      style={{ opacity: 0.6 }}
    />
  );
}

// ============================================================================
// ANIMATED DNA HELIX (Hero background)
// ============================================================================
function DNAHelix() {
  const [dots, setDots] = useState<
    { x1: number; y1: number; x2: number; y2: number; delay: number }[]
  >([]);

  useEffect(() => {
    const pairs: typeof dots = [];
    for (let i = 0; i < 18; i++) {
      const y = 60 + i * 24;
      const phase = (i * Math.PI) / 5;
      const x1 = 50 + Math.sin(phase) * 30;
      const x2 = 50 - Math.sin(phase) * 30;
      pairs.push({ x1, y1: y, x2, y2: y, delay: i * 0.06 });
    }
    setDots(pairs);
  }, []);

  if (dots.length === 0) return null;

  return (
    <svg
      className="absolute right-[8%] top-1/2 -translate-y-1/2 w-[120px] h-[500px] opacity-[0.07] pointer-events-none"
      viewBox="0 100 100 500"
    >
      {dots.map((d, i) => (
        <g key={i}>
          <motion.circle
            cx={d.x1}
            cy={d.y1}
            r="2.5"
            fill="white"
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 1 + d.delay, duration: 0.4, type: "spring" }}
          />
          <motion.circle
            cx={d.x2}
            cy={d.y2}
            r="2.5"
            fill="white"
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{
              delay: 1 + d.delay + 0.03,
              duration: 0.4,
              type: "spring",
            }}
          />
          <motion.line
            x1={d.x1}
            y1={d.y1}
            x2={d.x2}
            y2={d.y2}
            stroke="white"
            strokeWidth="0.5"
            strokeOpacity="0.4"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ delay: 1.2 + d.delay, duration: 0.3 }}
          />
        </g>
      ))}
      {/* Strand curves */}
      <motion.path
        d={`M${dots.map((d) => `${d.x1},${d.y1}`).join(" L")}`}
        stroke="white"
        strokeWidth="1"
        fill="none"
        strokeOpacity="0.3"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ delay: 0.8, duration: 1.5, ease: "easeOut" }}
      />
      <motion.path
        d={`M${dots.map((d) => `${d.x2},${d.y2}`).join(" L")}`}
        stroke="white"
        strokeWidth="1"
        fill="none"
        strokeOpacity="0.3"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ delay: 0.9, duration: 1.5, ease: "easeOut" }}
      />
    </svg>
  );
}

// ============================================================================
// TYPEWRITER TEXT
// ============================================================================
function Typewriter({
  texts,
  className = "",
  style,
}: {
  texts: string[];
  className?: string;
  style?: React.CSSProperties;
}) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [displayed, setDisplayed] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const text = texts[currentIndex];
    const speed = isDeleting ? 30 : 55;

    if (!isDeleting && displayed === text) {
      const pause = setTimeout(() => setIsDeleting(true), 2200);
      return () => clearTimeout(pause);
    }

    if (isDeleting && displayed === "") {
      setIsDeleting(false);
      setCurrentIndex((prev) => (prev + 1) % texts.length);
      return;
    }

    const timer = setTimeout(() => {
      setDisplayed(
        isDeleting ? text.slice(0, displayed.length - 1) : text.slice(0, displayed.length + 1)
      );
    }, speed);

    return () => clearTimeout(timer);
  }, [displayed, isDeleting, currentIndex, texts]);

  return (
    <span className={className} style={style}>
      {displayed}
      <span className="animate-pulse text-[#D50057]">|</span>
    </span>
  );
}

// ============================================================================
// TILT CARD wrapper
// ============================================================================
function TiltCard({
  children,
  className = "",
  style,
}: {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  const cardRef = useRef<HTMLDivElement>(null);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = cardRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    const rotateX = ((y - centerY) / centerY) * -4;
    const rotateY = ((x - centerX) / centerX) * 4;
    el.style.transform = `perspective(600px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(1.01)`;
  };

  const handleMouseLeave = () => {
    const el = cardRef.current;
    if (el)
      el.style.transform =
        "perspective(600px) rotateX(0deg) rotateY(0deg) scale(1)";
  };

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className={className}
      style={{ transition: "transform 0.2s ease-out", ...style }}
    >
      {children}
    </div>
  );
}

// ============================================================================
// HERO SECTION
// ============================================================================
function HeroSection() {
  const router = useRouter();
  const heroRef = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"],
  });
  const bgY = useTransform(scrollYProgress, [0, 1], ["0%", "30%"]);
  const orbScale = useTransform(scrollYProgress, [0, 1], [1, 1.3]);

  return (
    <section
      ref={heroRef}
      className="relative overflow-hidden text-white"
      style={{
        background:
          "linear-gradient(135deg, #0A0F1C 0%, #0D1B2A 40%, #0F2137 70%, #0A0F1C 100%)",
      }}
    >
      {/* Parallax mesh gradients */}
      <motion.div className="absolute inset-0" style={{ y: bgY }}>
        <motion.div
          className="absolute top-[-20%] right-[-10%] w-[700px] h-[700px] rounded-full blur-[180px]"
          style={{
            scale: orbScale,
            background: hexToRgba("#045AA9", 0.08),
          }}
        />
        <motion.div
          className="absolute bottom-[-30%] left-[-10%] w-[500px] h-[500px] rounded-full blur-[150px]"
          style={{
            scale: orbScale,
            background: hexToRgba("#D50057", 0.05),
          }}
        />
        <div
          className="absolute top-[40%] left-[30%] w-[300px] h-[300px] rounded-full blur-[120px]"
          style={{ background: hexToRgba("#14B8A6", 0.04) }}
        />
      </motion.div>

      {/* Particle field */}
      <ParticleField />

      {/* Grid overlay */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
          backgroundSize: "64px 64px",
        }}
      />

      {/* DNA helix decoration */}
      <DNAHelix />

      {/* Top edge */}
      <div
        className="absolute top-0 left-0 right-0 h-px"
        style={{
          background: `linear-gradient(90deg, transparent, ${hexToRgba("#045AA9", 0.3)}, transparent)`,
        }}
      />

      <div className="relative max-w-6xl mx-auto px-6 pt-24 pb-28 md:pt-32 md:pb-36">
        <motion.div
          variants={stagger.container}
          initial="hidden"
          animate="visible"
          className="max-w-4xl"
        >
          {/* Platform indicator */}
          <motion.div variants={stagger.item} className="mb-10">
            <div
              className="inline-flex items-center gap-2.5 px-4 py-2 rounded-full border border-white/[0.08] bg-white/[0.03] backdrop-blur-sm"
              style={FONT_MONO}
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
              </span>
              <span className="text-[11px] text-white/60 tracking-wider uppercase">
                Regeneron Clinical Trial Platform
              </span>
            </div>
          </motion.div>

          {/* Headline — left-aligned, editorial */}
          <motion.h1
            variants={stagger.item}
            className="text-5xl md:text-6xl lg:text-[5.5rem] font-bold leading-[0.95] tracking-[-0.03em]"
            style={FONT_DISPLAY}
          >
            <span className="text-white/90">Accelerating</span>
            <br />
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(135deg, #ffffff 0%, #5B9BD5 50%, #D50057 100%)",
              }}
            >
              Patient Recruitment
            </span>
          </motion.h1>

          <motion.div variants={stagger.item} className="mt-3 h-8">
            <Typewriter
              texts={[
                "for Regeneron Therapeutics",
                "powered by OMOP CDM",
                "via Health Information Exchanges",
                "with real-time eligibility screening",
              ]}
              className="text-lg md:text-xl text-white/25 tracking-tight"
              style={FONT_DISPLAY}
            />
          </motion.div>

          <motion.p
            variants={stagger.item}
            className="mt-8 text-[15px] text-white/40 max-w-xl leading-relaxed"
            style={FONT_DISPLAY}
          >
            Ingest patient data from Health Information Exchanges via Metriport,
            standardize to OMOP, and automatically screen patients against trial
            eligibility criteria — in real time.
          </motion.p>

          {/* CTAs */}
          <motion.div
            variants={stagger.item}
            className="mt-10 flex flex-col sm:flex-row items-start gap-3"
          >
            <Link href="/trials">
              <Button
                size="lg"
                className="bg-[#D50057] hover:bg-[#B8004B] text-white font-semibold px-8 shadow-[0_0_40px_-8px_rgba(213,0,87,0.4)] border-0 rounded-xl h-12 transition-all duration-300 hover:shadow-[0_0_50px_-4px_rgba(213,0,87,0.5)]"
                style={FONT_DISPLAY}
              >
                View Active Trials
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <Link href="/dashboard">
              <Button
                size="lg"
                className="bg-white/[0.04] backdrop-blur-sm border border-white/[0.08] text-white/60 hover:bg-white/[0.08] hover:text-white/80 hover:border-white/[0.15] px-8 rounded-xl h-12 transition-all duration-300"
                style={FONT_DISPLAY}
              >
                Platform Dashboard
              </Button>
            </Link>
            <Button
              size="lg"
              onClick={() => {
                document.cookie = "has_auth=true; path=/; max-age=86400";
                router.push("/dashboard");
              }}
              className="bg-transparent border-2 border-[#D50057]/40 text-[#D50057] hover:bg-[#D50057]/10 hover:border-[#D50057]/60 px-8 rounded-xl h-12 transition-all duration-300 font-semibold shadow-[0_0_30px_-8px_rgba(213,0,87,0.25)] hover:shadow-[0_0_40px_-4px_rgba(213,0,87,0.35)]"
              style={FONT_DISPLAY}
            >
              <Sparkles className="mr-2 h-4 w-4" />
              Try Demo
            </Button>
          </motion.div>
        </motion.div>

        {/* Stats bar — glassmorphic panel */}
        <motion.div
          variants={stagger.item}
          initial="hidden"
          animate="visible"
          className="mt-20"
        >
          <div
            className="rounded-2xl overflow-hidden border border-white/[0.06]"
            style={{
              background:
                "linear-gradient(135deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%)",
              backdropFilter: "blur(20px)",
            }}
          >
            {/* Terminal bar */}
            <div className="flex items-center gap-2 px-5 py-2.5 border-b border-white/[0.04]">
              <div className="flex gap-1.5">
                <div className="w-[7px] h-[7px] rounded-full bg-white/10" />
                <div className="w-[7px] h-[7px] rounded-full bg-white/10" />
                <div className="w-[7px] h-[7px] rounded-full bg-white/10" />
              </div>
              <span
                className="text-[9px] text-white/20 tracking-[0.2em] uppercase ml-2"
                style={FONT_MONO}
              >
                Trial Metrics — Live
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-white/[0.04]">
              {[
                {
                  value: "3",
                  label: "Active Regeneron Trials",
                  accent: false,
                },
                {
                  value: "80M+",
                  label: "EYLEA Injections Worldwide",
                  accent: true,
                },
                {
                  value: "1.4M+",
                  label: "DUPIXENT Patients Globally",
                  accent: false,
                },
                {
                  value: "68%",
                  label: "LIBTAYO Recurrence Reduction",
                  accent: true,
                },
              ].map((stat) => (
                <div key={stat.label} className="px-6 py-7 text-center">
                  <div
                    className={`text-3xl md:text-4xl font-bold tracking-tighter ${
                      stat.accent ? "text-[#D50057]" : "text-white/90"
                    }`}
                    style={FONT_MONO}
                  >
                    {stat.value}
                  </div>
                  <div
                    className="text-[10px] text-white/25 mt-2.5 tracking-[0.15em] uppercase"
                    style={FONT_MONO}
                  >
                    {stat.label}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </div>

      {/* Bottom edge */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
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
    accent: "#F59E0B",
    glow: "rgba(245, 158, 11, 0.15)",
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
    accent: "#D50057",
    glow: "rgba(213, 0, 87, 0.15)",
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
    accent: "#14B8A6",
    glow: "rgba(20, 184, 166, 0.15)",
  },
];

function TherapeuticPipelineSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <section
      className="py-24 px-6"
      style={{
        background:
          "linear-gradient(180deg, #0A0F1C 0%, #0D1525 50%, #0A0F1C 100%)",
      }}
    >
      <div className="max-w-6xl mx-auto" ref={ref}>
        <Reveal>
          <div className="text-center mb-16">
            <SectionLabel>Active Trials</SectionLabel>
            <h2
              className="text-3xl md:text-4xl font-bold tracking-[-0.02em] text-white"
              style={FONT_DISPLAY}
            >
              Regeneron Therapeutic Pipeline
            </h2>
            <p
              className="text-white/30 mt-3 max-w-lg mx-auto text-[15px]"
              style={FONT_DISPLAY}
            >
              Automated eligibility screening across ophthalmology, oncology,
              and immunology
            </p>
          </div>
        </Reveal>

        <div className="grid md:grid-cols-3 gap-5">
          {trials.map((trial, i) => {
            const Icon = trial.icon;
            return (
              <motion.div
                key={trial.drug}
                initial={{ opacity: 0, y: 36, filter: "blur(8px)" }}
                animate={
                  isInView ? { opacity: 1, y: 0, filter: "blur(0px)" } : {}
                }
                transition={{
                  duration: 0.6,
                  delay: 0.1 + i * 0.1,
                  ease: EASE,
                }}
              >
                <Link href="/trials" className="group block h-full">
                  <TiltCard className="relative h-full rounded-2xl border border-white/[0.06] overflow-hidden transition-all duration-500 hover:border-white/[0.12] group-hover:shadow-lg">
                    <div
                      className="absolute inset-0"
                      style={{
                        background:
                          "linear-gradient(180deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%)",
                      }}
                    />

                    {/* Animated gradient border on hover */}
                    <div
                      className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-700"
                      style={{
                        background: `linear-gradient(135deg, ${hexToRgba(trial.accent, 0.15)}, transparent 50%, ${hexToRgba(trial.accent, 0.08)})`,
                      }}
                    />

                    {/* Top accent */}
                    <div
                      className="h-[2px] w-full relative z-10"
                      style={{
                        background: `linear-gradient(90deg, transparent, ${trial.accent}, transparent)`,
                      }}
                    />

                    {/* Hover glow */}
                    <div
                      className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                      style={{
                        background: `radial-gradient(ellipse at top, ${trial.glow} 0%, transparent 70%)`,
                      }}
                    />

                    <div className="relative p-6 z-10">
                      {/* Icon + Phase */}
                      <div className="flex items-start justify-between mb-6">
                        <div
                          className="h-11 w-11 rounded-xl flex items-center justify-center"
                          style={{
                            background: `linear-gradient(135deg, ${hexToRgba(trial.accent, 0.12)}, ${hexToRgba(trial.accent, 0.03)})`,
                            border: `1px solid ${hexToRgba(trial.accent, 0.12)}`,
                          }}
                        >
                          <Icon
                            className="h-5 w-5"
                            style={{ color: trial.accent }}
                          />
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
                        className="text-[10px] font-semibold uppercase tracking-[0.2em] text-white/25 mb-2"
                        style={FONT_MONO}
                      >
                        {trial.area}
                      </p>
                      <h3
                        className="text-xl font-bold tracking-tight text-white mb-3 group-hover:text-white transition-colors"
                        style={FONT_DISPLAY}
                      >
                        {trial.drug}
                      </h3>
                      <p
                        className="text-[13px] text-white/30 leading-relaxed"
                        style={FONT_DISPLAY}
                      >
                        {trial.indication}
                      </p>

                      {/* Stats */}
                      <div className="mt-6 pt-5 border-t border-white/[0.06] flex items-end justify-between">
                        <div>
                          <div
                            className="text-2xl font-bold tracking-tighter"
                            style={{
                              ...FONT_MONO,
                              color: trial.accent,
                            }}
                          >
                            {trial.stat}
                          </div>
                          <div
                            className="text-[10px] text-white/20 mt-1 uppercase tracking-[0.15em]"
                            style={FONT_MONO}
                          >
                            {trial.statLabel}
                          </div>
                        </div>
                        <span
                          className="text-[10px] text-white/15"
                          style={FONT_MONO}
                        >
                          {trial.nct}
                        </span>
                      </div>
                    </div>

                    {/* Hover arrow */}
                    <div className="absolute bottom-6 right-6 opacity-0 group-hover:opacity-100 transition-all duration-300 translate-x-2 group-hover:translate-x-0 z-10">
                      <ArrowRight className="h-4 w-4 text-white/40" />
                    </div>
                  </TiltCard>
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
// LIVE ENROLLMENT PIPELINE (with animated pulse dots)
// ============================================================================
// Pipeline counts derived from seed_demo_data.py enrollment records:
//   Screened = all 18 enrollments entered the pipeline
//   Eligible = ELIGIBLE(3) + ENROLLED(3) + ACTIVE(3) + COMPLETED(1) = 10
//   Enrolled = ENROLLED(3) + ACTIVE(3) + COMPLETED(1) = 7
//   Active   = ACTIVE(3) + COMPLETED(1) = 4
//   Completed = COMPLETED(1) = 1
const pipelineSteps = [
  { label: "Screened", count: 18, pct: 100, color: "#64748B" },
  { label: "Eligible", count: 10, pct: 56, color: "#045AA9" },
  { label: "Enrolled", count: 7, pct: 39, color: "#14B8A6" },
  { label: "Active", count: 4, pct: 22, color: "#10B981" },
  { label: "Completed", count: 1, pct: 6, color: "#059669" },
];

const conversionMetrics = [
  { rate: 55.6, label: "Screen-to-Eligible", color: "#045AA9" },  // 10/18
  { rate: 70.0, label: "Eligible-to-Enrolled", color: "#14B8A6" }, // 7/10
  { rate: 57.1, label: "Enrolled-to-Active", color: "#10B981" },   // 4/7
];

function PulseDot({ color, delay }: { color: string; delay: number }) {
  return (
    <motion.div
      className="flex-shrink-0 relative"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay }}
    >
      <span
        className="block h-2 w-2 rounded-full"
        style={{ background: color }}
      />
      <motion.span
        className="absolute inset-0 rounded-full"
        style={{ background: color }}
        animate={{ scale: [1, 2.5], opacity: [0.5, 0] }}
        transition={{ duration: 1.5, repeat: Infinity, delay: delay + 0.5 }}
      />
    </motion.div>
  );
}

function EnrollmentPipelineSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <section
      className="py-24 px-6"
      style={{
        background:
          "linear-gradient(180deg, #0A0F1C 0%, #0E1729 50%, #0A0F1C 100%)",
      }}
    >
      <div className="max-w-5xl mx-auto" ref={ref}>
        <Reveal>
          <div className="text-center mb-14">
            <SectionLabel>Real-Time Data</SectionLabel>
            <div className="flex items-center justify-center gap-3">
              <h2
                className="text-3xl md:text-4xl font-bold tracking-[-0.02em] text-white"
                style={FONT_DISPLAY}
              >
                Live Enrollment Pipeline
              </h2>
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
              </span>
            </div>
            <p
              className="text-white/30 mt-3 text-[15px]"
              style={FONT_DISPLAY}
            >
              Real-time patient flow across all Regeneron trials
            </p>
          </div>
        </Reveal>

        <motion.div
          initial={{ opacity: 0, y: 28 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.7, delay: 0.15, ease: EASE }}
          className="rounded-2xl border border-white/[0.06] overflow-hidden"
          style={{
            background:
              "linear-gradient(180deg, rgba(255,255,255,0.025) 0%, rgba(255,255,255,0.005) 100%)",
          }}
        >
          {/* Terminal bar */}
          <div className="flex items-center gap-2 px-6 py-3 border-b border-white/[0.04]">
            <div className="flex gap-1.5">
              <div className="w-[7px] h-[7px] rounded-full bg-white/10" />
              <div className="w-[7px] h-[7px] rounded-full bg-white/10" />
              <div className="w-[7px] h-[7px] rounded-full bg-white/10" />
            </div>
            <span
              className="text-[9px] text-white/20 tracking-[0.2em] uppercase ml-2"
              style={FONT_MONO}
            >
              Enrollment Funnel — All Trials
            </span>
          </div>

          <div className="p-8">
            {/* Pipeline funnel with pulse dots */}
            <div className="flex items-stretch gap-2 md:gap-3">
              {pipelineSteps.map((step, i) => (
                <div
                  key={step.label}
                  className="flex-1 flex items-center gap-2 md:gap-3"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-center mb-4">
                      <div
                        className="text-2xl md:text-3xl font-bold tracking-tighter text-white"
                        style={FONT_MONO}
                      >
                        <AnimatedNumber value={step.count} />
                      </div>
                      <div
                        className="text-[10px] text-white/25 mt-1.5 uppercase tracking-[0.12em]"
                        style={FONT_MONO}
                      >
                        {step.label}
                      </div>
                    </div>
                    {/* Animated bar */}
                    <div className="h-1.5 rounded-full bg-white/[0.04] overflow-hidden">
                      <motion.div
                        className="h-full rounded-full"
                        style={{ backgroundColor: step.color }}
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
                  {i < pipelineSteps.length - 1 && (
                    <div className="flex flex-col items-center gap-1">
                      <PulseDot
                        color={pipelineSteps[i + 1].color}
                        delay={0.8 + i * 0.2}
                      />
                      <ChevronRight className="h-3 w-3 text-white/10 flex-shrink-0" />
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Conversion metrics with animated decimals */}
            <div className="mt-10 pt-6 border-t border-white/[0.04] grid grid-cols-3 gap-3">
              {conversionMetrics.map((metric) => (
                <div
                  key={metric.label}
                  className="text-center rounded-xl p-4 border border-white/[0.04] bg-white/[0.015]"
                >
                  <div
                    className="text-lg font-bold"
                    style={{ ...FONT_MONO, color: metric.color }}
                  >
                    <AnimatedNumber
                      value={metric.rate}
                      suffix="%"
                      decimals={1}
                    />
                  </div>
                  <div
                    className="text-[10px] text-white/20 mt-2 uppercase tracking-[0.12em]"
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
// HOW IT WORKS
// ============================================================================
const steps = [
  {
    step: "01",
    icon: Network,
    title: "Ingest from HIE",
    description:
      "Patient records flow from Carequality, CommonWell, and eHealth Exchange via Metriport. FHIR R4 Bundles are ingested automatically — conditions, medications, labs, and procedures.",
    accent: "#045AA9",
  },
  {
    step: "02",
    icon: BrainCircuit,
    title: "Normalize to OMOP",
    description:
      "All clinical data is mapped to OMOP concepts — ICD-10, LOINC, RxNorm, SNOMED CT. NLP extracts facts from unstructured notes. A patient knowledge graph captures every relationship.",
    accent: "#14B8A6",
  },
  {
    step: "03",
    icon: Target,
    title: "Screen & Match",
    description:
      "Patients are evaluated against Regeneron trial criteria instantly. Structured inclusion/exclusion rules check conditions, labs, and medications. Candidates are ranked and surfaced to coordinators.",
    accent: "#D50057",
  },
];

function HowItWorksSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <section
      className="py-24 px-6"
      style={{
        background:
          "linear-gradient(180deg, #0A0F1C 0%, #0D1525 50%, #0A0F1C 100%)",
      }}
    >
      <div className="max-w-5xl mx-auto" ref={ref}>
        <Reveal>
          <div className="text-center mb-16">
            <SectionLabel>Workflow</SectionLabel>
            <h2
              className="text-3xl md:text-4xl font-bold tracking-[-0.02em] text-white"
              style={FONT_DISPLAY}
            >
              How It Works
            </h2>
            <p
              className="text-white/30 mt-3 text-[15px]"
              style={FONT_DISPLAY}
            >
              From HIE data to trial enrollment in three steps
            </p>
          </div>
        </Reveal>

        <div className="relative">
          {/* Connecting line — fixed gradient (was using invalid Tailwind syntax) */}
          <motion.div
            className="hidden md:block absolute top-[56px] left-[16%] right-[16%] h-px"
            initial={{ scaleX: 0 }}
            animate={isInView ? { scaleX: 1 } : {}}
            transition={{ duration: 1, delay: 0.4, ease: "easeOut" }}
            style={{ originX: 0 }}
          >
            <div
              className="w-full h-full"
              style={{
                background: `linear-gradient(90deg, ${hexToRgba("#045AA9", 0.3)}, ${hexToRgba("#14B8A6", 0.3)}, ${hexToRgba("#D50057", 0.3)})`,
              }}
            />
          </motion.div>

          <div className="grid md:grid-cols-3 gap-12">
            {steps.map(
              ({ step, icon: Icon, title, description, accent }, i) => (
                <motion.div
                  key={step}
                  initial={{ opacity: 0, y: 36 }}
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
                    <div
                      className="h-[72px] w-[72px] rounded-2xl flex items-center justify-center shadow-lg"
                      style={{
                        background: `linear-gradient(135deg, ${hexToRgba(accent, 0.18)}, ${hexToRgba(accent, 0.06)})`,
                        border: `1px solid ${hexToRgba(accent, 0.15)}`,
                        boxShadow: `0 8px 32px -8px ${hexToRgba(accent, 0.12)}`,
                      }}
                    >
                      <Icon className="h-8 w-8" style={{ color: accent }} />
                    </div>
                    <span
                      className="absolute -top-2 -right-2 h-7 w-7 rounded-full bg-[#0D1525] border border-white/[0.08] flex items-center justify-center text-[11px] font-bold"
                      style={{ ...FONT_MONO, color: accent }}
                    >
                      {step}
                    </span>
                  </div>
                  <h3
                    className="font-bold text-lg mb-3 tracking-tight text-white"
                    style={FONT_DISPLAY}
                  >
                    {title}
                  </h3>
                  <p
                    className="text-[13px] text-white/30 leading-relaxed max-w-xs mx-auto"
                    style={FONT_DISPLAY}
                  >
                    {description}
                  </p>
                </motion.div>
              )
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// PLATFORM CAPABILITIES — Bento Grid with tilt
// ============================================================================
function CapabilitiesSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  const smallCards = [
    {
      icon: Globe,
      accent: "#14B8A6",
      title: "HIE Integration",
      description: "Carequality, CommonWell, eHealth Exchange via Metriport",
    },
    {
      icon: Database,
      accent: "#045AA9",
      title: "OMOP CDM",
      description: "Standardized concepts for cross-site analysis",
    },
    {
      icon: GitBranch,
      accent: "#A855F7",
      title: "Knowledge Graph",
      description: "Clinical relationships and temporal context",
    },
    {
      icon: Zap,
      accent: "#F59E0B",
      title: "Real-time Screening",
      description: "Instant eligibility evaluation against trial criteria",
    },
  ];

  return (
    <section
      className="py-24 px-6"
      style={{
        background:
          "linear-gradient(180deg, #0A0F1C 0%, #0E1729 50%, #0A0F1C 100%)",
      }}
    >
      <div className="max-w-5xl mx-auto" ref={ref}>
        <Reveal>
          <div className="text-center mb-16">
            <SectionLabel>Infrastructure</SectionLabel>
            <h2
              className="text-3xl md:text-4xl font-bold tracking-[-0.02em] text-white"
              style={FONT_DISPLAY}
            >
              Platform Capabilities
            </h2>
            <p
              className="text-white/30 mt-3 text-[15px]"
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
            initial={{ opacity: 0, y: 28 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6, delay: 0.1, ease: EASE }}
            className="col-span-2 row-span-2"
          >
            <TiltCard
              className="rounded-2xl p-6 relative overflow-hidden group transition-all duration-500 h-full"
              style={{
                background: `linear-gradient(135deg, ${hexToRgba("#045AA9", 0.12)}, ${hexToRgba("#002B5C", 0.25)})`,
                border: `1px solid ${hexToRgba("#045AA9", 0.15)}`,
              }}
            >
              {/* Grid pattern */}
              <div
                className="absolute inset-0 opacity-[0.03]"
                style={{
                  backgroundImage:
                    "radial-gradient(circle, rgba(255,255,255,0.8) 1px, transparent 1px)",
                  backgroundSize: "20px 20px",
                }}
              />
              {/* Hover glow */}
              <div
                className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                style={{
                  background: `linear-gradient(to bottom right, ${hexToRgba("#045AA9", 0.1)}, transparent)`,
                }}
              />

              <div className="relative">
                <div
                  className="h-11 w-11 rounded-xl flex items-center justify-center mb-6"
                  style={{
                    background: hexToRgba("#045AA9", 0.15),
                    border: `1px solid ${hexToRgba("#045AA9", 0.2)}`,
                  }}
                >
                  <HeartPulse className="h-5 w-5 text-[#5B9BD5]" />
                </div>
                <h3
                  className="text-lg font-bold mb-3 tracking-tight text-white"
                  style={FONT_DISPLAY}
                >
                  FHIR R4 Bundle Import
                </h3>
                <p
                  className="text-sm text-white/30 leading-relaxed mb-6"
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
                        className="flex items-center gap-2 text-xs text-white/35"
                        style={FONT_DISPLAY}
                      >
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500/60" />
                        {item}
                      </div>
                    )
                  )}
                </div>
              </div>
            </TiltCard>
          </motion.div>

          {/* Small cards with tilt */}
          {smallCards.map((card, i) => {
            const Icon = card.icon;
            return (
              <motion.div
                key={card.title}
                initial={{ opacity: 0, y: 28 }}
                animate={isInView ? { opacity: 1, y: 0 } : {}}
                transition={{
                  duration: 0.6,
                  delay: 0.15 + i * 0.06,
                  ease: EASE,
                }}
              >
                <TiltCard
                  className="rounded-2xl border border-white/[0.06] overflow-hidden group transition-all duration-500 hover:border-white/[0.1] h-full"
                  style={{
                    background:
                      "linear-gradient(180deg, rgba(255,255,255,0.025) 0%, rgba(255,255,255,0.005) 100%)",
                  }}
                >
                  {/* Top accent */}
                  <div
                    className="h-[2px] w-full"
                    style={{
                      background: `linear-gradient(90deg, transparent, ${hexToRgba(card.accent, 0.3)}, transparent)`,
                    }}
                  />
                  <div className="p-5">
                    <div
                      className="h-10 w-10 rounded-xl flex items-center justify-center mb-3"
                      style={{
                        background: hexToRgba(card.accent, 0.06),
                        border: `1px solid ${hexToRgba(card.accent, 0.08)}`,
                      }}
                    >
                      <Icon
                        className="h-5 w-5"
                        style={{ color: card.accent }}
                      />
                    </div>
                    <h3
                      className="font-semibold text-sm mb-1.5 tracking-tight text-white/80"
                      style={FONT_DISPLAY}
                    >
                      {card.title}
                    </h3>
                    <p
                      className="text-[12px] text-white/25 leading-relaxed"
                      style={FONT_DISPLAY}
                    >
                      {card.description}
                    </p>
                  </div>
                </TiltCard>
              </motion.div>
            );
          })}

          {/* Wide card — Analytics */}
          <motion.div
            initial={{ opacity: 0, y: 28 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6, delay: 0.45, ease: EASE }}
            className="col-span-2"
          >
            <TiltCard
              className="rounded-2xl border border-white/[0.06] p-5 transition-all duration-500 hover:border-white/[0.1]"
              style={{
                background: `linear-gradient(135deg, ${hexToRgba("#10B981", 0.04)}, rgba(255,255,255,0.01))`,
              }}
            >
              <div className="flex items-start gap-4">
                <div
                  className="h-10 w-10 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{
                    background: hexToRgba("#10B981", 0.1),
                    border: `1px solid ${hexToRgba("#10B981", 0.15)}`,
                  }}
                >
                  <BarChart3 className="h-5 w-5 text-emerald-500" />
                </div>
                <div>
                  <h3
                    className="font-semibold text-sm mb-1.5 tracking-tight text-white/80"
                    style={FONT_DISPLAY}
                  >
                    Enrollment Analytics & Reporting
                  </h3>
                  <p
                    className="text-[12px] text-white/25 leading-relaxed"
                    style={FONT_DISPLAY}
                  >
                    Track screening-to-enrollment conversion by trial, site, and
                    time period. Monitor recruitment bottlenecks and optimize
                    pipeline velocity.
                  </p>
                </div>
              </div>
            </TiltCard>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// STANDARDS & COMPLIANCE — with horizontal marquee
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
    <section
      className="py-16 px-6 overflow-hidden"
      style={{
        background: "#0A0F1C",
        borderTop: "1px solid rgba(255,255,255,0.04)",
        borderBottom: "1px solid rgba(255,255,255,0.04)",
      }}
    >
      <Reveal className="max-w-5xl mx-auto">
        <div className="grid md:grid-cols-2 gap-12">
          {/* Standards — scrolling marquee */}
          <div>
            <p
              className="text-[10px] font-semibold uppercase tracking-[0.2em] text-white/20 mb-5"
              style={FONT_MONO}
            >
              Standards & Vocabularies
            </p>
            {/* Marquee container */}
            <div className="relative overflow-hidden">
              <div className="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-[#0A0F1C] to-transparent z-10" />
              <div className="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-[#0A0F1C] to-transparent z-10" />
              <motion.div
                className="flex gap-2 whitespace-nowrap"
                animate={{ x: ["0%", "-50%"] }}
                transition={{
                  x: {
                    repeat: Infinity,
                    repeatType: "loop",
                    duration: 25,
                    ease: "linear",
                  },
                }}
              >
                {/* Double the items for seamless loop */}
                {[...standardsList, ...standardsList].map((standard, idx) => (
                  <span
                    key={`${standard}-${idx}`}
                    className="px-3 py-1.5 text-[11px] rounded-lg bg-white/[0.03] text-white/30 border border-white/[0.06] flex-shrink-0"
                    style={FONT_MONO}
                  >
                    {standard}
                  </span>
                ))}
              </motion.div>
            </div>
          </div>

          {/* Compliance */}
          <div>
            <p
              className="text-[10px] font-semibold uppercase tracking-[0.2em] text-white/20 mb-5"
              style={FONT_MONO}
            >
              Security & Compliance
            </p>
            <div className="grid grid-cols-2 gap-3">
              {[
                { icon: Shield, label: "HIPAA Compliant", accent: "#10B981" },
                { icon: Lock, label: "SOC 2 Type II", accent: "#10B981" },
                {
                  icon: FileText,
                  label: "21 CFR Part 11",
                  accent: "#10B981",
                },
                {
                  icon: Activity,
                  label: "Full Audit Trail",
                  accent: "#10B981",
                },
              ].map(({ icon: Icon, label, accent }) => (
                <div
                  key={label}
                  className="flex items-center gap-3 rounded-xl p-3 border border-white/[0.04] bg-white/[0.015]"
                >
                  <div
                    className="h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{
                      background: hexToRgba(accent, 0.06),
                      border: `1px solid ${hexToRgba(accent, 0.09)}`,
                    }}
                  >
                    <Icon className="h-4 w-4" style={{ color: accent }} />
                  </div>
                  <span
                    className="text-[13px] text-white/40 font-medium"
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
// CTA
// ============================================================================
function CTASection() {
  const router = useRouter();
  return (
    <section
      className="relative py-28 px-6 overflow-hidden"
      style={{ background: "#0A0F1C" }}
    >
      {/* Gradient orbs */}
      <div className="absolute inset-0">
        <div
          className="absolute top-[-20%] right-[10%] w-[500px] h-[500px] rounded-full blur-[150px]"
          style={{ background: hexToRgba("#D50057", 0.06) }}
        />
        <div
          className="absolute bottom-[-20%] left-[10%] w-[400px] h-[400px] rounded-full blur-[120px]"
          style={{ background: hexToRgba("#045AA9", 0.08) }}
        />
      </div>

      <Reveal className="relative max-w-3xl mx-auto text-center">
        <h2
          className="text-3xl md:text-5xl font-bold leading-[1.05] tracking-[-0.02em] text-white"
          style={FONT_DISPLAY}
        >
          Ready to Accelerate
          <br />
          <span
            className="bg-clip-text text-transparent"
            style={{
              backgroundImage:
                "linear-gradient(135deg, #ffffff 0%, #D50057 100%)",
            }}
          >
            Regeneron Trial Enrollment?
          </span>
        </h2>
        <p
          className="mt-5 text-white/30 text-base max-w-xl mx-auto"
          style={FONT_DISPLAY}
        >
          See how automated eligibility screening reduces time-to-enrollment and
          ensures no eligible patient is missed.
        </p>
        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link href="/trials">
            <Button
              size="lg"
              className="bg-[#D50057] hover:bg-[#B8004B] text-white font-semibold px-8 shadow-[0_0_40px_-8px_rgba(213,0,87,0.4)] border-0 rounded-xl h-12 transition-all duration-300 hover:shadow-[0_0_50px_-4px_rgba(213,0,87,0.5)]"
              style={FONT_DISPLAY}
            >
              <FlaskConical className="mr-2 h-4 w-4" />
              Explore Trials
            </Button>
          </Link>
          <Link href="/dashboard">
            <Button
              size="lg"
              className="bg-white/[0.04] backdrop-blur-sm border border-white/[0.08] text-white/60 hover:bg-white/[0.08] hover:text-white/80 hover:border-white/[0.15] px-8 rounded-xl h-12 transition-all duration-300"
              style={FONT_DISPLAY}
            >
              View Dashboard
            </Button>
          </Link>
          <Button
            size="lg"
            onClick={() => {
              document.cookie = "has_auth=true; path=/; max-age=86400";
              router.push("/dashboard");
            }}
            className="bg-transparent border-2 border-[#D50057]/40 text-[#D50057] hover:bg-[#D50057]/10 hover:border-[#D50057]/60 px-8 rounded-xl h-12 transition-all duration-300 font-semibold shadow-[0_0_30px_-8px_rgba(213,0,87,0.25)] hover:shadow-[0_0_40px_-4px_rgba(213,0,87,0.35)]"
            style={FONT_DISPLAY}
          >
            <Sparkles className="mr-2 h-4 w-4" />
            Try Demo
          </Button>
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
      style={{
        background: "#0A0F1C",
        borderTop: "1px solid rgba(255,255,255,0.04)",
      }}
    >
      <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div
            className="h-8 w-8 rounded-lg flex items-center justify-center"
            style={{
              background: hexToRgba("#045AA9", 0.15),
              border: `1px solid ${hexToRgba("#045AA9", 0.2)}`,
            }}
          >
            <Microscope className="h-4 w-4 text-[#5B9BD5]" />
          </div>
          <div>
            <span
              className="font-semibold text-sm text-white/70"
              style={FONT_DISPLAY}
            >
              Clinical Ontology Normalizer
            </span>
            <span
              className="text-xs text-white/20 ml-2"
              style={FONT_DISPLAY}
            >
              for Regeneron
            </span>
          </div>
        </div>
        <div
          className="flex items-center gap-6 text-[11px] text-white/15 tracking-[0.15em]"
          style={FONT_MONO}
        >
          <span>HIPAA</span>
          <span>SOC 2</span>
          <span>21 CFR Part 11</span>
          <span>FHIR R4</span>
        </div>
        <p className="text-xs text-white/15" style={FONT_DISPLAY}>
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
  // Force body background dark so white theme doesn't bleed through
  useEffect(() => {
    const prev = document.body.style.background;
    document.body.style.background = "#0A0F1C";
    document.documentElement.style.background = "#0A0F1C";
    return () => {
      document.body.style.background = prev;
      document.documentElement.style.background = "";
    };
  }, []);

  return (
    <div className="min-h-screen" style={{ background: "#0A0F1C" }}>
      <FontLoader />
      <FloatingNav />
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
