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
} from "lucide-react";

// Animated counter component
function AnimatedStat({ value, label, suffix = "" }: { value: string; label: string; suffix?: string }) {
  return (
    <div className="text-center">
      <div className="text-3xl md:text-4xl font-bold text-white">
        {value}
        {suffix && <span className="text-blue-200">{suffix}</span>}
      </div>
      <div className="text-sm text-blue-200 mt-1">{label}</div>
    </div>
  );
}

// Feature card component
function FeatureCard({
  icon: Icon,
  title,
  description,
  accent = "blue",
}: {
  icon: React.ElementType;
  title: string;
  description: string;
  accent?: "blue" | "teal" | "emerald" | "purple";
}) {
  const accentColors = {
    blue: "from-blue-500/10 to-blue-600/5 border-blue-200/50 dark:border-blue-800/50",
    teal: "from-teal-500/10 to-teal-600/5 border-teal-200/50 dark:border-teal-800/50",
    emerald: "from-emerald-500/10 to-emerald-600/5 border-emerald-200/50 dark:border-emerald-800/50",
    purple: "from-purple-500/10 to-purple-600/5 border-purple-200/50 dark:border-purple-800/50",
  };
  const iconColors = {
    blue: "text-blue-600 dark:text-blue-400",
    teal: "text-teal-600 dark:text-teal-400",
    emerald: "text-emerald-600 dark:text-emerald-400",
    purple: "text-purple-600 dark:text-purple-400",
  };

  return (
    <Card className={`bg-gradient-to-br ${accentColors[accent]} border hover:shadow-lg transition-all duration-300 hover:-translate-y-0.5`}>
      <CardContent className="pt-6">
        <div className={`h-10 w-10 rounded-lg bg-white dark:bg-gray-900 shadow-sm flex items-center justify-center mb-4 ${iconColors[accent]}`}>
          <Icon className="h-5 w-5" />
        </div>
        <h3 className="font-semibold text-lg mb-2">{title}</h3>
        <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
      </CardContent>
    </Card>
  );
}

// Pipeline stage component
function PipelineStage({
  label,
  count,
  color,
  isLast = false,
}: {
  label: string;
  count: string;
  color: string;
  isLast?: boolean;
}) {
  return (
    <div className="flex items-center">
      <div className="flex flex-col items-center">
        <div className={`w-14 h-14 rounded-xl ${color} flex items-center justify-center text-white font-bold text-lg shadow-md`}>
          {count}
        </div>
        <span className="text-xs font-medium mt-2 text-muted-foreground">{label}</span>
      </div>
      {!isLast && (
        <div className="mx-2 md:mx-4">
          <ArrowRight className="h-5 w-5 text-muted-foreground/40" />
        </div>
      )}
    </div>
  );
}

