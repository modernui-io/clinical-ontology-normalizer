"use client";

import { useState, useMemo } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  BookOpen,
  Search,
  Shield,
  BarChart3,
  Database,
  Activity,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";

// =============================================================================
// Types
// =============================================================================

interface GlossaryTerm {
  term: string;
  definition: string;
  systemUsage: string;
  clinicianNote: string;
  category: Category;
}

type Category =
  | "Confidence & Scoring"
  | "Evidence & Provenance"
  | "Safety & Controls"
  | "Data Quality";

// =============================================================================
// Glossary data
// =============================================================================

const CATEGORY_META: Record<
  Category,
  { icon: React.ComponentType<{ className?: string }>; color: string }
> = {
  "Confidence & Scoring": { icon: BarChart3, color: "bg-blue-500/10 text-blue-700 border-blue-200" },
  "Evidence & Provenance": { icon: Database, color: "bg-purple-500/10 text-purple-700 border-purple-200" },
  "Safety & Controls": { icon: Shield, color: "bg-red-500/10 text-red-700 border-red-200" },
  "Data Quality": { icon: Activity, color: "bg-emerald-500/10 text-emerald-700 border-emerald-200" },
};

const GLOSSARY_TERMS: GlossaryTerm[] = [
  // Confidence & Scoring
  {
    term: "Confidence Score",
    definition:
      "A numerical value (0.0 to 1.0) representing the system's certainty that a clinical concept was correctly identified and mapped.",
    systemUsage:
      "Attached to every extracted mention and concept mapping. Scores below configurable thresholds trigger human review workflows.",
    clinicianNote:
      "A confidence score of 0.95 means the system is highly certain. Scores below 0.7 should always be reviewed by a clinician before acting on the result.",
    category: "Confidence & Scoring",
  },
  {
    term: "Evidence Weight",
    definition:
      "A composite score reflecting the strength and quality of evidence supporting a clinical assertion, factoring in source reliability, recency, and corroboration.",
    systemUsage:
      "Used by the fact builder to rank competing concept mappings and by the clinical agent when generating recommendations.",
    clinicianNote:
      "Higher evidence weight means more reliable data sources agree. Low weights may indicate the finding came from a single, older, or less reliable source.",
    category: "Confidence & Scoring",
  },
  {
    term: "Calibration",
    definition:
      "The degree to which predicted confidence scores match actual correctness rates. A well-calibrated system's 80% confidence predictions are correct 80% of the time.",
    systemUsage:
      "Monitored via drift detection. If calibration drifts beyond tolerance, the system flags the model for retraining or manual review.",
    clinicianNote:
      "Well-calibrated scores are trustworthy — if the system says 90% confident, it really is right about 90% of the time. Miscalibration is a quality signal.",
    category: "Confidence & Scoring",
  },
  {
    term: "Coverage",
    definition:
      "The proportion of clinical concepts in a document that the system successfully identifies and maps to standard terminologies.",
    systemUsage:
      "Reported per document and per pipeline run. Low coverage triggers data quality alerts and may indicate vocabulary gaps.",
    clinicianNote:
      "100% coverage is rare for complex notes. Coverage below 70% suggests the document may need manual review for missed concepts.",
    category: "Confidence & Scoring",
  },
  // Evidence & Provenance
  {
    term: "Provenance",
    definition:
      "The complete trail of where a piece of clinical data originated, how it was transformed, and what processing steps were applied.",
    systemUsage:
      "Every ClinicalFact stores a provenance chain linking back to the source document, extraction model, and mapping version used.",
    clinicianNote:
      "Provenance lets you trace any result back to its source note and understand exactly how the system arrived at a conclusion. Essential for clinical accountability.",
    category: "Evidence & Provenance",
  },
  {
    term: "Knowledge Graph",
    definition:
      "A network of interconnected clinical entities (patients, conditions, medications, procedures) and their relationships, built from extracted and normalized clinical data.",
    systemUsage:
      "Constructed by the graph builder service. Supports graph queries, clinical reasoning, and GraphRAG for context-aware AI responses.",
    clinicianNote:
      "The knowledge graph is how the system understands relationships — for example, which medications a patient takes for which conditions, and when treatments changed.",
    category: "Evidence & Provenance",
  },
  {
    term: "OMOP Concept",
    definition:
      "A standardized representation of a clinical concept from the OHDSI OMOP Common Data Model, providing a universal vocabulary for clinical data.",
    systemUsage:
      "All extracted mentions are mapped to OMOP concepts. The vocabulary service provides search, hierarchy navigation, and cross-vocabulary mapping.",
    clinicianNote:
      "OMOP standardization means the same condition is represented the same way regardless of how it was originally documented, enabling reliable analytics and comparison.",
    category: "Evidence & Provenance",
  },
  {
    term: "Mention",
    definition:
      "A specific span of text in a clinical document that the NLP system has identified as referring to a clinical concept, including its position, assertion status, and context.",
    systemUsage:
      "The core unit of NLP extraction. Each mention includes character offsets, negation/assertion attributes, temporality, and candidate OMOP mappings.",
    clinicianNote:
      "A mention is the exact phrase the system found in the note — for example, 'type 2 diabetes' at characters 45-62 with assertion status 'present'.",
    category: "Evidence & Provenance",
  },
  {
    term: "ClinicalFact",
    definition:
      "A normalized, evidence-backed clinical assertion derived from one or more mentions, representing a verified piece of clinical knowledge about a patient.",
    systemUsage:
      "Created by the fact builder after deduplication, conflict resolution, and evidence weighting of multiple mentions across documents.",
    clinicianNote:
      "A ClinicalFact is the system's best understanding of a clinical truth — for example, 'Patient has diabetes (Type 2), confirmed across 3 documents'.",
    category: "Evidence & Provenance",
  },
  // Safety & Controls
  {
    term: "Decline",
    definition:
      "The system's decision to abstain from providing a result when confidence is too low or safety constraints are not met, rather than returning a potentially incorrect answer.",
    systemUsage:
      "Triggered when confidence falls below the decline threshold or when safety gates detect high-risk scenarios. The system returns an explicit 'declined' status with reasoning.",
    clinicianNote:
      "When the system declines, it is being transparent about its limitations. This is a safety feature — it is better to say 'I am not sure' than to give a wrong answer.",
    category: "Safety & Controls",
  },
  {
    term: "Degraded Mode",
    definition:
      "An operational state where the system continues functioning with reduced capabilities because one or more non-critical dependencies are unavailable.",
    systemUsage:
      "Automatically entered when Redis, Neo4j, or Kafka become unreachable. Core NLP and mapping still work; graph queries and real-time streaming may be limited.",
    clinicianNote:
      "In degraded mode, the system still processes documents but some features (like graph-based reasoning) may be temporarily unavailable. Core safety checks remain active.",
    category: "Safety & Controls",
  },
  {
    term: "Risk Tier",
    definition:
      "A classification (Low, Medium, High, Critical) assigned to clinical operations based on their potential impact on patient safety and clinical decision-making.",
    systemUsage:
      "Determines which approval gates, audit logging levels, and confidence thresholds apply. Critical-tier operations require higher confidence and may trigger human-in-the-loop review.",
    clinicianNote:
      "Risk tiers ensure that high-stakes operations (like drug interaction alerts) receive more scrutiny than lower-risk operations (like demographic extraction).",
    category: "Safety & Controls",
  },
  {
    term: "Action Gate",
    definition:
      "A configurable checkpoint that must be satisfied before the system takes a clinical action, such as generating an alert or recommendation.",
    systemUsage:
      "Implemented in the policy engine. Gates can require minimum confidence scores, mandatory provenance chains, or explicit human approval based on risk tier.",
    clinicianNote:
      "Action gates are guardrails. They prevent the system from acting on uncertain information and ensure that high-risk actions always involve human oversight.",
    category: "Safety & Controls",
  },
  {
    term: "Human-in-the-Loop",
    definition:
      "A workflow pattern where the system pauses automated processing and routes a decision to a qualified clinician for review and approval.",
    systemUsage:
      "Triggered by action gates, low-confidence mappings, or critical risk tier operations. The system queues items for review with full context and provenance.",
    clinicianNote:
      "The system will ask for your input when it cannot make a safe decision alone. Your expertise is the final authority in these situations.",
    category: "Safety & Controls",
  },
  // Data Quality
  {
    term: "Data Quality Index",
    definition:
      "A composite metric measuring the completeness, consistency, conformance, and plausibility of clinical data passing through the system.",
    systemUsage:
      "Computed per document and per batch. Feeds into quality dashboards and triggers alerts when thresholds are breached. Follows OHDSI Data Quality Dashboard conventions.",
    clinicianNote:
      "A high Data Quality Index means the data is complete, consistent, and reliable. Low scores indicate missing fields, contradictions, or implausible values that may affect downstream analysis.",
    category: "Data Quality",
  },
  {
    term: "Drift Detection",
    definition:
      "Automated monitoring that identifies when the statistical properties of incoming data or model performance shift significantly from established baselines.",
    systemUsage:
      "Runs continuously against NLP extraction accuracy, concept mapping distributions, and confidence score calibration. Triggers alerts and potential model retraining.",
    clinicianNote:
      "Drift detection catches situations where the system's accuracy may be declining — for example, if a new documentation style is causing more extraction errors.",
    category: "Data Quality",
  },
  {
    term: "Validation Rule",
    definition:
      "A programmatic check that verifies clinical data meets expected constraints — such as value ranges, required fields, or logical consistency between related concepts.",
    systemUsage:
      "Applied during document ingestion, NLP extraction, and OMOP mapping. Failed validations are logged and may block pipeline progression depending on severity.",
    clinicianNote:
      "Validation rules catch obvious errors early — like a blood pressure of 500/300 or a missing diagnosis code. They are the first line of defense for data quality.",
    category: "Data Quality",
  },
  {
    term: "Gold Standard",
    definition:
      "A curated set of expert-annotated clinical documents used as ground truth for evaluating and benchmarking NLP extraction and concept mapping accuracy.",
    systemUsage:
      "Used in validation studies and model evaluation. Performance metrics (precision, recall, F1) are computed against the gold standard corpus.",
    clinicianNote:
      "The gold standard is created by clinical experts and represents the 'correct answer'. It is how we measure whether the system is performing accurately.",
    category: "Data Quality",
  },
];

