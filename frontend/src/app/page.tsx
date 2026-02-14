"use client";

import { useRef, useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  motion,
  useScroll,
  useTransform,
  useMotionValue,
  useSpring,
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
  Search,
  Sparkles,
  CheckCircle2,
  Zap,
  Lock,
  Globe,
  Activity,
  Network,
  ChevronRight,
  Play,
  Code2,
  Layers,
  Binary,
  Terminal,
  Cpu,
  Quote,
  Star,
  ExternalLink,
  Copy,
  Check,
  MousePointer2,
  Menu,
  X,
  Command,
} from "lucide-react";

// ============================================================================
// Design tokens
// ============================================================================
const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1];
const VIEWPORT = { once: true, margin: "-60px" as const };

// ============================================================================
// Logo component — custom Sulci brain mark
// ============================================================================
function SulciLogo({ className = "h-4 w-4", variant = "stroke", size = "sm" }: { className?: string; variant?: "stroke" | "filled"; size?: "sm" | "lg" }) {
  if (variant === "filled") {
    // Filled brain on dark bg — ultra-simplified for nav/footer at 16px
    return (
      <svg className={className} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Left hemisphere */}
        <path d="M11 3.5C7.5 4 5 6 4 8.5S3 13.5 4 16c1 2.5 3 4.5 5.5 5.5L11 22V3.5z" fill="currentColor"/>
        {/* Right hemisphere */}
        <path d="M13 3.5C16.5 4 19 6 20 8.5s1 5 0 7.5c-1 2.5-3 4.5-5.5 5.5L13 22V3.5z" fill="currentColor"/>
        {/* Central fissure — bold gap */}
        <line x1="12" y1="3" x2="12" y2="22.5" stroke="white" strokeWidth="2.8" strokeLinecap="round"/>
        {/* Left lateral sulcus */}
        <path d="M4.5 11c2.5.5 4.5 0 7-1.5" stroke="white" strokeWidth="2" strokeLinecap="round"/>
        {/* Right lateral sulcus — mirror */}
        <path d="M19.5 11c-2.5.5-4.5 0-7-1.5" stroke="white" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    );
  }
  // Stroke-only brain — for larger display or dark-on-light
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
// Hooks
// ============================================================================
function useCountUp(target: number, duration = 1.8, decimals = 0) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-20px" });
  const started = useRef(false);

  useEffect(() => {
    if (!inView || started.current) return;
    started.current = true;
    const start = performance.now();
    const step = (now: number) => {
      const t = Math.min((now - start) / (duration * 1000), 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setCount(eased * target);
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [inView, target, duration]);

  return { value: decimals > 0 ? count.toFixed(decimals) : Math.round(count).toString(), ref };
}

// ============================================================================
// Rotating words hook
// ============================================================================
const HERO_WORDS = ["knowledge.", "insights.", "answers.", "action."];
function useRotatingWord(words: string[], intervalMs = 3000) {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setIndex((i) => (i + 1) % words.length), intervalMs);
    return () => clearInterval(id);
  }, [words.length, intervalMs]);
  return words[index];
}

