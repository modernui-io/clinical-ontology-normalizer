"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ArrowRight,
  Activity,
  Shield,
  Zap,
  Users,
  Database,
  GitBranch,
  Target,
  CheckCircle2,
  BarChart3,
  Globe,
  Lock,
  FileText,
  Search,
  FlaskConical,
  Workflow,
  TrendingUp,
  HeartPulse,
  Eye,
  ShieldCheck,
  Sparkles,
  Microscope,
  Pill,
  Scan,
  BrainCircuit,
  Network,
} from "lucide-react";

// Regeneron brand colors
const COLORS = {
  regenBlue: "#045AA9",
  regenRed: "#D50057",
  regenDark: "#002B5C",
  regenLight: "#E8F4FD",
};

// Floating molecule decoration (CSS-only)
function MoleculeDecoration({ className = "" }: { className?: string }) {
  return (
    <div className={`absolute pointer-events-none ${className}`}>
      {/* Central node */}
      <div className="relative">
        <div className="w-4 h-4 rounded-full bg-white/20 animate-pulse" />
        {/* Bond lines */}
        <div className="absolute top-1/2 left-full w-12 h-px bg-gradient-to-r from-white/20 to-transparent" />
        <div className="absolute top-full left-1/2 w-px h-12 bg-gradient-to-b from-white/20 to-transparent" />
        <div className="absolute top-1/2 right-full w-12 h-px bg-gradient-to-l from-white/20 to-transparent" />
        {/* Satellite nodes */}
        <div className="absolute -top-6 -left-6 w-2 h-2 rounded-full bg-white/10" />
        <div className="absolute -bottom-8 left-8 w-3 h-3 rounded-full bg-white/15 animate-pulse [animation-delay:1s]" />
        <div className="absolute top-4 -right-10 w-2 h-2 rounded-full bg-white/10 animate-pulse [animation-delay:0.5s]" />
      </div>
    </div>
  );
}

// Antibody Y-shape decoration
function AntibodyDecoration({ className = "" }: { className?: string }) {
  return (
    <svg className={`absolute pointer-events-none opacity-[0.07] ${className}`} width="120" height="140" viewBox="0 0 120 140" fill="none">
      {/* Y-shaped antibody */}
      <path d="M60 140 L60 80 L20 30 M60 80 L100 30" stroke="currentColor" strokeWidth="6" strokeLinecap="round" fill="none" />
      {/* Binding sites */}
      <circle cx="20" cy="25" r="12" stroke="currentColor" strokeWidth="4" fill="none" />
      <circle cx="100" cy="25" r="12" stroke="currentColor" strokeWidth="4" fill="none" />
      {/* Fc region */}
      <ellipse cx="60" cy="130" rx="14" ry="10" stroke="currentColor" strokeWidth="4" fill="none" />
    </svg>
  );
}

// Stat counter for hero
function HeroStat({ value, label, accent = false }: { value: string; label: string; accent?: boolean }) {
  return (
    <div className="text-center">
      <div className={`text-3xl md:text-4xl font-bold ${accent ? "text-[#D50057]" : "text-white"}`}>
        {value}
      </div>
      <div className="text-sm text-blue-200/80 mt-1 font-medium">{label}</div>
    </div>
  );
}