export default function Home() {
  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 text-white">
        {/* Subtle grid pattern overlay */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:64px_64px]" />
        {/* Gradient orbs */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-teal-500/10 rounded-full blur-3xl" />

        <div className="relative max-w-6xl mx-auto px-6 py-16 md:py-24">
          <div className="text-center max-w-4xl mx-auto">
            <Badge className="bg-blue-500/20 text-blue-200 border-blue-400/30 mb-6 text-xs font-medium px-3 py-1">
              <FlaskConical className="h-3 w-3 mr-1.5" />
              Clinical Trial Recruitment Platform
            </Badge>
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight leading-tight">
              Accelerate Patient
              <span className="block bg-gradient-to-r from-blue-400 via-teal-300 to-emerald-400 bg-clip-text text-transparent">
                Enrollment
              </span>
            </h1>
            <p className="mt-6 text-lg md:text-xl text-blue-100/80 max-w-2xl mx-auto leading-relaxed">
              Ingest patient data from HIEs, standardize to OMOP, and automatically screen
              patients against trial eligibility criteria — in real time.
            </p>
            <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href="/trials">
                <Button size="lg" className="bg-white text-slate-900 hover:bg-blue-50 font-semibold px-8 shadow-lg shadow-white/10">
                  View Active Trials
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
              <Link href="/dashboard">
                <Button size="lg" className="bg-transparent border border-white/30 text-white hover:bg-white/10 px-8">
                  Platform Dashboard
                </Button>
              </Link>
            </div>
          </div>

          {/* Stats bar */}
          <div className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-8 max-w-3xl mx-auto">
            <AnimatedStat value="3" label="Active Trials" />
            <AnimatedStat value="1,700" label="Sites Connected" suffix="+" />
            <AnimatedStat value="133" label="Patients Enrolled" />
            <AnimatedStat value="98" label="Eligibility Accuracy" suffix="%" />
          </div>
        </div>
      </section>

      {/* Enrollment Pipeline Visualization */}
      <section className="py-16 px-6 bg-gradient-to-b from-slate-50 to-white dark:from-gray-950 dark:to-gray-900">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-2xl md:text-3xl font-bold">Enrollment Pipeline</h2>
            <p className="text-muted-foreground mt-2">
              Automated patient flow from screening to active participation
            </p>
          </div>

          {/* Pipeline */}
          <div className="flex items-center justify-center flex-wrap gap-y-6">
            <PipelineStage label="Screened" count="415" color="bg-slate-500" />
            <PipelineStage label="Eligible" count="287" color="bg-blue-500" />
            <PipelineStage label="Consented" count="198" color="bg-teal-500" />
            <PipelineStage label="Enrolled" count="133" color="bg-emerald-500" />
            <PipelineStage label="Active" count="89" color="bg-green-600" isLast />
          </div>

          {/* Pipeline description cards */}
          <div className="mt-12 grid md:grid-cols-3 gap-6">
            <div className="rounded-xl border bg-white/50 dark:bg-gray-900/50 p-5 backdrop-blur-sm">
              <div className="flex items-center gap-3 mb-3">
                <Search className="h-5 w-5 text-blue-500" />
                <h3 className="font-semibold">Automatic Screening</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                Every patient record is evaluated against structured inclusion and exclusion
                criteria mapped to ICD-10, LOINC, and RxNorm codes.
              </p>
            </div>
            <div className="rounded-xl border bg-white/50 dark:bg-gray-900/50 p-5 backdrop-blur-sm">
              <div className="flex items-center gap-3 mb-3">
                <Target className="h-5 w-5 text-teal-500" />
                <h3 className="font-semibold">Match Scoring</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                Candidates are ranked by a composite eligibility score based on criteria
                met, clinical data quality, and temporal relevance.
              </p>
            </div>
            <div className="rounded-xl border bg-white/50 dark:bg-gray-900/50 p-5 backdrop-blur-sm">
              <div className="flex items-center gap-3 mb-3">
                <TrendingUp className="h-5 w-5 text-emerald-500" />
                <h3 className="font-semibold">Site Coordination</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                Eligible patients are flagged for site coordinators with full clinical
                context and eligibility documentation.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-16 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-2xl md:text-3xl font-bold">How It Works</h2>
            <p className="text-muted-foreground mt-2">
              Three steps from data ingestion to trial enrollment
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                step: "01",
                icon: Database,
                title: "Connect Patient Data",
                description:
                  "Ingest FHIR R4 Bundles directly or receive consolidated records from Health Information Exchanges via Metriport's Medical API.",
                color: "text-blue-600",
                bg: "bg-blue-50 dark:bg-blue-950/50",
              },
              {
                step: "02",
                icon: Workflow,
                title: "Standardize & Map",
                description:
                  "Conditions, medications, and labs are normalized to OMOP concepts. NLP extracts clinical facts from unstructured notes. A patient knowledge graph is built automatically.",
                color: "text-teal-600",
                bg: "bg-teal-50 dark:bg-teal-950/50",
              },
              {
                step: "03",
                icon: Users,
                title: "Screen & Enroll",
                description:
                  "Patients are automatically evaluated against trial eligibility criteria. Candidates are ranked by match score and surfaced to site coordinators for enrollment.",
                color: "text-emerald-600",
                bg: "bg-emerald-50 dark:bg-emerald-950/50",
              },
            ].map(({ step, icon: Icon, title, description, color, bg }) => (
              <div key={step} className={`rounded-2xl ${bg} p-6 relative`}>
                <span className={`text-5xl font-bold ${color} opacity-20 absolute top-4 right-4`}>
                  {step}
                </span>
                <div className={`h-12 w-12 rounded-xl bg-white dark:bg-gray-900 shadow-sm flex items-center justify-center mb-4 ${color}`}>
                  <Icon className="h-6 w-6" />
                </div>
                <h3 className="font-semibold text-lg mb-2">{title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Feature Bento Grid */}
      <section className="py-16 px-6 bg-gradient-to-b from-white to-slate-50 dark:from-gray-900 dark:to-gray-950">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-2xl md:text-3xl font-bold">Platform Capabilities</h2>
            <p className="text-muted-foreground mt-2">
              End-to-end clinical data infrastructure for trial recruitment
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            <FeatureCard
              icon={HeartPulse}
              title="FHIR R4 Bundle Import"
              description="Ingest complete patient records as FHIR Bundles. Conditions, medications, observations, procedures, and allergies are parsed and mapped automatically."
              accent="blue"
            />
            <FeatureCard
              icon={Globe}
              title="HIE Integration"
              description="Connect to Carequality, CommonWell, and eHealth Exchange via Metriport. Consolidated patient records flow directly into the screening pipeline."
              accent="teal"
            />
            <FeatureCard
              icon={Database}
              title="OMOP Standardization"
              description="All clinical data is normalized to OMOP Common Data Model concepts — enabling cross-site analysis and standardized eligibility evaluation."
              accent="emerald"
            />
            <FeatureCard
              icon={GitBranch}
              title="Knowledge Graph"
              description="Patient data is structured as a clinical knowledge graph — capturing relationships between conditions, medications, lab values, and temporal context."
              accent="purple"
            />
            <FeatureCard
              icon={Zap}
              title="Real-time Eligibility"
              description="Structured trial criteria are evaluated against patient data instantly. Inclusion and exclusion criteria use ICD-10, LOINC, RxNorm, and SNOMED CT codes."
              accent="blue"
            />
            <FeatureCard
              icon={BarChart3}
              title="Enrollment Analytics"
              description="Track enrollment pipeline metrics by trial, site, and time period. Monitor screening-to-enrollment conversion rates and identify recruitment bottlenecks."
              accent="teal"
            />
          </div>
        </div>
      </section>

      {/* Integration Strip */}
      <section className="py-12 px-6 border-y bg-white dark:bg-gray-900">
        <div className="max-w-5xl mx-auto">
          <p className="text-center text-sm font-medium text-muted-foreground mb-8">
            Standards & Integrations
          </p>
          <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-4">
            {[
              "FHIR R4",
              "OMOP CDM",
              "ICD-10-CM",
              "SNOMED CT",
              "LOINC",
              "RxNorm",
              "CPT",
              "HL7 v2",
              "CDS Hooks",
              "SMART on FHIR",
            ].map((standard) => (
              <span key={standard} className="text-sm font-mono text-muted-foreground/70 hover:text-foreground transition-colors">
                {standard}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Trust & Compliance */}
      <section className="py-16 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-2xl md:text-3xl font-bold">Security & Compliance</h2>
            <p className="text-muted-foreground mt-2">
              Built for regulated clinical environments
            </p>
          </div>

          <div className="grid md:grid-cols-4 gap-6">
            {[
              {
                icon: Shield,
                title: "HIPAA Compliant",
                description: "Full PHI protection with BAA support",
              },
              {
                icon: Lock,
                title: "SOC 2 Type II",
                description: "Enterprise security controls and audit trails",
              },
              {
                icon: FileText,
                title: "21 CFR Part 11",
                description: "FDA electronic records compliance",
              },
              {
                icon: Activity,
                title: "Audit Logging",
                description: "Complete data lineage and access tracking",
              },
            ].map(({ icon: Icon, title, description }) => (
              <div key={title} className="text-center p-6 rounded-xl border bg-white/50 dark:bg-gray-900/50">
                <div className="h-12 w-12 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto mb-4">
                  <Icon className="h-6 w-6 text-slate-600 dark:text-slate-400" />
                </div>
                <h3 className="font-semibold mb-1">{title}</h3>
                <p className="text-xs text-muted-foreground">{description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 px-6 bg-gradient-to-br from-blue-950 via-slate-900 to-blue-950 text-white relative overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:64px_64px]" />
        <div className="relative max-w-3xl mx-auto text-center">
          <h2 className="text-2xl md:text-3xl font-bold">
            Ready to Accelerate Enrollment?
          </h2>
          <p className="mt-4 text-blue-100/80 text-lg">
            See how automated eligibility screening can reduce time-to-enrollment
            for your clinical trials.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/trials">
              <Button size="lg" className="bg-white text-slate-900 hover:bg-blue-50 font-semibold px-8 shadow-lg">
                <FlaskConical className="mr-2 h-4 w-4" />
                Explore Trials
              </Button>
            </Link>
            <Link href="/dashboard">
              <Button size="lg" className="bg-transparent border border-white/30 text-white hover:bg-white/10 px-8">
                View Dashboard
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t bg-white dark:bg-gray-900">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <HeartPulse className="h-5 w-5 text-blue-600" />
            <span className="font-semibold text-sm">Clinical Ontology Normalizer</span>
          </div>
          <div className="flex items-center gap-6 text-xs text-muted-foreground">
            <span>HIPAA Compliant</span>
            <span>SOC 2 Type II</span>
            <span>21 CFR Part 11</span>
          </div>
          <p className="text-xs text-muted-foreground">
            &copy; 2026 Clinical Ontology Platform
          </p>
        </div>
      </footer>
    </div>
  );
}