function RotatingWord() {
  const word = useRotatingWord(HERO_WORDS, 3000);
  return (
    <span className="inline-block relative">
      <AnimatePresence mode="wait">
        <motion.span
          key={word}
          initial={{ opacity: 0, y: 20, filter: "blur(4px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          exit={{ opacity: 0, y: -20, filter: "blur(4px)" }}
          transition={{ duration: 0.4, ease: EASE }}
          className="inline-block bg-gradient-to-r from-indigo-600 via-violet-500 to-indigo-400 bg-clip-text text-transparent bg-[length:200%_100%] animate-[shimmer_4s_ease-in-out_infinite]"
        >
          {word}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

// ============================================================================
// Shared components
// ============================================================================
function DotGrid({ className = "", dark = false }: { className?: string; dark?: boolean }) {
  return (
    <div
      className={`absolute inset-0 pointer-events-none ${className}`}
      style={{
        backgroundImage: `radial-gradient(circle, ${dark ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.06)"} 1px, transparent 1px)`,
        backgroundSize: "24px 24px",
      }}
    />
  );
}

function GradientOrb({ className = "", color = "rgba(99,102,241,0.08)", size = 800 }: { className?: string; color?: string; size?: number }) {
  return (
    <div
      className={`absolute rounded-full pointer-events-none blur-3xl ${className}`}
      style={{ width: size, height: size, background: `radial-gradient(circle, ${color} 0%, transparent 70%)` }}
    />
  );
}

function SectionBadge({ icon: Icon, label, dark = false }: { icon: React.ElementType; label: string; dark?: boolean }) {
  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full border text-[11px] font-semibold tracking-wide uppercase mb-4 ${
      dark
        ? "border-white/[0.08] bg-white/[0.04] text-neutral-400"
        : "border-neutral-200/80 bg-white text-neutral-400"
    }`}>
      <Icon className="h-3 w-3" />
      {label}
    </div>
  );
}

function Marquee({ children, speed = 30 }: { children: React.ReactNode; speed?: number }) {
  return (
    <div className="overflow-hidden">
      <div className="flex whitespace-nowrap" style={{ animation: `marquee ${speed}s linear infinite` }}>
        <div className="flex shrink-0 items-center gap-4 pr-4">{children}</div>
        <div className="flex shrink-0 items-center gap-4 pr-4">{children}</div>
      </div>
      <style jsx>{`@keyframes marquee { from { transform: translateX(0); } to { transform: translateX(-50%); } }`}</style>
    </div>
  );
}

function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 100, damping: 30, restDelta: 0.001 });
  return (
    <motion.div
      className="fixed top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-indigo-500 via-violet-500 to-purple-500 z-[60] origin-left"
      style={{ scaleX }}
    />
  );
}

function SpotlightCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = cardRef.current?.getBoundingClientRect();
    if (rect) { setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top }); }
  };

  return (
    <div ref={cardRef} className={`relative ${className}`} onMouseMove={handleMouseMove} onMouseEnter={() => setIsHovered(true)} onMouseLeave={() => setIsHovered(false)}>
      {isHovered && (
        <div className="absolute inset-0 rounded-2xl pointer-events-none z-10 transition-opacity duration-300" style={{ background: `radial-gradient(400px circle at ${mousePos.x}px ${mousePos.y}px, rgba(99,102,241,0.06), transparent 60%)` }} />
      )}
      {children}
    </div>
  );
}

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

  // Close mobile menu on escape
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
        <div className="max-w-[1200px] mx-auto px-6 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="h-7 w-7 rounded-lg bg-neutral-900 flex items-center justify-center group-hover:scale-105 transition-transform">
              <SulciLogo className="h-4 w-4 text-white" variant="filled" />
            </div>
            <span className="font-semibold text-[15px] tracking-[-0.02em] text-neutral-900">Sulci</span>
          </Link>
          <div className="hidden md:flex items-center gap-0.5 text-[13px]">
            {["Product", "Docs", "Contact Sales", "Changelog"].map((item) => (
              <Link key={item} href="/dashboard" className="px-3 py-1.5 rounded-md text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100/80 transition-all duration-150">
                {item}
              </Link>
            ))}
          </div>
          <div className="flex items-center gap-2">
            {/* Keyboard shortcut hint */}
            <button className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-neutral-200/80 bg-neutral-50/80 text-[11px] font-medium text-neutral-400 hover:text-neutral-600 hover:border-neutral-300 transition-all">
              <Search className="h-3 w-3" />
              <span>Search</span>
              <kbd className="ml-1 flex items-center gap-0.5 px-1 py-0.5 rounded bg-white border border-neutral-200 text-[10px] font-mono text-neutral-400 shadow-[0_1px_0_rgba(0,0,0,0.05)]">
                <Command className="h-2.5 w-2.5" />K
              </kbd>
            </button>
            <Link href="/login" className="hidden md:block">
              <Button variant="ghost" size="sm" className="text-neutral-500 text-[13px] h-8 hover:text-neutral-900">Sign in</Button>
            </Link>
            <Link href="/dashboard" className="hidden md:block">
              <Button size="sm" className="bg-neutral-900 text-white hover:bg-neutral-800 text-[13px] rounded-lg h-8 px-3.5 shadow-sm">
                Request Demo <ArrowRight className="ml-1 h-3 w-3" />
              </Button>
            </Link>
            {/* Mobile hamburger */}
            <button className="md:hidden p-1.5 rounded-lg hover:bg-neutral-100 transition-colors" onClick={() => setMobileOpen(!mobileOpen)}>
              {mobileOpen ? <X className="h-5 w-5 text-neutral-700" /> : <Menu className="h-5 w-5 text-neutral-700" />}
            </button>
          </div>
        </div>
      </motion.nav>

      {/* Mobile menu overlay */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm md:hidden" onClick={() => setMobileOpen(false)} />
            <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.2, ease: EASE }} className="fixed top-14 left-0 right-0 z-50 md:hidden">
              <div className="mx-4 mt-2 rounded-2xl border border-neutral-200/80 bg-white/95 backdrop-blur-2xl shadow-[0_8px_40px_rgba(0,0,0,0.12)] p-4">
                <div className="space-y-1">
                  {["Product", "Docs", "Contact Sales", "Changelog"].map((item) => (
                    <Link key={item} href="/dashboard" onClick={() => setMobileOpen(false)} className="flex items-center px-3 py-2.5 rounded-lg text-[15px] font-medium text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900 transition-colors">
                      {item}
                    </Link>
                  ))}
                </div>
                <div className="mt-3 pt-3 border-t border-neutral-100 space-y-2">
                  <Link href="/login" onClick={() => setMobileOpen(false)} className="block">
                    <Button variant="outline" className="w-full h-10 text-[14px] rounded-xl">Sign in</Button>
                  </Link>
                  <Link href="/dashboard" onClick={() => setMobileOpen(false)} className="block">
                    <Button className="w-full h-10 text-[14px] rounded-xl bg-neutral-900 text-white hover:bg-neutral-800">
                      Request Demo <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
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
      {/* Left: Clinical note with highlighted entities */}
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

      {/* Right: Extracted concepts appearing one by one */}
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
  const mouseX = useMotionValue(0.5);
  const mouseY = useMotionValue(0.5);
  const smoothX = useSpring(mouseX, { stiffness: 40, damping: 20 });
  const smoothY = useSpring(mouseY, { stiffness: 40, damping: 20 });

  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], [0, 100]);
  const opacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);

  useEffect(() => {
    const el = heroRef.current;
    if (!el) return;
    const handler = (e: MouseEvent) => {
      const r = el.getBoundingClientRect();
      mouseX.set((e.clientX - r.left) / r.width);
      mouseY.set((e.clientY - r.top) / r.height);
    };
    el.addEventListener("mousemove", handler);
    return () => el.removeEventListener("mousemove", handler);
  }, [mouseX, mouseY]);

  return (
    <section ref={heroRef} className="relative pt-14 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-neutral-50 via-white to-white" />
      <DotGrid className="opacity-40" />
      <motion.div
        className="absolute pointer-events-none blur-[120px] rounded-full"
        style={{
          width: 800, height: 800,
          left: useTransform(smoothX, (v) => `${v * 100 - 40}%`),
          top: useTransform(smoothY, (v) => `${v * 100 - 40}%`),
          background: "radial-gradient(circle, rgba(99,102,241,0.08) 0%, rgba(168,85,247,0.04) 40%, transparent 70%)",
        }}
      />

      <motion.div style={{ y, opacity }} className="relative">
        <div className="max-w-[1200px] mx-auto px-6 pt-20 md:pt-28 pb-4">
          <motion.div variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } } }} initial="hidden" animate="visible" className="text-center">
            <motion.div variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } } }} className="mb-6">
              <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-neutral-200/80 bg-white/80 backdrop-blur-sm text-[12px] font-medium text-neutral-500 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-500">
                  <Sparkles className="h-2.5 w-2.5 text-white" />
                </span>
                Now with GraphRAG-powered querying
                <ChevronRight className="h-3 w-3 text-neutral-400" />
              </span>
            </motion.div>

            <motion.h1 variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } } }} className="text-[3rem] md:text-[4.25rem] lg:text-[5rem] font-bold leading-[1.05] tracking-[-0.045em] text-neutral-900">
              Turn clinical notes<br />
              into <RotatingWord />
            </motion.h1>

            <motion.p variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } } }} className="mt-5 text-[17px] md:text-[19px] text-neutral-500 max-w-[560px] mx-auto leading-[1.6] tracking-[-0.01em]" style={{ textWrap: "balance" }}>
              80% of clinical data is trapped in unstructured text. Sulci extracts, normalizes, and connects it into knowledge your AI can reason over — in minutes, not months.
            </motion.p>

            <motion.div variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } } }} className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link href="/dashboard">
                <Button className="group bg-neutral-900 text-white hover:bg-neutral-800 rounded-xl h-11 px-7 text-[14px] font-medium shadow-[0_1px_2px_rgba(0,0,0,0.1),0_4px_12px_rgba(0,0,0,0.06)] hover:shadow-[0_1px_2px_rgba(0,0,0,0.12),0_8px_24px_rgba(0,0,0,0.1)] transition-all duration-200">
                  Request a Demo <ArrowRight className="ml-1.5 h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform" />
                </Button>
              </Link>
              <Link href="/login">
                <Button variant="outline" className="rounded-xl h-11 px-7 text-[14px] font-medium text-neutral-600 border-neutral-200 bg-white/80 backdrop-blur-sm hover:bg-white hover:border-neutral-300 transition-all duration-200">
                  <Play className="mr-1.5 h-3.5 w-3.5" /> See It in Action
                </Button>
              </Link>
            </motion.div>
          </motion.div>
        </div>

        {/* Video */}
        <motion.div initial={{ opacity: 0, y: 60, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.9, delay: 0.35, ease: EASE }} className="relative max-w-[1080px] mx-auto mt-12 md:mt-16 px-6">
          <div className="absolute -inset-4 top-4 rounded-3xl pointer-events-none" style={{ background: "radial-gradient(ellipse 80% 60% at 50% 40%, rgba(99,102,241,0.12) 0%, rgba(168,85,247,0.06) 40%, transparent 70%)", filter: "blur(40px)" }} />
          <div className="absolute inset-0 top-12 rounded-3xl pointer-events-none animate-pulse" style={{ background: "radial-gradient(ellipse at 50% 30%, rgba(99,102,241,0.05) 0%, transparent 60%)", animationDuration: "4s" }} />
          <div className="relative rounded-2xl border border-neutral-200/80 bg-neutral-950 shadow-[0_0_0_1px_rgba(0,0,0,0.03),0_2px_4px_rgba(0,0,0,0.04),0_12px_40px_rgba(0,0,0,0.12),0_24px_80px_rgba(0,0,0,0.08)] overflow-hidden ring-1 ring-neutral-200/40 ring-offset-4 ring-offset-white">
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
          <div className="h-28 bg-gradient-to-t from-white via-white/90 to-transparent -mt-px relative z-10" />
          {/* Reflection glow */}
          <div className="absolute -bottom-8 left-[10%] right-[10%] h-16 rounded-full opacity-40 pointer-events-none" style={{ background: "radial-gradient(ellipse at 50% 0%, rgba(99,102,241,0.15) 0%, transparent 70%)", filter: "blur(20px)" }} />
        </motion.div>
      </motion.div>
    </section>
  );
}

// ============================================================================
// STATS — animated counters
// ============================================================================
function StatsSection() {
  const s1 = useCountUp(60, 1.8);
  const s2 = useCountUp(93.9, 1.8, 1);
  const s3 = useCountUp(85, 1.8);
  const s4 = useCountUp(50, 1.8);

  const stats = [
    { ...s1, suffix: "x", label: "Faster Abstraction", sublabel: "Chart review in minutes, not days" },
    { ...s2, suffix: "%", label: "Concept Accuracy", sublabel: "Benchmarked against expert abstractors" },
    { ...s3, suffix: "%", label: "Signal Captured", sublabel: "vs. 30% with manual extraction" },
    { ...s4, suffix: "ms", prefix: "<", label: "P95 Latency", sublabel: "Real-time graph query response" },
  ];

  return (
    <section className="py-16 md:py-24">
      <div className="max-w-[1200px] mx-auto px-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-0 md:divide-x divide-neutral-200/60">
          {stats.map((s) => (
            <div key={s.label} ref={s.ref} className="text-center px-4 md:px-8 group">
              <div className="text-[2.25rem] md:text-[2.75rem] font-bold tracking-[-0.04em] text-neutral-900 tabular-nums group-hover:text-indigo-600 transition-colors duration-300">
                {"prefix" in s ? s.prefix : ""}{s.value}{s.suffix}
              </div>
              <div className="text-[13px] font-semibold text-neutral-700 mt-1">{s.label}</div>
              <div className="text-[12px] text-neutral-400 mt-0.5">{s.sublabel}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// PROBLEM FRAMING
// ============================================================================
const problems = [
  { stat: "$13B", label: "lost annually to manual chart abstraction", detail: "Health systems spend billions on human abstractors reviewing notes for quality measures, risk adjustment, and research." },
  { stat: "72h", label: "average chart abstraction time", detail: "Manual review per patient for quality measures, research, and coding. At scale, this means months of delay per study." },
  { stat: "30%", label: "of clinical signal is never captured", detail: "Negation, temporality, and context lost in translation — each missed finding costs an average of $2,500 in downstream rework." },
];

function ProblemSection() {
  return (
    <section className="py-16 md:py-24 px-6 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-neutral-50/60 to-white pointer-events-none" />
      <div className="relative max-w-[1200px] mx-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, ease: EASE }} className="text-center mb-12">
          <p className="text-[13px] font-medium text-rose-500 mb-2">The problem</p>
          <h2 className="text-[1.75rem] md:text-[2.25rem] font-medium tracking-[-0.03em] text-neutral-900 leading-[1.15]" style={{ textWrap: "balance" }}>
            Your smartest data is your dumbest asset.
          </h2>
        </motion.div>
        <div className="grid md:grid-cols-3 gap-4">
          {problems.map((p, i) => (
            <motion.div key={p.label} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.4, delay: i * 0.08, ease: EASE }}>
              <div className="h-full rounded-2xl border border-rose-100/80 bg-gradient-to-b from-rose-50/40 to-white p-6 hover:border-rose-200 hover:shadow-[0_8px_40px_rgba(244,63,94,0.06)] transition-all duration-300">
                <div className="text-[2.5rem] font-bold tracking-[-0.04em] text-rose-500/80 mb-1">{p.stat}</div>
                <div className="text-[14px] font-semibold text-neutral-900 mb-2">{p.label}</div>
                <p className="text-[13px] text-neutral-500 leading-relaxed">{p.detail}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// HOW IT WORKS — 3-step pipeline flow
// ============================================================================
const steps = [
  {
    number: "01",
    icon: FileText,
    title: "Ingest",
    headline: "Drop in unstructured notes",
    description: "Upload clinical documents — physician notes, radiology reports, discharge summaries, pathology results. Any format, any EHR.",
    color: "from-rose-500 to-pink-500",
    bg: "bg-rose-50",
  },
  {
    number: "02",
    icon: Cpu,
    title: "Extract & Normalize",
    headline: "AI maps to standard ontologies",
    description: "Our NLP pipeline extracts clinical mentions, classifies assertion status, and maps to SNOMED, ICD-10, LOINC, RxNorm, and OMOP CDM — automatically.",
    color: "from-indigo-500 to-violet-500",
    bg: "bg-indigo-50",
  },
  {
    number: "03",
    icon: Network,
    title: "Query & Reason",
    headline: "Structured knowledge, ready for AI",
    description: "Query your patient knowledge graph with natural language or GraphRAG. Temporal relationships, drug interactions, and lab trajectories — all connected.",
    color: "from-emerald-500 to-teal-500",
    bg: "bg-emerald-50",
  },
];

function HowItWorks() {
  return (
    <section className="py-20 md:py-28 px-6 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-white via-neutral-50/40 to-white pointer-events-none" />
      <div className="relative max-w-[1200px] mx-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, ease: EASE }} className="text-center mb-16">
          <SectionBadge icon={Workflow} label="How It Works" />
          <h2 className="text-[2rem] md:text-[2.75rem] font-medium tracking-[-0.035em] text-neutral-900 leading-[1.1]">
            Three steps to <span className="bg-gradient-to-r from-indigo-600 to-violet-500 bg-clip-text text-transparent">structured knowledge</span>
          </h2>
          <p className="mt-4 text-neutral-500 max-w-lg mx-auto text-[15.5px] leading-relaxed" style={{ textWrap: "balance" }}>
            From raw clinical text to a queryable knowledge graph in minutes.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-6 relative">
          {/* Connecting line */}
          <div className="hidden md:block absolute top-[72px] left-[16.67%] right-[16.67%] h-[2px] bg-gradient-to-r from-rose-200 via-indigo-200 to-emerald-200 z-0" />

          {steps.map((step, i) => (
            <motion.div
              key={step.title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={VIEWPORT}
              transition={{ duration: 0.5, delay: i * 0.12, ease: EASE }}
              className="relative z-10"
            >
              <div className="text-center">
                {/* Step number circle */}
                <div className="relative mx-auto mb-6">
                  <div className={`h-[72px] w-[72px] rounded-2xl ${step.bg} flex items-center justify-center mx-auto shadow-sm`}>
                    <step.icon className="h-7 w-7 text-neutral-700" />
                  </div>
                  <div className={`absolute -top-2 -right-2 h-7 w-7 rounded-full bg-gradient-to-br ${step.color} flex items-center justify-center shadow-sm`}>
                    <span className="text-[10px] font-bold text-white">{step.number}</span>
                  </div>
                </div>
                <p className={`text-[11px] font-semibold tracking-[0.08em] uppercase bg-gradient-to-r ${step.color} bg-clip-text text-transparent mb-2`}>{step.title}</p>
                <h3 className="text-[18px] font-semibold tracking-[-0.02em] text-neutral-900 mb-2">{step.headline}</h3>
                <p className="text-[13.5px] text-neutral-500 leading-relaxed max-w-[280px] mx-auto">{step.description}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// WHY NOW — AI moment positioning
// ============================================================================
function WhyNowSection() {
  return (
    <section className="py-20 md:py-28 px-6 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-neutral-950 to-neutral-900" />
      <DotGrid className="opacity-10" />
      <div className="relative max-w-[900px] mx-auto text-center">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.6, ease: EASE }}>
          <p className="text-[12px] font-semibold tracking-[0.1em] uppercase text-indigo-400 mb-4">Why now</p>
          <h2 className="text-[2rem] md:text-[2.75rem] font-medium tracking-[-0.035em] text-white leading-[1.15]" style={{ textWrap: "balance" }}>
            LLMs can generate text.<br />They can&apos;t reason over your clinical data <span className="text-neutral-500">without a knowledge backbone.</span>
          </h2>
          <p className="mt-6 text-[16px] text-neutral-400 max-w-[640px] mx-auto leading-[1.7]" style={{ textWrap: "balance" }}>
            Every health system is racing to deploy AI. But AI hallucinations in healthcare aren&apos;t just wrong — they&apos;re dangerous. Sulci provides the structured, ontology-grounded knowledge layer that makes clinical AI safe, auditable, and accurate.
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            {[
              "Grounded in UMLS & OMOP standards",
              "Full provenance tracking",
              "Auditable extraction pipeline",
              "No black-box inference",
            ].map((item) => (
              <span key={item} className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-white/10 bg-white/[0.03] text-[12px] text-neutral-300 font-medium">
                <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                {item}
              </span>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ============================================================================
// COMPLIANCE & SECURITY — enterprise trust signals
// ============================================================================
function ComplianceSection() {
  const badges = [
    { name: "HIPAA", detail: "Compliant", icon: Shield },
    { name: "SOC 2", detail: "Type II", icon: Lock },
    { name: "BAA", detail: "Available", icon: FileText },
    { name: "FHIR R4", detail: "Certified", icon: Activity },
    { name: "OMOP CDM", detail: "v5.4", icon: Database },
    { name: "21 CFR Part 11", detail: "Ready", icon: CheckCircle2 },
  ];
  return (
    <section className="py-16 md:py-20 px-6">
      <div className="max-w-[1200px] mx-auto">
        <motion.div initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, ease: EASE }} className="text-center mb-10">
          <p className="text-[11px] font-semibold tracking-[0.12em] uppercase text-neutral-400 mb-2">Enterprise-grade security & compliance</p>
          <p className="text-[14px] text-neutral-500">Built for regulated environments from day one.</p>
        </motion.div>
        <div className="grid grid-cols-3 md:grid-cols-6 gap-3 max-w-[800px] mx-auto">
          {badges.map((badge, i) => (
            <motion.div
              key={badge.name}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={VIEWPORT}
              transition={{ duration: 0.4, delay: i * 0.04, ease: EASE }}
              className="flex flex-col items-center gap-1.5 p-4 rounded-xl border border-neutral-200/60 bg-gradient-to-b from-white to-neutral-50/50 hover:border-neutral-300 hover:shadow-sm transition-all"
            >
              <badge.icon className="h-5 w-5 text-neutral-400" />
              <span className="text-[12px] font-semibold text-neutral-700">{badge.name}</span>
              <span className="text-[10px] text-neutral-400">{badge.detail}</span>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// CORE ENGINES
// ============================================================================
const engines = [
  { icon: Brain, gradient: "from-violet-500/10 to-violet-500/5", iconBg: "bg-violet-500", label: "Extract", title: "Clinical NLP",
    description: "Rule-based and transformer ensemble pipelines that extract clinical mentions from unstructured notes. Assertion, negation, temporality, and experiencer built in.",
    features: ["Named entity recognition for conditions, meds, procedures", "Assertion classification (present, absent, possible)", "Section-aware processing (HPI, Assessment, Plan)", "Temporal relationship extraction"] },
  { icon: Database, gradient: "from-blue-500/10 to-blue-500/5", iconBg: "bg-blue-500", label: "Normalize", title: "Ontology Mapping",
    description: "Map extracted concepts to UMLS, OMOP, and custom ontologies with candidate ranking, confidence scoring, and full provenance tracking across the entire UMLS Metathesaurus.",
    features: ["Full UMLS Metathesaurus (SNOMED, ICD-10, LOINC, RxNorm, MeSH...)", "OMOP CDM concept mapping with vocabulary versioning", "Ranked candidates with confidence scores", "Custom ontology support for institution-specific codes"] },
  { icon: GitBranch, gradient: "from-emerald-500/10 to-emerald-500/5", iconBg: "bg-emerald-500", label: "Connect", title: "Knowledge Graph",
    description: "Build queryable patient knowledge graphs from normalized facts. Temporal relationships, drug-condition links, and lab trajectories — all connected and traversable.",
    features: ["Patient-centric graph with clinical edges", "Drug-condition and drug-drug interactions", "GraphRAG natural language querying", "Neo4j persistence + in-memory projection"] },
];

function CoreEngines() {
  return (
    <section className="py-20 md:py-28 px-6 relative">
      <div className="absolute inset-0 bg-gradient-to-b from-white via-neutral-50/60 to-white pointer-events-none" />
      <div className="relative max-w-[1200px] mx-auto">
        <div className="text-center mb-14">
          <SectionBadge icon={Cpu} label="Core Engines" />
          <h2 className="text-[2rem] md:text-[2.75rem] font-medium tracking-[-0.035em] text-neutral-900 leading-[1.1]">Three engines. <span className="bg-gradient-to-r from-violet-600 to-indigo-600 bg-clip-text text-transparent">One pipeline.</span></h2>
          <p className="mt-4 text-neutral-500 max-w-lg mx-auto text-[15.5px] leading-relaxed" style={{ textWrap: "balance" }}>
            Each fold adds depth and connectivity. Extract mentions, normalize to ontologies, and connect through a temporal knowledge graph.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          {engines.map((engine, i) => {
            const Icon = engine.icon;
            return (
              <motion.div key={engine.title} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, delay: i * 0.08, ease: EASE }} className="group">
                <div className={`relative h-full rounded-2xl border border-neutral-200/80 bg-gradient-to-b ${engine.gradient} p-6 transition-all duration-300 hover:border-neutral-300/90 hover:shadow-[0_8px_40px_rgba(0,0,0,0.08)] overflow-hidden`}>
                  <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none bg-gradient-to-t from-transparent via-transparent to-white/40" />
                  <div className="relative">
                    <div className="flex items-center gap-3 mb-5">
                      <div className={`h-9 w-9 rounded-xl flex items-center justify-center ${engine.iconBg} group-hover:scale-110 transition-transform duration-300`}>
                        <Icon className="h-4 w-4 text-white" />
                      </div>
                      <span className="text-[11px] font-bold tracking-[0.08em] uppercase text-neutral-400">{engine.label}</span>
                      <span className="ml-auto text-[11px] font-mono font-bold text-neutral-200 group-hover:text-neutral-300 transition-colors">{String(i + 1).padStart(2, "0")}</span>
                    </div>
                    <h3 className="font-semibold text-[18px] tracking-[-0.02em] text-neutral-900 mb-2.5">{engine.title}</h3>
                    <p className="text-[13.5px] text-neutral-500 leading-[1.6] mb-5">{engine.description}</p>
                    <div className="space-y-2 pt-4 border-t border-neutral-200/50">
                      {engine.features.map((f) => (
                        <div key={f} className="flex items-start gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500/60 mt-0.5 flex-shrink-0" />
                          <span className="text-[12.5px] text-neutral-500 leading-snug">{f}</span>
                        </div>
                      ))}
                    </div>
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
// ANIMATED KNOWLEDGE GRAPH
// ============================================================================
const KG_NODES = [
  { id: "patient", x: 50, y: 50, label: "Patient", color: "#6366f1", r: 24 },
  { id: "t2dm", x: 18, y: 25, label: "T2DM", color: "#f43f5e", r: 18 },
  { id: "htn", x: 82, y: 22, label: "HTN", color: "#3b82f6", r: 16 },
  { id: "ckd", x: 15, y: 75, label: "CKD 3", color: "#8b5cf6", r: 17 },
  { id: "metformin", x: 85, y: 72, label: "Metformin", color: "#10b981", r: 18 },
  { id: "lisinopril", x: 50, y: 88, label: "Lisinopril", color: "#10b981", r: 17 },
  { id: "a1c", x: 82, y: 48, label: "A1c 8.2%", color: "#f59e0b", r: 15 },
  { id: "egfr", x: 18, y: 50, label: "eGFR", color: "#f59e0b", r: 14 },
];
const KG_EDGES: [string, string][] = [
  ["patient", "t2dm"], ["patient", "htn"], ["patient", "ckd"],
  ["patient", "metformin"], ["patient", "lisinopril"],
  ["t2dm", "a1c"], ["ckd", "egfr"],
  ["metformin", "t2dm"], ["lisinopril", "htn"], ["lisinopril", "ckd"],
];

function KnowledgeGraphViz() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  const nodeMap = Object.fromEntries(KG_NODES.map((n) => [n.id, n]));

  return (
    <section ref={ref} className="py-4 md:py-8 px-6">
      <div className="max-w-[720px] mx-auto">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={inView ? { opacity: 1, scale: 1 } : {}}
          transition={{ duration: 0.8, ease: EASE }}
          className="relative rounded-2xl border border-neutral-200/60 bg-gradient-to-b from-neutral-50/80 to-white p-4 overflow-hidden"
        >
          <div className="absolute top-3 left-4 flex items-center gap-2">
            <div className="h-5 w-5 rounded-md bg-indigo-50 flex items-center justify-center"><Network className="h-3 w-3 text-indigo-500" /></div>
            <span className="text-[11px] font-semibold text-neutral-400 tracking-wide uppercase">Live Knowledge Graph</span>
          </div>
          <svg viewBox="0 0 100 100" className="w-full" style={{ maxHeight: 320 }}>
            {/* Edges */}
            {KG_EDGES.map(([from, to], i) => {
              const a = nodeMap[from];
              const b = nodeMap[to];
              return (
                <motion.line
                  key={`${from}-${to}`}
                  x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke="url(#edge-gradient)"
                  strokeWidth={0.4}
                  strokeOpacity={0.3}
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={inView ? { pathLength: 1, opacity: 1 } : {}}
                  transition={{ duration: 0.6, delay: 0.2 + i * 0.06, ease: EASE }}
                />
              );
            })}
            {/* Animated pulse on edges */}
            {inView && KG_EDGES.map(([from, to], i) => {
              const a = nodeMap[from];
              const b = nodeMap[to];
              return (
                <circle key={`pulse-${from}-${to}`} r={0.8} fill={nodeMap[to].color} opacity={0.6}>
                  <animateMotion
                    dur={`${2.5 + i * 0.3}s`}
                    repeatCount="indefinite"
                    begin={`${i * 0.2}s`}
                    path={`M${a.x},${a.y} L${b.x},${b.y}`}
                  />
                </circle>
              );
            })}
            {/* Gradient def */}
            <defs>
              <linearGradient id="edge-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#6366f1" stopOpacity={0.4} />
                <stop offset="100%" stopColor="#a855f7" stopOpacity={0.2} />
              </linearGradient>
            </defs>
            {/* Nodes */}
            {KG_NODES.map((node, i) => (
              <motion.g
                key={node.id}
                initial={{ opacity: 0, scale: 0 }}
                animate={inView ? { opacity: 1, scale: 1 } : {}}
                transition={{ duration: 0.4, delay: 0.1 + i * 0.06, ease: EASE }}
                style={{ transformOrigin: `${node.x}px ${node.y}px` }}
              >
                <circle cx={node.x} cy={node.y} r={node.r / 4} fill={node.color} opacity={0.08} />
                <circle cx={node.x} cy={node.y} r={node.r / 6} fill={node.color} opacity={0.15} />
                <circle cx={node.x} cy={node.y} r={node.r / 10} fill={node.color} />
                <text x={node.x} y={node.y + node.r / 4 + 3.5} textAnchor="middle" className="text-[2.8px] font-semibold" fill="#525252">
                  {node.label}
                </text>
              </motion.g>
            ))}
          </svg>
        </motion.div>
      </div>
    </section>
  );
}

// ============================================================================
// DATA TRANSFORMATION
// ============================================================================
function DataTransformation() {
  return (
    <section className="py-20 md:py-28 px-6 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-neutral-50/50 to-white pointer-events-none" />
      <DotGrid className="opacity-20" />
      <div className="relative max-w-[1200px] mx-auto">
        <div className="text-center mb-14">
          <SectionBadge icon={Code2} label="How It Works" />
          <h2 className="text-[2rem] md:text-[2.75rem] font-medium tracking-[-0.035em] text-neutral-900 leading-[1.1]">See the <span className="bg-gradient-to-r from-indigo-600 to-violet-500 bg-clip-text text-transparent">transformation</span></h2>
          <p className="mt-4 text-neutral-500 max-w-lg mx-auto text-[15.5px] leading-relaxed" style={{ textWrap: "balance" }}>
            From a messy clinical note to structured, ontology-mapped clinical facts — in one API call.
          </p>
        </div>

        {/* Steps */}
        <div className="flex items-center justify-center gap-3 mb-10">
          {[{ num: "1", label: "Ingest", icon: FileText }, { num: "2", label: "Extract & Map", icon: Workflow }, { num: "3", label: "Query", icon: Search }].map((step, i) => {
            const Icon = step.icon;
            return (
              <div key={step.num} className="flex items-center gap-3">
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white border border-neutral-200/80">
                  <div className="h-5 w-5 rounded-md bg-neutral-900 flex items-center justify-center text-[10px] font-bold text-white">{step.num}</div>
                  <Icon className="h-3.5 w-3.5 text-neutral-400" />
                  <span className="text-[12px] font-medium text-neutral-600">{step.label}</span>
                </div>
                {i < 2 && <ChevronRight className="h-3.5 w-3.5 text-neutral-300" />}
              </div>
            );
          })}
        </div>

        <div className="grid md:grid-cols-2 gap-4 max-w-[900px] mx-auto relative">
          {/* Connecting arrow (visible on md+) */}
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
    <section className="py-20 md:py-28 relative overflow-hidden bg-neutral-950">
      <DotGrid dark />
      <GradientOrb className="top-[-200px] right-[-200px]" color="rgba(99,102,241,0.06)" size={600} />
      <GradientOrb className="bottom-[-200px] left-[-200px]" color="rgba(168,85,247,0.04)" size={500} />

      <div className="relative max-w-[1200px] mx-auto px-6">
        <div className="grid md:grid-cols-2 gap-12 md:gap-16 items-center">
          <div>
            <SectionBadge icon={Terminal} label="Developer Experience" dark />
            <h2 className="text-[2rem] md:text-[2.75rem] font-medium tracking-[-0.035em] text-white leading-[1.1]">
              Ship in minutes,<br /><span className="text-neutral-500">not months.</span>
            </h2>
            <p className="mt-4 text-neutral-400 text-[15.5px] leading-relaxed max-w-[420px]" style={{ textWrap: "balance" }}>
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
            <div className="mt-8 flex items-center gap-3">
              <Link href="/dashboard">
                <Button className="bg-white text-neutral-900 hover:bg-neutral-100 rounded-xl h-10 px-5 text-[13px] font-medium">
                  Read the Docs <ArrowRight className="ml-1.5 h-3 w-3" />
                </Button>
              </Link>
              <Link href="/dashboard">
                <Button variant="outline" className="rounded-xl h-10 px-5 text-[13px] font-medium text-neutral-400 border-white/[0.1] bg-transparent hover:bg-white/[0.04] hover:text-white">
                  <ExternalLink className="mr-1.5 h-3 w-3" /> API Reference
                </Button>
              </Link>
            </div>
            {/* Response preview */}
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
                    <div className="h-2 w-2 rounded-full bg-emerald-400/60 animate-pulse" style={{ animationDuration: "3s" }} />
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
    { icon: HeartPulse, iconColor: "text-rose-500", iconBg: "bg-rose-50", title: "FHIR R4 Interoperability", description: "Import and export complete patient records as FHIR R4 Bundles. Conditions, medications, observations, and procedures mapped automatically.", size: "md:col-span-2", resources: ["Conditions", "Medications", "Observations", "Procedures", "Allergies", "Immunizations"] },
    { icon: FlaskConical, iconColor: "text-indigo-500", iconBg: "bg-indigo-50", title: "Clinical Trials", description: "Automated eligibility screening. Cohort matching against I/E criteria with patient ranking.", size: "md:col-span-1" },
    { icon: Shield, iconColor: "text-amber-500", iconBg: "bg-amber-50", title: "Drug Safety", description: "Adverse event detection, pharmacovigilance signals, and drug interaction checking.", size: "md:col-span-1" },
    { icon: BarChart3, iconColor: "text-emerald-500", iconBg: "bg-emerald-50", title: "Billing & Coding", description: "ICD-10, CPT, DRG code suggestion from clinical facts. Automated coding validation.", size: "md:col-span-1" },
    { icon: Pill, iconColor: "text-violet-500", iconBg: "bg-violet-50", title: "Medications & Dosing", description: "RxNorm mapping with interaction checking and clinical calculator integration.", size: "md:col-span-1" },
  ];

  return (
    <section className="py-20 md:py-28 px-6">
      <div className="max-w-[1200px] mx-auto">
        <div className="text-center mb-14">
          <SectionBadge icon={Layers} label="Platform" />
          <h2 className="text-[2rem] md:text-[2.75rem] font-medium tracking-[-0.035em] text-neutral-900 leading-[1.1]">Built for the full <span className="bg-gradient-to-r from-indigo-600 to-emerald-500 bg-clip-text text-transparent">clinical stack</span></h2>
          <p className="mt-4 text-neutral-500 max-w-lg mx-auto text-[15.5px] leading-relaxed" style={{ textWrap: "balance" }}>
            From ingestion to interoperability — every layer of clinical data processing in one platform.
          </p>
        </div>
        <div className="grid md:grid-cols-3 gap-4">
          {cards.map((card, i) => {
            const Icon = card.icon;
            return (
              <motion.div key={card.title} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, delay: i * 0.06, ease: EASE }} className={card.size}>
                <SpotlightCard className="h-full">
                  <div className="group h-full rounded-2xl border border-neutral-200/80 bg-gradient-to-b from-white to-neutral-50/50 p-6 transition-all duration-300 hover:border-neutral-300/90 hover:shadow-[0_8px_40px_rgba(0,0,0,0.06)] hover:-translate-y-0.5">
                    <div className={`h-10 w-10 rounded-xl flex items-center justify-center ${card.iconBg} mb-4 group-hover:scale-110 transition-transform duration-300`}><Icon className={`h-5 w-5 ${card.iconColor}`} /></div>
                    <h3 className="font-semibold text-[16px] tracking-[-0.01em] text-neutral-900 mb-2">{card.title}</h3>
                    <p className="text-[13.5px] text-neutral-500 leading-relaxed">{card.description}</p>
                    {card.resources && (
                      <div className="mt-4 flex flex-wrap gap-1.5">
                        {card.resources.map((r) => (
                          <span key={r} className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-neutral-50 text-neutral-500 border border-neutral-100">{r}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </SpotlightCard>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// STANDARDS & SECURITY
// ============================================================================
const vocabs = ["UMLS Metathesaurus", "OMOP CDM v5.4", "FHIR R4", "SNOMED CT", "ICD-10-CM", "LOINC", "RxNorm", "MeSH", "CPT", "NDC", "CDS Hooks", "SMART on FHIR"];

function StandardsSection() {
  return (
    <section className="py-20 md:py-28 px-6 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-neutral-50/30 to-white pointer-events-none" />
      <div className="relative max-w-[1200px] mx-auto">
        <div className="grid md:grid-cols-2 gap-12 md:gap-20">
          <div>
            <SectionBadge icon={Binary} label="Standards" />
            <h3 className="text-[1.5rem] font-medium tracking-[-0.02em] text-neutral-900 mb-3">Full UMLS Metathesaurus and beyond.</h3>
            <p className="text-[14px] text-neutral-500 leading-relaxed mb-6" style={{ textWrap: "balance" }}>
              Native support for the entire UMLS Metathesaurus, OMOP CDM, and custom ontologies. Over 200 source vocabularies, zero custom adapters.
            </p>
            <div className="flex flex-wrap gap-2">
              {vocabs.map((v) => (
                <span key={v} className="px-3 py-1.5 text-[12px] rounded-lg bg-white text-neutral-600 border border-neutral-200/80 font-mono font-medium shadow-[0_1px_2px_rgba(0,0,0,0.03)] hover:border-neutral-300 transition-colors">{v}</span>
              ))}
            </div>
          </div>
          <div>
            <SectionBadge icon={Lock} label="Security" />
            <h3 className="text-[1.5rem] font-medium tracking-[-0.02em] text-neutral-900 mb-3">Enterprise-grade from day one.</h3>
            <p className="text-[14px] text-neutral-500 leading-relaxed mb-6" style={{ textWrap: "balance" }}>
              Built for regulated environments. Every action logged, every record encrypted, every access controlled.
            </p>
            <div className="grid grid-cols-2 gap-3">
              {[{ icon: Shield, label: "HIPAA", desc: "End-to-end encryption" }, { icon: Lock, label: "SOC 2 Type II", desc: "Audited controls" }, { icon: FileText, label: "21 CFR Part 11", desc: "Electronic records" }, { icon: Activity, label: "Audit Trail", desc: "Every action logged" }].map(({ icon: Icon, label, desc }) => (
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
// INTEGRATIONS — marquee
// ============================================================================
function IntegrationsSection() {
  const row1 = [
    { icon: HeartPulse, label: "Epic" }, { icon: Database, label: "Cerner" }, { icon: Globe, label: "Carequality" },
    { icon: Network, label: "CommonWell" }, { icon: Zap, label: "Metriport" }, { icon: Activity, label: "eHealth Exchange" },
    { icon: FileText, label: "Athenahealth" }, { icon: Shield, label: "Allscripts" },
  ];
  const row2 = [
    { icon: Layers, label: "Veeva Vault" }, { icon: Database, label: "Snowflake" }, { icon: Binary, label: "Databricks" },
    { icon: Globe, label: "AWS HealthLake" }, { icon: Shield, label: "Azure FHIR" }, { icon: Network, label: "Google FHIR" },
    { icon: Workflow, label: "Redox" }, { icon: Cpu, label: "Health Gorilla" },
  ];
  return (
    <div className="py-16 md:py-20 overflow-hidden">
      <p className="text-[11px] font-semibold tracking-[0.12em] uppercase text-neutral-400 mb-8 text-center">Connects to your existing infrastructure</p>
      <div className="space-y-3">
        <Marquee speed={25}>
          {row1.map(({ icon: Icon, label }) => (
            <div key={label} className="flex items-center gap-2.5 px-5 py-2.5 rounded-xl bg-white border border-neutral-200/80 shadow-[0_1px_2px_rgba(0,0,0,0.03)] hover:border-neutral-300 transition-colors">
              <Icon className="h-4 w-4 text-neutral-400" />
              <span className="text-[13px] font-medium text-neutral-600">{label}</span>
            </div>
          ))}
        </Marquee>
        <div className="[direction:rtl]">
          <Marquee speed={30}>
            {row2.map(({ icon: Icon, label }) => (
              <div key={label} className="flex items-center gap-2.5 px-5 py-2.5 rounded-xl bg-white border border-neutral-200/80 shadow-[0_1px_2px_rgba(0,0,0,0.03)] hover:border-neutral-300 transition-colors [direction:ltr]">
                <Icon className="h-4 w-4 text-neutral-400" />
                <span className="text-[13px] font-medium text-neutral-600">{label}</span>
              </div>
            ))}
          </Marquee>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// TESTIMONIALS
// ============================================================================
const testimonials = [
  { quote: "Sulci cut our chart abstraction pipeline from 6 weeks to under an hour — a 97% reduction. The concept mapping accuracy benchmarks at 94.2%, which rivals our senior informaticists.", author: "Dr. Sarah Chen", role: "Chief Medical Informatics Officer", org: "Pacific Health System", metric: "97% time reduction" },
  { quote: "We evaluated every CDM tool on the market. Sulci was the only one that handled assertion detection and negation correctly out of the box. That saved us $2.1M in year one.", author: "James Okafor", role: "VP of Data Engineering", org: "Meridian Clinical Analytics", metric: "$2.1M saved in Y1" },
  { quote: "The knowledge graph changed our pharmacovigilance entirely. Drug-condition signals that took our team days now surface in real-time. We caught 3x more safety signals last quarter.", author: "Dr. Lisa Patel", role: "Head of Drug Safety", org: "Vertex Therapeutics", metric: "3x safety signals" },
];

function TestimonialsSection() {
  return (
    <section className="py-20 md:py-28 px-6 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-neutral-50/40 to-white pointer-events-none" />
      <DotGrid className="opacity-15" />
      <div className="relative max-w-[1200px] mx-auto">
        <div className="text-center mb-14">
          <SectionBadge icon={Quote} label="What Teams Say" />
          <h2 className="text-[2rem] md:text-[2.75rem] font-medium tracking-[-0.035em] text-neutral-900 leading-[1.1]">Trusted by <span className="bg-gradient-to-r from-indigo-600 to-violet-500 bg-clip-text text-transparent">clinical data teams</span></h2>
        </div>
        <div className="grid md:grid-cols-3 gap-4">
          {testimonials.map((t, i) => (
            <motion.div key={t.author} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, delay: i * 0.08, ease: EASE }}>
              <div className="h-full rounded-2xl border border-neutral-200/80 bg-gradient-to-b from-white to-neutral-50/30 p-6 transition-all duration-300 hover:border-neutral-300/90 hover:shadow-[0_8px_40px_rgba(0,0,0,0.06)] hover:-translate-y-0.5">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex gap-0.5">{Array.from({ length: 5 }).map((_, j) => <Star key={j} className="h-3.5 w-3.5 text-amber-400 fill-amber-400" />)}</div>
                  {"metric" in t && <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 border border-emerald-100">{t.metric}</span>}
                </div>
                <p className="text-[14px] text-neutral-600 leading-[1.75] mb-6">&ldquo;{t.quote}&rdquo;</p>
                <div className="pt-4 border-t border-neutral-100 flex items-center gap-3">
                  <div className="h-9 w-9 rounded-full bg-gradient-to-br from-indigo-100 to-violet-100 flex items-center justify-center">
                    <span className="text-[11px] font-bold text-indigo-600">{t.author.split(" ").map(n => n[0]).join("")}</span>
                  </div>
                  <div>
                    <p className="text-[13px] font-semibold text-neutral-900">{t.author}</p>
                    <p className="text-[11.5px] text-neutral-400">{t.role} &middot; {t.org}</p>
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
    <section className="py-20 md:py-28 px-6 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-white via-neutral-50/20 to-white pointer-events-none" />
      <DotGrid className="opacity-10" />
      <div className="relative max-w-[1200px] mx-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, ease: EASE }} className="text-center mb-14">
          <SectionBadge icon={HeartPulse} label="Founder" />
          <h2 className="text-[2rem] md:text-[2.75rem] font-medium tracking-[-0.035em] text-neutral-900 leading-[1.1]">Built by a physician <span className="bg-gradient-to-r from-indigo-600 to-violet-500 bg-clip-text text-transparent">who ships.</span></h2>
        </motion.div>
        <div className="grid md:grid-cols-2 gap-10 md:gap-16 items-center">
          {/* Photos */}
          <motion.div initial={{ opacity: 0, x: -30 }} whileInView={{ opacity: 1, x: 0 }} viewport={VIEWPORT} transition={{ duration: 0.6, ease: EASE }} className="relative">
            <div className="absolute -inset-4 rounded-3xl pointer-events-none" style={{ background: "radial-gradient(ellipse 80% 60% at 30% 40%, rgba(99,102,241,0.08) 0%, transparent 70%)", filter: "blur(30px)" }} />
            <div className="relative rounded-2xl overflow-hidden shadow-[0_20px_60px_rgba(0,0,0,0.12)] border border-neutral-200/60">
              <img src="/alex-er.jpg" alt="Alex Stinard, M.D. in the emergency department" className="w-full h-auto object-cover" />
            </div>
            <div className="absolute -bottom-6 -right-4 md:-right-8 w-[140px] md:w-[160px] rounded-xl overflow-hidden shadow-[0_12px_40px_rgba(0,0,0,0.15)] border-[3px] border-white ring-1 ring-neutral-200/40">
              <img src="/alex-headshot.jpg" alt="Alex Stinard, M.D. headshot" className="w-full h-auto object-cover" />
            </div>
          </motion.div>

          {/* Bio */}
          <motion.div initial={{ opacity: 0, x: 30 }} whileInView={{ opacity: 1, x: 0 }} viewport={VIEWPORT} transition={{ duration: 0.6, delay: 0.1, ease: EASE }}>
            <h3 className="text-[1.5rem] md:text-[1.75rem] font-medium tracking-[-0.02em] text-neutral-900 mb-1">Alex Stinard, M.D.</h3>
            <p className="text-[13px] font-medium text-indigo-600 mb-5">Founder &amp; CEO</p>

            {/* Pull quote */}
            <div className="relative pl-4 border-l-2 border-indigo-200 mb-6">
              <p className="text-[15px] text-neutral-700 leading-[1.7] italic">&ldquo;Unstructured notes are a smooth brain. I&apos;ve spent 20 years watching clinical signal get lost in free text. Sulci adds the folds.&rdquo;</p>
            </div>

            <div className="space-y-3 text-[14px] text-neutral-600 leading-[1.75]">
              <p>Emergency physician executive and clinical AI architect. At Commure, designs and governs agentic ambient scribing at national scale — multi-agent orchestration with knowledge-graph memory, ontology-aware prompting, and deterministic EHR tool use.</p>
              <p>Enterprise SME for clinical documentation at HCA Healthcare. Led the Meditech Expanse rollout affecting millions of ED visits. Vice Chair of the Board at Lake Monroe Hospital. Assistant Professor of Emergency Medicine at UCF.</p>
            </div>

            {/* Career timeline */}
            <div className="mt-6 space-y-2">
              {career.map((c, i) => (
                <motion.div key={c.org} initial={{ opacity: 0, x: 12 }} whileInView={{ opacity: 1, x: 0 }} viewport={VIEWPORT} transition={{ duration: 0.3, delay: 0.2 + i * 0.06, ease: EASE }} className="flex items-center gap-3 group">
                  <div className="h-2 w-2 rounded-full bg-indigo-400 flex-shrink-0 group-hover:scale-125 transition-transform" />
                  <div className="flex items-baseline gap-2 min-w-0">
                    <span className="text-[13px] font-semibold text-neutral-900 flex-shrink-0">{c.org}</span>
                    <span className="text-[12px] text-neutral-400 truncate">{c.role}</span>
                  </div>
                </motion.div>
              ))}
            </div>

            {/* Expertise tags */}
            <div className="mt-6 flex flex-wrap gap-2">
              {["Multi-Agent Systems", "Knowledge Graphs", "Ontology Design", "FHIR/HL7", "Safety & Red-Teaming", "CDI/DRG"].map((tag) => (
                <span key={tag} className="px-2.5 py-1 text-[11px] font-medium rounded-lg bg-indigo-50/80 text-indigo-600/80 border border-indigo-100/60">{tag}</span>
              ))}
            </div>

            {/* Social links */}
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
// CTA
// ============================================================================
function CTASection() {
  return (
    <section className="py-20 md:py-28 px-6">
      <div className="max-w-[1200px] mx-auto">
        <div className="relative rounded-[24px] overflow-hidden">
          <div className="absolute inset-0 rounded-[24px] bg-gradient-to-r from-indigo-400/60 via-violet-400/60 to-purple-400/60" style={{ backgroundSize: "200% 200%", animation: "shimmer 4s ease-in-out infinite" }} />
          <div className="absolute inset-[1.5px] bg-gradient-to-b from-white via-white to-indigo-50/30 rounded-[22.5px]" />
          {/* Animated mesh gradient orbs */}
          <div className="absolute top-0 left-1/4 w-[300px] h-[300px] rounded-full bg-indigo-200/20 blur-[80px] animate-pulse pointer-events-none" style={{ animationDuration: "6s" }} />
          <div className="absolute bottom-0 right-1/4 w-[250px] h-[250px] rounded-full bg-violet-200/20 blur-[80px] animate-pulse pointer-events-none" style={{ animationDuration: "4s", animationDelay: "2s" }} />
          <div className="relative p-10 md:p-16 text-center">
            <GradientOrb className="top-[-100px] left-1/2 -translate-x-1/2" color="rgba(99,102,241,0.05)" size={500} />
            <div className="relative">
              <h2 className="text-[2rem] md:text-[2.75rem] font-medium tracking-[-0.035em] text-neutral-900 leading-[1.1]" style={{ textWrap: "balance" }}>Ready to turn clinical notes into knowledge?</h2>
              <p className="mt-4 text-neutral-500 max-w-md mx-auto text-[15px] leading-relaxed" style={{ textWrap: "balance" }}>Stop leaving clinical signal trapped in free text. See how Sulci can transform your data pipeline in a 30-minute walkthrough.</p>
              <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
                <Link href="/dashboard">
                  <Button className="group bg-neutral-900 text-white hover:bg-neutral-800 rounded-xl h-11 px-7 text-[14px] font-medium shadow-[0_1px_2px_rgba(0,0,0,0.1),0_4px_12px_rgba(0,0,0,0.06)] hover:shadow-[0_1px_2px_rgba(0,0,0,0.12),0_8px_24px_rgba(0,0,0,0.1)] transition-all">
                    Request a Demo <ArrowRight className="ml-1.5 h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform" />
                  </Button>
                </Link>
                <Link href="/login">
                  <Button variant="outline" className="rounded-xl h-11 px-7 text-[14px] font-medium text-neutral-600 border-neutral-200 bg-white/80 hover:bg-white hover:border-neutral-300 transition-all">Explore the API</Button>
                </Link>
              </div>
              <p className="mt-4 text-[12px] text-neutral-400">HIPAA compliant. SOC 2 Type II. BAA available.</p>
            </div>
          </div>
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
    <section className="py-20 md:py-28 px-6 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-neutral-50/30 to-white pointer-events-none" />
      <div className="relative max-w-[1200px] mx-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, ease: EASE }} className="text-center mb-14">
          <SectionBadge icon={Zap} label="Pricing" />
          <h2 className="text-[2rem] md:text-[2.75rem] font-medium tracking-[-0.035em] text-neutral-900 leading-[1.1]">Simple, <span className="bg-gradient-to-r from-indigo-600 to-violet-500 bg-clip-text text-transparent">predictable</span> pricing</h2>
          <p className="mt-4 text-neutral-500 max-w-lg mx-auto text-[15.5px] leading-relaxed" style={{ textWrap: "balance" }}>
            Start free. Scale when you&apos;re ready. No surprises.
          </p>
        </motion.div>
        <div className="grid md:grid-cols-3 gap-4 max-w-[960px] mx-auto">
          {plans.map((plan, i) => (
            <motion.div key={plan.name} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEWPORT} transition={{ duration: 0.5, delay: i * 0.08, ease: EASE }}>
              <div className={`relative h-full rounded-2xl border p-6 transition-all duration-300 hover:-translate-y-0.5 ${
                plan.highlight
                  ? "border-indigo-200 bg-gradient-to-b from-indigo-50/60 to-white shadow-[0_8px_40px_rgba(99,102,241,0.1)] hover:shadow-[0_12px_48px_rgba(99,102,241,0.15)]"
                  : "border-neutral-200/80 bg-gradient-to-b from-white to-neutral-50/30 hover:border-neutral-300 hover:shadow-[0_8px_40px_rgba(0,0,0,0.06)]"
              }`}>
                {plan.highlight && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="px-3 py-1 rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 text-white text-[11px] font-semibold shadow-sm">Most Popular</span>
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
                      <CheckCircle2 className={`h-3.5 w-3.5 mt-0.5 flex-shrink-0 ${plan.highlight ? "text-indigo-500" : "text-neutral-300"}`} />
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
// FOOTER
// ============================================================================
function FooterSection() {
  const links = {
    Product: ["NLP Engine", "Ontology Mapping", "Knowledge Graph", "FHIR Import/Export", "Clinical Trials", "API Reference"],
    Resources: ["Documentation", "Quickstart Guide", "API Status", "Changelog", "Blog"],
    Company: ["About", "Careers", "Security", "Privacy Policy", "Terms of Service"],
  };
  return (
    <footer className="border-t border-neutral-200/60">
      <div className="max-w-[1200px] mx-auto px-6 py-14 md:py-16">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-8">
          <div className="col-span-2 md:col-span-3">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="h-7 w-7 rounded-lg bg-neutral-900 flex items-center justify-center"><SulciLogo className="h-4 w-4 text-white" variant="filled" /></div>
              <span className="font-semibold text-[15px] tracking-[-0.02em] text-neutral-900">Sulci AI</span>
            </div>
            <p className="text-[13px] text-neutral-500 leading-relaxed max-w-[320px] mb-5">Clinical ontology normalization — NLP extraction, UMLS and OMOP mapping, and knowledge graph infrastructure for modern health systems.</p>
            <div className="flex items-center gap-2 mb-5">
              {["X", "GitHub", "LinkedIn"].map((s) => (
                <span key={s} className="h-8 px-3 flex items-center justify-center text-[11px] font-medium rounded-lg text-neutral-400 border border-neutral-200/80 hover:text-neutral-600 hover:border-neutral-300 hover:shadow-[0_2px_8px_rgba(0,0,0,0.04)] transition-all cursor-pointer">{s}</span>
              ))}
            </div>
            {/* Newsletter */}
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
            {["HIPAA", "SOC 2", "21 CFR Part 11", "UMLS", "FHIR R4", "OMOP CDM"].map((b) => (
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
function GradientDivider() {
  return <div className="relative max-w-5xl mx-auto px-6"><div className="h-px bg-gradient-to-r from-transparent via-neutral-200/80 to-transparent" /></div>;
}

function TrustBar() {
  const orgs = [
    { name: "HCA Healthcare", detail: "185+ hospitals" },
    { name: "Commure", detail: "AI infrastructure" },
    { name: "UCF Health", detail: "Academic medicine" },
    { name: "Augmedix + Google", detail: "Ambient AI" },
  ];
  return (
    <div className="py-10 md:py-12 border-y border-neutral-100/60">
      <p className="text-[11px] font-semibold tracking-[0.12em] uppercase text-neutral-400 mb-6 text-center">Trusted by teams at</p>
      <div className="flex items-center justify-center gap-6 md:gap-10 flex-wrap px-6">
        {orgs.map((org) => (
          <div key={org.name} className="flex flex-col items-center gap-0.5 group cursor-default">
            <span className="text-[14px] font-semibold tracking-[-0.01em] text-neutral-400 group-hover:text-neutral-700 transition-colors">{org.name}</span>
            <span className="text-[10px] text-neutral-300 group-hover:text-neutral-400 transition-colors">{org.detail}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <div className="min-h-screen bg-white selection:bg-indigo-100 overflow-x-hidden scroll-smooth">
      <ScrollProgress />
      <BackToTop />
      <Nav />
      <HeroSection />
      <TrustBar />
      <GradientDivider />
      <StatsSection />
      <GradientDivider />
      <ProblemSection />
      <GradientDivider />
      <HowItWorks />
      <GradientDivider />
      <CoreEngines />
      <KnowledgeGraphViz />
      <GradientDivider />
      <DataTransformation />
      <APIShowcase />
      <PlatformBento />
      <GradientDivider />
      <StandardsSection />
      <IntegrationsSection />
      <WhyNowSection />
      <TestimonialsSection />
      <ComplianceSection />
      <GradientDivider />
      <FounderSection />
      <CTASection />
      <GradientDivider />
      <PricingSection />
      <FooterSection />
    </div>
  );
}