// Therapeutic area card
function TherapeuticCard({
  icon: Icon,
  area,
  drug,
  indication,
  phase,
  nct,
  stat,
  statLabel,
  gradient,
  accentColor,
  href,
}: {
  icon: React.ElementType;
  area: string;
  drug: string;
  indication: string;
  phase: string;
  nct: string;
  stat: string;
  statLabel: string;
  gradient: string;
  accentColor: string;
  href: string;
}) {
  return (
    <Link href={href} className="group block">
      <div className={`relative overflow-hidden rounded-2xl ${gradient} p-[1px] transition-all duration-500 hover:shadow-xl hover:shadow-black/10 hover:-translate-y-1`}>
        <div className="relative rounded-[15px] bg-white dark:bg-gray-950 p-6 h-full">
          {/* Accent stripe */}
          <div className={`absolute top-0 left-0 right-0 h-1 ${accentColor}`} />

          {/* Icon + Area */}
          <div className="flex items-start justify-between mb-4">
            <div className={`h-12 w-12 rounded-xl ${gradient} flex items-center justify-center text-white shadow-lg`}>
              <Icon className="h-6 w-6" />
            </div>
            <Badge variant="outline" className="text-xs font-mono">
              {phase}
            </Badge>
          </div>

          {/* Content */}
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {area}
            </p>
            <h3 className="text-xl font-bold group-hover:text-[#045AA9] transition-colors">
              {drug}
            </h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {indication}
            </p>
          </div>

          {/* Stats */}
          <div className="mt-5 pt-4 border-t flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-[#045AA9]">{stat}</div>
              <div className="text-xs text-muted-foreground">{statLabel}</div>
            </div>
            <div className="text-xs font-mono text-muted-foreground/60">
              {nct}
            </div>
          </div>

          {/* Hover arrow */}
          <div className="absolute bottom-6 right-6 opacity-0 group-hover:opacity-100 transition-all duration-300 translate-x-2 group-hover:translate-x-0">
            <ArrowRight className="h-5 w-5 text-[#045AA9]" />
          </div>
        </div>
      </div>
    </Link>
  );
}