// =============================================================================
// Component
// =============================================================================

export default function GlossaryPage() {
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<Category | "All">(
    "All",
  );
  const [expandedTerms, setExpandedTerms] = useState<Set<string>>(new Set());

  const categories: (Category | "All")[] = [
    "All",
    "Confidence & Scoring",
    "Evidence & Provenance",
    "Safety & Controls",
    "Data Quality",
  ];

  const filteredTerms = useMemo(() => {
    return GLOSSARY_TERMS.filter((t) => {
      const matchesSearch =
        !search ||
        t.term.toLowerCase().includes(search.toLowerCase()) ||
        t.definition.toLowerCase().includes(search.toLowerCase());
      const matchesCategory =
        selectedCategory === "All" || t.category === selectedCategory;
      return matchesSearch && matchesCategory;
    });
  }, [search, selectedCategory]);

  const toggleTerm = (term: string) => {
    setExpandedTerms((prev) => {
      const next = new Set(prev);
      if (next.has(term)) {
        next.delete(term);
      } else {
        next.add(term);
      }
      return next;
    });
  };

  const groupedTerms = useMemo(() => {
    const groups: Record<string, GlossaryTerm[]> = {};
    for (const term of filteredTerms) {
      if (!groups[term.category]) groups[term.category] = [];
      groups[term.category].push(term);
    }
    return groups;
  }, [filteredTerms]);

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BookOpen className="h-6 w-6" />
          Clinical AI Glossary
        </h1>
        <p className="text-muted-foreground mt-1">
          Reference guide for confidence, evidence, safety, and data quality
          concepts used throughout the Sulci platform.
        </p>
      </div>

      {/* Search and filter bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search terms..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          {categories.map((cat) => (
            <Button
              key={cat}
              variant={selectedCategory === cat ? "default" : "outline"}
              size="sm"
              onClick={() => setSelectedCategory(cat)}
            >
              {cat}
            </Button>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="flex gap-4 text-sm text-muted-foreground">
        <span>
          Showing {filteredTerms.length} of {GLOSSARY_TERMS.length} terms
        </span>
      </div>

      {/* Terms by category */}
      {Object.entries(groupedTerms).map(([category, terms]) => {
        const meta = CATEGORY_META[category as Category];
        const Icon = meta.icon;
        return (
          <div key={category} className="space-y-3">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Icon className="h-5 w-5" />
              {category}
              <Badge variant="secondary" className="ml-1">
                {terms.length}
              </Badge>
            </h2>
            <div className="grid gap-2">
              {terms.map((t) => {
                const isExpanded = expandedTerms.has(t.term);
                return (
                  <Card key={t.term} className="transition-shadow hover:shadow-md">
                    <CardHeader
                      className="cursor-pointer py-3 px-4"
                      onClick={() => toggleTerm(t.term)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          )}
                          <CardTitle className="text-base">
                            {t.term}
                          </CardTitle>
                        </div>
                        <Badge
                          variant="outline"
                          className={meta.color}
                        >
                          {t.category}
                        </Badge>
                      </div>
                      <CardDescription className="ml-6">
                        {t.definition}
                      </CardDescription>
                    </CardHeader>
                    {isExpanded && (
                      <CardContent className="pt-0 pb-4 px-4 ml-6 space-y-3">
                        <div>
                          <p className="text-sm font-medium text-muted-foreground">
                            How it is used in the system
                          </p>
                          <p className="text-sm mt-1">{t.systemUsage}</p>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-muted-foreground">
                            What clinicians should know
                          </p>
                          <p className="text-sm mt-1">{t.clinicianNote}</p>
                        </div>
                      </CardContent>
                    )}
                  </Card>
                );
              })}
            </div>
          </div>
        );
      })}

      {filteredTerms.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No terms match your search. Try a different query or category filter.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
