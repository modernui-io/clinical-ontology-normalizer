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
  Brain,
  Globe,
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
  | "Data Quality"
  | "NLP & Extraction"
  | "Interoperability";

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
  "NLP & Extraction": { icon: Brain, color: "bg-amber-500/10 text-amber-700 border-amber-200" },
  "Interoperability": { icon: Globe, color: "bg-cyan-500/10 text-cyan-700 border-cyan-200" },
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
  // Confidence & Scoring (additional)
  {
    term: "Precision & Recall",
    definition:
      "Precision measures how many of the system's positive identifications were correct; recall measures how many actual positives the system found.",
    systemUsage:
      "Computed per NLP model and per concept domain. Precision/recall trade-offs inform threshold tuning — higher thresholds increase precision at the cost of recall.",
    clinicianNote:
      "High precision means fewer false alarms. High recall means fewer missed findings. The right balance depends on clinical context — screening favors recall, diagnosis favors precision.",
    category: "Confidence & Scoring",
  },
  {
    term: "F1 Score",
    definition:
      "The harmonic mean of precision and recall, providing a single metric that balances both. Ranges from 0.0 (worst) to 1.0 (perfect).",
    systemUsage:
      "Primary evaluation metric for NLP extraction models. Reported per entity type (conditions, medications, procedures) in model evaluation dashboards.",
    clinicianNote:
      "An F1 of 0.90 means the system is doing well at both finding relevant concepts and avoiding false positives. Below 0.80 may warrant caution for that entity type.",
    category: "Confidence & Scoring",
  },
  {
    term: "Ensemble Agreement",
    definition:
      "The degree of consensus among multiple independent models or extraction methods when identifying the same clinical concept.",
    systemUsage:
      "The NLP pipeline runs rule-based and ML extractors in parallel. Ensemble agreement boosts confidence scores when methods converge and flags disagreements for review.",
    clinicianNote:
      "When multiple independent methods agree on a finding, it is more likely correct. Disagreements are flagged and may require your review.",
    category: "Confidence & Scoring",
  },
  {
    term: "Threshold",
    definition:
      "A configurable confidence cutoff that determines whether the system accepts, flags for review, or declines a particular extraction or mapping.",
    systemUsage:
      "Configured per risk tier and per domain. Thresholds can be adjusted via the admin dashboard without redeploying the system.",
    clinicianNote:
      "Thresholds control how cautious the system is. Tighter thresholds mean more items are routed for human review but fewer errors slip through.",
    category: "Confidence & Scoring",
  },
  // Evidence & Provenance (additional)
  {
    term: "Assertion Status",
    definition:
      "A classification of whether a clinical finding is present, absent, possible, conditional, or hypothetical based on the linguistic context in which it appears.",
    systemUsage:
      "Extracted by NLP assertion detection. Each mention carries an assertion attribute (present, negated, possible, conditional, hypothetical) that affects downstream fact building.",
    clinicianNote:
      "Assertion status is critical — 'patient denies chest pain' and 'patient reports chest pain' reference the same concept but have opposite clinical meanings.",
    category: "Evidence & Provenance",
  },
  {
    term: "Temporality",
    definition:
      "The time-related context of a clinical mention — whether it refers to a current, historical, or future/planned event.",
    systemUsage:
      "Detected by NLP temporal classifiers. Temporality attributes (current, historical, future) are stored on mentions and used to build accurate patient timelines in the knowledge graph.",
    clinicianNote:
      "Temporality distinguishes 'has diabetes' (current) from 'history of diabetes' (past). Getting this right is essential for accurate patient summaries.",
    category: "Evidence & Provenance",
  },
  {
    term: "Concept Hierarchy",
    definition:
      "The parent-child relationships between clinical concepts in a terminology, representing levels of specificity from general to detailed.",
    systemUsage:
      "Used in vocabulary navigation, concept rollup for analytics, and ancestor/descendant queries. The OMOP vocabulary provides hierarchy data for SNOMED, ICD, RxNorm, and others.",
    clinicianNote:
      "Hierarchies let you query at any level of detail — for example, searching for 'cardiovascular disease' can include all subtypes like heart failure, atrial fibrillation, and hypertension.",
    category: "Evidence & Provenance",
  },
  {
    term: "Semantic Similarity",
    definition:
      "A numerical measure of how closely related two clinical concepts are in meaning, computed using embedding models or ontological distance in concept hierarchies.",
    systemUsage:
      "Powers concept search, fuzzy vocabulary matching, and deduplication of near-identical findings. The graph embedding service generates concept vectors for similarity computation.",
    clinicianNote:
      "Semantic similarity helps the system recognize that 'heart attack' and 'myocardial infarction' mean the same thing, even though they use different words.",
    category: "Evidence & Provenance",
  },
  // Safety & Controls (additional)
  {
    term: "Audit Trail",
    definition:
      "A tamper-evident chronological record of all system actions, user interactions, and data transformations performed on clinical data.",
    systemUsage:
      "Every API call, data modification, and pipeline action is logged with user identity, timestamp, and affected resources. Required for HIPAA compliance and clinical accountability.",
    clinicianNote:
      "The audit trail answers 'who did what, when, and why' for any piece of data. It provides accountability and supports regulatory compliance reviews.",
    category: "Safety & Controls",
  },
  {
    term: "Circuit Breaker",
    definition:
      "A fault-tolerance pattern that stops calling a failing service after repeated errors, preventing cascading failures across the system.",
    systemUsage:
      "Wraps calls to external services (NLP models, graph database, terminology APIs). After a configurable number of failures, the breaker opens and the system enters degraded mode for that dependency.",
    clinicianNote:
      "Circuit breakers ensure that one failing component does not bring down the entire system. Core functionality continues while the failing part recovers.",
    category: "Safety & Controls",
  },
  {
    term: "Safety Envelope",
    definition:
      "The set of all safety constraints, confidence thresholds, and validation rules that collectively define the boundaries of safe automated operation.",
    systemUsage:
      "Implemented across the pipeline: input validation at ingestion, confidence gates at extraction, risk-tier checks at fact building, and action gates at output. All critical paths fail loudly rather than silently.",
    clinicianNote:
      "The safety envelope defines what the system can do autonomously vs. what requires human oversight. Operating within the envelope means all safety checks have passed.",
    category: "Safety & Controls",
  },
  {
    term: "Consent Management",
    definition:
      "The tracking and enforcement of patient consent preferences governing how their clinical data may be processed, shared, or used in analytics.",
    systemUsage:
      "Consent records are checked at data access points. Processing pipelines filter or redact data based on active consent directives. Audit logging captures all consent-gated access.",
    clinicianNote:
      "The system respects patient consent at every step. If a patient has restricted certain data sharing, those restrictions are automatically enforced across all system functions.",
    category: "Safety & Controls",
  },
  // Data Quality (additional)
  {
    term: "Completeness",
    definition:
      "The proportion of expected data fields that are present and populated in a clinical record, measuring whether the record contains all required information.",
    systemUsage:
      "Evaluated per document and per patient record. Missing required fields (diagnosis codes, medication dosages) are flagged with severity levels in data quality reports.",
    clinicianNote:
      "Incomplete records can lead to missed findings. A completeness score below 80% suggests the source note may be missing important clinical details.",
    category: "Data Quality",
  },
  {
    term: "Deduplication",
    definition:
      "The process of identifying and merging duplicate clinical findings that refer to the same underlying concept, often extracted from multiple documents or encounters.",
    systemUsage:
      "Performed by the fact builder during ClinicalFact creation. Uses concept identity, temporal overlap, and source provenance to determine whether two mentions represent the same clinical fact.",
    clinicianNote:
      "Deduplication prevents the same condition from appearing multiple times in a patient summary, ensuring a clean and accurate clinical picture.",
    category: "Data Quality",
  },
  {
    term: "Conformance",
    definition:
      "The degree to which clinical data adheres to expected formats, value sets, and structural rules defined by standards like OMOP, FHIR, or institutional policies.",
    systemUsage:
      "Checked during ingestion and mapping. Non-conformant data (wrong value sets, invalid codes, structural violations) is logged and routed for correction.",
    clinicianNote:
      "Conformant data follows the expected rules and standards. Non-conformant data may be processed incorrectly or rejected, so it needs correction at the source.",
    category: "Data Quality",
  },
  {
    term: "Plausibility",
    definition:
      "The assessment of whether clinical data values fall within medically reasonable ranges and are consistent with expected physiological parameters.",
    systemUsage:
      "Plausibility checks flag values outside clinical ranges (e.g., heart rate of 500, age of 200). Implements OHDSI-style plausibility rules across numeric and categorical fields.",
    clinicianNote:
      "Implausible values are almost always data entry errors. The system flags these automatically so they can be corrected before affecting analysis or clinical decisions.",
    category: "Data Quality",
  },
  // NLP & Extraction
  {
    term: "Named Entity Recognition",
    definition:
      "The NLP task of identifying and classifying spans of text that refer to clinical entities such as conditions, medications, procedures, anatomical sites, and lab tests.",
    systemUsage:
      "The core extraction step in the pipeline. Both rule-based (pattern matching, dictionary lookup) and ML (transformer, ensemble) NER models run in parallel to maximize coverage.",
    clinicianNote:
      "NER is how the system finds clinical concepts in free-text notes. It highlights phrases like 'type 2 diabetes' or 'metformin 500mg' and labels them by type.",
    category: "NLP & Extraction",
  },
  {
    term: "Negation Detection",
    definition:
      "The identification of linguistic cues indicating that a clinical concept is denied, absent, or ruled out rather than present or confirmed.",
    systemUsage:
      "Applied after NER to set assertion status. Uses NegEx-style rules and contextual ML models to detect negation scopes in clinical text. Critical for accurate fact building.",
    clinicianNote:
      "Negation detection ensures 'no evidence of cancer' is not misinterpreted as a cancer diagnosis. It is one of the most important accuracy checks in clinical NLP.",
    category: "NLP & Extraction",
  },
  {
    term: "Span",
    definition:
      "The exact character range (start and end offsets) in a source document where a clinical concept mention was identified by the NLP system.",
    systemUsage:
      "Stored on every Mention record. Enables precise highlighting in the document viewer and supports provenance tracing back to exact source text.",
    clinicianNote:
      "Spans let you click on any extracted concept and see exactly where in the original note it came from, making it easy to verify the system's work.",
    category: "NLP & Extraction",
  },
  {
    term: "Experiencer",
    definition:
      "The person to whom a clinical finding applies — typically the patient, but potentially a family member (family history) or someone else mentioned in the note.",
    systemUsage:
      "Classified per mention as patient, family, or other. Family history mentions are tagged differently from patient findings to avoid incorrect attribution in the knowledge graph.",
    clinicianNote:
      "Experiencer detection distinguishes 'patient has diabetes' from 'father had diabetes'. Getting this right is essential for accurate personal vs. family medical histories.",
    category: "NLP & Extraction",
  },
  {
    term: "Section Detection",
    definition:
      "The identification of structural sections within a clinical document (e.g., Chief Complaint, Medications, Assessment/Plan) to provide context for extracted concepts.",
    systemUsage:
      "Section headers are detected using pattern matching and layout analysis. Section context improves extraction accuracy — a medication name in the 'Allergies' section has different meaning than in 'Current Medications'.",
    clinicianNote:
      "Where a concept appears in a note matters. The system uses section context to correctly interpret findings — 'aspirin' under Allergies is very different from 'aspirin' under Medications.",
    category: "NLP & Extraction",
  },
  {
    term: "Tokenization",
    definition:
      "The process of breaking clinical text into individual units (tokens) such as words, punctuation, and abbreviations for downstream NLP processing.",
    systemUsage:
      "First step in the NLP pipeline. Uses a clinical-aware tokenizer that handles medical abbreviations, dosage formats, and special characters common in clinical notes.",
    clinicianNote:
      "Clinical text has unique challenges — abbreviations like 'q.i.d.' and dosage formats like '500mg/5mL' need special handling to be processed correctly.",
    category: "NLP & Extraction",
  },
  // Interoperability
  {
    term: "FHIR Resource",
    definition:
      "A standardized data unit in the HL7 FHIR (Fast Healthcare Interoperability Resources) specification, representing a clinical concept such as a Patient, Condition, Observation, or MedicationRequest.",
    systemUsage:
      "The FHIR import/export service converts between internal ClinicalFacts and FHIR Resources. Supports FHIR R4 for integration with EHR systems and health information exchanges.",
    clinicianNote:
      "FHIR is the modern standard for sharing healthcare data between systems. It allows the platform to exchange data with your EHR and other clinical systems seamlessly.",
    category: "Interoperability",
  },
  {
    term: "SNOMED CT",
    definition:
      "A comprehensive clinical terminology providing standardized codes for diseases, symptoms, procedures, body structures, and other clinical concepts used worldwide.",
    systemUsage:
      "One of the primary target vocabularies for concept mapping. SNOMED concepts are mapped to OMOP standard concepts and used for clinical reasoning in the knowledge graph.",
    clinicianNote:
      "SNOMED CT provides the detailed clinical language the system uses internally. It ensures that clinical concepts are represented precisely and consistently.",
    category: "Interoperability",
  },
  {
    term: "ICD-10",
    definition:
      "The International Classification of Diseases, 10th Revision — a coding system used primarily for billing, epidemiology, and public health reporting of diagnoses and procedures.",
    systemUsage:
      "Supported as both a source vocabulary (from billing data) and a mapping target. Cross-mapped with SNOMED CT through the OMOP vocabulary. Used in the billing/coding stack.",
    clinicianNote:
      "ICD-10 codes are what you see on billing records and problem lists. The system maps between ICD-10 and more detailed clinical terminologies automatically.",
    category: "Interoperability",
  },
  {
    term: "RxNorm",
    definition:
      "A standardized naming system for medications maintained by the NLM, providing normalized names and codes for clinical drugs at multiple levels of specificity.",
    systemUsage:
      "The primary vocabulary for medication mapping. Used by the drug safety and drug interaction services. Supports ingredient, clinical drug, and branded drug levels.",
    clinicianNote:
      "RxNorm standardizes medication names so 'Lipitor 20mg tablet' and 'atorvastatin calcium 20mg oral tablet' are recognized as the same drug.",
    category: "Interoperability",
  },
  {
    term: "Value Set",
    definition:
      "A defined collection of codes from one or more terminologies that represent a specific clinical concept group, such as 'all diabetes diagnoses' or 'cardiovascular medications'.",
    systemUsage:
      "Managed via the value set editor. Used in quality measures, clinical decision support rules, and cohort definitions. Supports expansion, versioning, and comparison.",
    clinicianNote:
      "Value sets define clinical groupings — for example, a 'Diabetes' value set includes all the different codes that represent diabetes, making it easy to query across coding systems.",
    category: "Interoperability",
  },
  {
    term: "CDS Hooks",
    definition:
      "A standard for integrating clinical decision support into EHR workflows, triggering automated advice at specific points in the clinician's workflow.",
    systemUsage:
      "The CDS Hooks service exposes platform intelligence (drug interactions, clinical calculators, guideline recommendations) as hook responses that EHR systems can consume in real time.",
    clinicianNote:
      "CDS Hooks deliver the platform's insights directly into your EHR workflow — for example, alerting you to a drug interaction right when you are placing an order.",
    category: "Interoperability",
  },
  {
    term: "SMART on FHIR",
    definition:
      "An open standard for launching third-party applications within an EHR, providing secure OAuth2-based authorization and access to patient data through FHIR APIs.",
    systemUsage:
      "Enables the platform to be launched from within an EHR as a SMART app, receiving patient context and authorization automatically. Supports standalone and EHR-launch workflows.",
    clinicianNote:
      "SMART on FHIR means you can access the platform directly from your EHR without logging in separately — it opens with the right patient already loaded.",
    category: "Interoperability",
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
    "NLP & Extraction",
    "Interoperability",
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