// Pipeline step
function PipelineStep({
  label,
  count,
  percentage,
  color,
}: {
  label: string;
  count: number;
  percentage: number;
  color: string;
}) {
  return (
    <div className="flex-1 min-w-[100px]">
      <div className="text-center mb-3">
        <div className="text-2xl font-bold">{count.toLocaleString()}</div>
        <div className="text-xs text-muted-foreground font-medium">{label}</div>
      </div>
      <div className="h-2 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
        <div
          className={`h-full rounded-full ${color} transition-all duration-1000`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <div className="min-h-screen">
      {/* ====== HERO ====== */}
      <section className="relative overflow-hidden bg-gradient-to-br from-[#002B5C] via-[#045AA9] to-[#002B5C] text-white">
        {/* Background decorations */}
        <div className="absolute inset-0">
          {/* Subtle grid */}
          <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:48px_48px]" />
          {/* Gradient orbs */}
          <div className="absolute -top-32 -right-32 w-[500px] h-[500px] bg-[#D50057]/10 rounded-full blur-[120px]" />
          <div className="absolute -bottom-32 -left-32 w-[400px] h-[400px] bg-blue-400/10 rounded-full blur-[100px]" />
          {/* Floating molecules */}
          <MoleculeDecoration className="top-20 right-[15%]" />
          <MoleculeDecoration className="bottom-32 left-[10%]" />
          <MoleculeDecoration className="top-40 left-[25%]" />
          {/* Antibody decorations */}
          <AntibodyDecoration className="top-12 right-[8%] text-white w-[80px] h-[100px]" />
          <AntibodyDecoration className="bottom-16 left-[5%] text-white w-[60px] h-[80px] rotate-12" />
        </div>

        <div className="relative max-w-6xl mx-auto px-6 py-16 md:py-24">
          <div className="text-center max-w-4xl mx-auto">
            {/* Regeneron badge */}
            <div className="inline-flex items-center gap-3 mb-8">
              <Badge className="bg-white/10 text-white border-white/20 backdrop-blur-sm text-xs font-medium px-4 py-1.5 hover:bg-white/15">
                <Microscope className="h-3.5 w-3.5 mr-2" />
                Regeneron Clinical Trial Platform
              </Badge>
            </div>

            {/* Main headline */}
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight leading-[1.1]">
              Accelerating
              <span className="block mt-2 bg-gradient-to-r from-white via-blue-200 to-[#D50057] bg-clip-text text-transparent">
                Patient Recruitment
              </span>
              <span className="block text-2xl md:text-3xl font-medium text-blue-200/80 mt-4">
                for Regeneron Therapeutics
              </span>
            </h1>

            <p className="mt-6 text-lg text-blue-100/70 max-w-2xl mx-auto leading-relaxed">
              Ingest patient data from Health Information Exchanges via Metriport,
              standardize to OMOP, and automatically screen patients against
              trial eligibility criteria — in real time.
            </p>

            {/* CTAs */}
            <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href="/trials">
                <Button
                  size="lg"
                  className="bg-[#D50057] hover:bg-[#B8004B] text-white font-semibold px-8 shadow-lg shadow-[#D50057]/20 border-0"
                >
                  View Active Trials
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
              <Link href="/dashboard">
                <Button
                  size="lg"
                  className="bg-white/10 backdrop-blur-sm border border-white/20 text-white hover:bg-white/20 px-8"
                >
                  Platform Dashboard
                </Button>
              </Link>
            </div>
          </div>

          {/* Stats bar */}
          <div className="mt-16 max-w-4xl mx-auto">
            <div className="rounded-2xl bg-white/5 backdrop-blur-sm border border-white/10 p-8">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
                <HeroStat value="3" label="Active Regeneron Trials" />
                <HeroStat value="80M+" label="EYLEA Injections Worldwide" accent />
                <HeroStat value="1.4M+" label="DUPIXENT Patients Globally" />
                <HeroStat value="68%" label="LIBTAYO Recurrence Reduction" accent />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ====== THERAPEUTIC AREAS ====== */}
      <section className="py-16 px-6 bg-gradient-to-b from-slate-50 to-white dark:from-gray-950 dark:to-gray-900">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <Badge className="bg-[#045AA9]/10 text-[#045AA9] border-[#045AA9]/20 mb-4">
              Active Trials
            </Badge>
            <h2 className="text-2xl md:text-3xl font-bold">
              Regeneron Therapeutic Pipeline
            </h2>
            <p className="text-muted-foreground mt-2 max-w-xl mx-auto">
              Automated eligibility screening across ophthalmology, oncology, and immunology
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <TherapeuticCard
              icon={Eye}
              area="Ophthalmology"
              drug="EYLEA HD"
              indication="Phase III for Diabetic Macular Edema in adults with Type 2 Diabetes. High-dose aflibercept with extended dosing intervals."
              phase="Phase III"
              nct="NCT04429503"
              stat="900"
              statLabel="Target enrollment"
              gradient="bg-gradient-to-br from-amber-400 to-orange-500"
              accentColor="bg-amber-500"
              href="/trials"
            />
            <TherapeuticCard
              icon={ShieldCheck}
              area="Oncology"
              drug="LIBTAYO"
              indication="Phase II for advanced Cutaneous Squamous Cell Carcinoma. Cemiplimab anti-PD-1 immunotherapy for patients ineligible for surgery."
              phase="Phase II"
              nct="NCT02760498"
              stat="200"
              statLabel="Target enrollment"
              gradient="bg-gradient-to-br from-[#D50057] to-rose-600"
              accentColor="bg-[#D50057]"
              href="/trials"
            />
            <TherapeuticCard
              icon={Sparkles}
              area="Immunology"
              drug="DUPIXENT"
              indication="Phase III LIBERTY AD CHRONOS for moderate-to-severe Atopic Dermatitis. Dupilumab long-term efficacy with topical corticosteroids."
              phase="Phase III"
              nct="NCT02395133"
              stat="600"
              statLabel="Target enrollment"
              gradient="bg-gradient-to-br from-teal-400 to-emerald-500"
              accentColor="bg-teal-500"
              href="/trials"
            />
          </div>
        </div>
      </section>

      {/* ====== LIVE ENROLLMENT PIPELINE ====== */}
      <section className="py-16 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-2xl md:text-3xl font-bold">
              Live Enrollment Pipeline
            </h2>
            <p className="text-muted-foreground mt-2">
              Real-time patient flow across all Regeneron trials
            </p>
          </div>

          {/* Pipeline visualization */}
          <div className="rounded-2xl border bg-white dark:bg-gray-950 p-8 shadow-sm">
            <div className="flex items-stretch gap-3">
              <PipelineStep label="Screened" count={415} percentage={100} color="bg-slate-400" />
              <div className="flex items-center">
                <ArrowRight className="h-4 w-4 text-muted-foreground/30" />
              </div>
              <PipelineStep label="Eligible" count={287} percentage={69} color="bg-[#045AA9]" />
              <div className="flex items-center">
                <ArrowRight className="h-4 w-4 text-muted-foreground/30" />
              </div>
              <PipelineStep label="Consented" count={198} percentage={48} color="bg-teal-500" />
              <div className="flex items-center">
                <ArrowRight className="h-4 w-4 text-muted-foreground/30" />
              </div>
              <PipelineStep label="Enrolled" count={133} percentage={32} color="bg-emerald-500" />
              <div className="flex items-center">
                <ArrowRight className="h-4 w-4 text-muted-foreground/30" />
              </div>
              <PipelineStep label="Active" count={89} percentage={21} color="bg-green-600" />
            </div>

            {/* Conversion metrics */}
            <div className="mt-8 pt-6 border-t grid grid-cols-3 gap-4">
              <div className="text-center rounded-xl bg-slate-50 dark:bg-gray-900 p-4">
                <div className="text-lg font-bold text-[#045AA9]">69.2%</div>
                <div className="text-xs text-muted-foreground mt-1">Screen-to-Eligible Rate</div>
              </div>
              <div className="text-center rounded-xl bg-slate-50 dark:bg-gray-900 p-4">
                <div className="text-lg font-bold text-teal-600">69.0%</div>
                <div className="text-xs text-muted-foreground mt-1">Eligible-to-Consent Rate</div>
              </div>
              <div className="text-center rounded-xl bg-slate-50 dark:bg-gray-900 p-4">
                <div className="text-lg font-bold text-emerald-600">67.2%</div>
                <div className="text-xs text-muted-foreground mt-1">Consent-to-Enrolled Rate</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ====== HOW IT WORKS ====== */}
      <section className="py-16 px-6 bg-gradient-to-b from-white to-slate-50 dark:from-gray-900 dark:to-gray-950">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-2xl md:text-3xl font-bold">How It Works</h2>
            <p className="text-muted-foreground mt-2">
              From HIE data to trial enrollment in three steps
            </p>
          </div>

          <div className="relative">
            {/* Connecting line */}
            <div className="hidden md:block absolute top-[72px] left-[16%] right-[16%] h-px bg-gradient-to-r from-[#045AA9]/20 via-[#045AA9]/40 to-[#045AA9]/20" />

            <div className="grid md:grid-cols-3 gap-8">
              {[
                {
                  step: "01",
                  icon: Network,
                  title: "Ingest from HIE",
                  description:
                    "Patient records flow from Carequality, CommonWell, and eHealth Exchange via Metriport. FHIR R4 Bundles are ingested automatically — conditions, medications, labs, and procedures.",
                  color: "from-[#045AA9] to-blue-600",
                },
                {
                  step: "02",
                  icon: BrainCircuit,
                  title: "Normalize to OMOP",
                  description:
                    "All clinical data is mapped to OMOP concepts — ICD-10, LOINC, RxNorm, SNOMED CT. NLP extracts facts from unstructured notes. A patient knowledge graph captures every relationship.",
                  color: "from-teal-500 to-emerald-500",
                },
                {
                  step: "03",
                  icon: Target,
                  title: "Screen & Match",
                  description:
                    "Patients are evaluated against Regeneron trial criteria instantly. Structured inclusion/exclusion rules check conditions, labs, and medications. Candidates are ranked and surfaced to coordinators.",
                  color: "from-[#D50057] to-rose-500",
                },
              ].map(({ step, icon: Icon, title, description, color }) => (
                <div key={step} className="relative text-center">
                  {/* Step number circle */}
                  <div className="relative inline-flex mb-6">
                    <div className={`h-16 w-16 rounded-2xl bg-gradient-to-br ${color} flex items-center justify-center text-white shadow-lg mx-auto`}>
                      <Icon className="h-7 w-7" />
                    </div>
                    <span className="absolute -top-2 -right-2 h-7 w-7 rounded-full bg-white dark:bg-gray-950 border-2 border-current flex items-center justify-center text-xs font-bold text-[#045AA9] shadow-sm">
                      {step}
                    </span>
                  </div>
                  <h3 className="font-bold text-lg mb-3">{title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed max-w-xs mx-auto">
                    {description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ====== PLATFORM CAPABILITIES ====== */}
      <section className="py-16 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-2xl md:text-3xl font-bold">Platform Capabilities</h2>
            <p className="text-muted-foreground mt-2">
              End-to-end clinical data infrastructure powering Regeneron trial recruitment
            </p>
          </div>

          {/* Bento grid */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Large card - FHIR */}
            <div className="col-span-2 row-span-2 rounded-2xl bg-gradient-to-br from-[#045AA9] to-[#002B5C] p-6 text-white relative overflow-hidden group hover:shadow-xl transition-shadow">
              <AntibodyDecoration className="bottom-4 right-4 text-white w-[100px] h-[120px] opacity-[0.1] group-hover:opacity-[0.15] transition-opacity" />
              <div className="relative">
                <div className="h-12 w-12 rounded-xl bg-white/10 flex items-center justify-center mb-4">
                  <HeartPulse className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold mb-2">FHIR R4 Bundle Import</h3>
                <p className="text-sm text-blue-100/70 leading-relaxed mb-6">
                  Ingest complete patient records as FHIR Bundles. Conditions, medications,
                  observations, procedures, and allergies are parsed and mapped to OMOP automatically.
                </p>
                <div className="grid grid-cols-2 gap-3">
                  {["Conditions", "Medications", "Lab Results", "Procedures"].map((item) => (
                    <div key={item} className="flex items-center gap-2 text-xs text-blue-200/80">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      {item}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Small cards */}
            <div className="rounded-2xl border bg-white dark:bg-gray-950 p-5 hover:shadow-md transition-shadow">
              <Globe className="h-8 w-8 text-teal-500 mb-3" />
              <h3 className="font-semibold text-sm mb-1">HIE Integration</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Carequality, CommonWell, eHealth Exchange via Metriport
              </p>
            </div>

            <div className="rounded-2xl border bg-white dark:bg-gray-950 p-5 hover:shadow-md transition-shadow">
              <Database className="h-8 w-8 text-[#045AA9] mb-3" />
              <h3 className="font-semibold text-sm mb-1">OMOP CDM</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Standardized concepts for cross-site analysis
              </p>
            </div>

            <div className="rounded-2xl border bg-white dark:bg-gray-950 p-5 hover:shadow-md transition-shadow">
              <GitBranch className="h-8 w-8 text-purple-500 mb-3" />
              <h3 className="font-semibold text-sm mb-1">Knowledge Graph</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Clinical relationships and temporal context
              </p>
            </div>

            <div className="rounded-2xl border bg-white dark:bg-gray-950 p-5 hover:shadow-md transition-shadow">
              <Zap className="h-8 w-8 text-amber-500 mb-3" />
              <h3 className="font-semibold text-sm mb-1">Real-time Screening</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Instant eligibility evaluation against trial criteria
              </p>
            </div>

            {/* Wide card */}
            <div className="col-span-2 rounded-2xl border bg-gradient-to-r from-slate-50 to-white dark:from-gray-900 dark:to-gray-950 p-5 hover:shadow-md transition-shadow">
              <div className="flex items-start gap-4">
                <BarChart3 className="h-8 w-8 text-emerald-500 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold text-sm mb-1">Enrollment Analytics & Reporting</h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Track screening-to-enrollment conversion by trial, site, and time period.
                    Monitor recruitment bottlenecks and optimize pipeline velocity.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ====== STANDARDS & COMPLIANCE ====== */}
      <section className="py-12 px-6 border-y bg-white dark:bg-gray-900">
        <div className="max-w-5xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12">
            {/* Standards */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">
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
                    className="px-3 py-1.5 text-xs font-mono rounded-lg bg-slate-100 dark:bg-slate-800 text-muted-foreground"
                  >
                    {standard}
                  </span>
                ))}
              </div>
            </div>

            {/* Compliance */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">
                Security & Compliance
              </p>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { icon: Shield, label: "HIPAA Compliant" },
                  { icon: Lock, label: "SOC 2 Type II" },
                  { icon: FileText, label: "21 CFR Part 11" },
                  { icon: Activity, label: "Full Audit Trail" },
                ].map(({ icon: Icon, label }) => (
                  <div key={label} className="flex items-center gap-2.5 text-sm">
                    <div className="h-8 w-8 rounded-lg bg-emerald-50 dark:bg-emerald-950/50 flex items-center justify-center flex-shrink-0">
                      <Icon className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <span className="text-muted-foreground font-medium">{label}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ====== CTA ====== */}
      <section className="py-20 px-6 bg-gradient-to-br from-[#002B5C] via-[#045AA9] to-[#002B5C] text-white relative overflow-hidden">
        {/* Background */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:48px_48px]" />
        <div className="absolute -top-24 right-0 w-[400px] h-[400px] bg-[#D50057]/10 rounded-full blur-[120px]" />
        <AntibodyDecoration className="top-8 left-[10%] text-white w-[100px] h-[120px]" />
        <AntibodyDecoration className="bottom-8 right-[8%] text-white w-[80px] h-[100px] -rotate-12" />

        <div className="relative max-w-3xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold leading-tight">
            Ready to Accelerate
            <span className="block bg-gradient-to-r from-white to-[#D50057] bg-clip-text text-transparent">
              Regeneron Trial Enrollment?
            </span>
          </h2>
          <p className="mt-4 text-blue-100/70 text-lg max-w-xl mx-auto">
            See how automated eligibility screening reduces time-to-enrollment
            and ensures no eligible patient is missed.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/trials">
              <Button
                size="lg"
                className="bg-[#D50057] hover:bg-[#B8004B] text-white font-semibold px-8 shadow-lg shadow-[#D50057]/20 border-0"
              >
                <FlaskConical className="mr-2 h-4 w-4" />
                Explore Trials
              </Button>
            </Link>
            <Link href="/dashboard">
              <Button
                size="lg"
                className="bg-white/10 backdrop-blur-sm border border-white/20 text-white hover:bg-white/20 px-8"
              >
                View Dashboard
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* ====== FOOTER ====== */}
      <footer className="py-8 px-6 border-t bg-white dark:bg-gray-900">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-[#045AA9] flex items-center justify-center">
              <Microscope className="h-4 w-4 text-white" />
            </div>
            <div>
              <span className="font-semibold text-sm">Clinical Ontology Normalizer</span>
              <span className="text-xs text-muted-foreground ml-2">for Regeneron</span>
            </div>
          </div>
          <div className="flex items-center gap-6 text-xs text-muted-foreground">
            <span>HIPAA</span>
            <span>SOC 2</span>
            <span>21 CFR Part 11</span>
            <span>FHIR R4</span>
          </div>
          <p className="text-xs text-muted-foreground">
            &copy; 2026 Clinical Ontology Platform
          </p>
        </div>
      </footer>
    </div>
  );
}
