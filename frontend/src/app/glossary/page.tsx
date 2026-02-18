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
import { Separator } from "@/components/ui/separator";
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
  Workflow,
  Lock,
  Monitor,
  Stethoscope,
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
  | "Interoperability"
  | "Clinical Workflows"
  | "Privacy & Compliance";

// =============================================================================
// Glossary data
// =============================================================================

interface CategoryMeta {
  icon: React.ComponentType<{ className?: string }>;
  badge: string;
  border: string;
  bg: string;
  iconColor: string;
  cardBg: string;
}

const CATEGORY_META: Record<Category, CategoryMeta> = {
  "Confidence & Scoring": {
    icon: BarChart3,
    badge: "bg-blue-500/10 text-blue-700 border-blue-200 dark:text-blue-400",
    border: "border-l-blue-500",
    bg: "bg-blue-50 dark:bg-blue-950/30",
    iconColor: "text-blue-600 dark:text-blue-400",
    cardBg: "hover:bg-blue-50/50 dark:hover:bg-blue-950/20",
  },
  "Evidence & Provenance": {
    icon: Database,
    badge: "bg-purple-500/10 text-purple-700 border-purple-200 dark:text-purple-400",
    border: "border-l-purple-500",
    bg: "bg-purple-50 dark:bg-purple-950/30",
    iconColor: "text-purple-600 dark:text-purple-400",
    cardBg: "hover:bg-purple-50/50 dark:hover:bg-purple-950/20",
  },
  "Safety & Controls": {
    icon: Shield,
    badge: "bg-red-500/10 text-red-700 border-red-200 dark:text-red-400",
    border: "border-l-red-500",
    bg: "bg-red-50 dark:bg-red-950/30",
    iconColor: "text-red-600 dark:text-red-400",
    cardBg: "hover:bg-red-50/50 dark:hover:bg-red-950/20",
  },
  "Data Quality": {
    icon: Activity,
    badge: "bg-emerald-500/10 text-emerald-700 border-emerald-200 dark:text-emerald-400",
    border: "border-l-emerald-500",
    bg: "bg-emerald-50 dark:bg-emerald-950/30",
    iconColor: "text-emerald-600 dark:text-emerald-400",
    cardBg: "hover:bg-emerald-50/50 dark:hover:bg-emerald-950/20",
  },
  "NLP & Extraction": {
    icon: Brain,
    badge: "bg-amber-500/10 text-amber-700 border-amber-200 dark:text-amber-400",
    border: "border-l-amber-500",
    bg: "bg-amber-50 dark:bg-amber-950/30",
    iconColor: "text-amber-600 dark:text-amber-400",
    cardBg: "hover:bg-amber-50/50 dark:hover:bg-amber-950/20",
  },
  "Interoperability": {
    icon: Globe,
    badge: "bg-cyan-500/10 text-cyan-700 border-cyan-200 dark:text-cyan-400",
    border: "border-l-cyan-500",
    bg: "bg-cyan-50 dark:bg-cyan-950/30",
    iconColor: "text-cyan-600 dark:text-cyan-400",
    cardBg: "hover:bg-cyan-50/50 dark:hover:bg-cyan-950/20",
  },
  "Clinical Workflows": {
    icon: Workflow,
    badge: "bg-orange-500/10 text-orange-700 border-orange-200 dark:text-orange-400",
    border: "border-l-orange-500",
    bg: "bg-orange-50 dark:bg-orange-950/30",
    iconColor: "text-orange-600 dark:text-orange-400",
    cardBg: "hover:bg-orange-50/50 dark:hover:bg-orange-950/20",
  },
  "Privacy & Compliance": {
    icon: Lock,
    badge: "bg-rose-500/10 text-rose-700 border-rose-200 dark:text-rose-400",
    border: "border-l-rose-500",
    bg: "bg-rose-50 dark:bg-rose-950/30",
    iconColor: "text-rose-600 dark:text-rose-400",
    cardBg: "hover:bg-rose-50/50 dark:hover:bg-rose-950/20",
  },
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
  // Interoperability (additional)
  {
    term: "LOINC",
    definition:
      "Logical Observation Identifiers Names and Codes — a universal standard for identifying laboratory tests, clinical observations, and survey instruments.",
    systemUsage:
      "Used as the standard vocabulary for lab result mapping. Lab observations are normalized to LOINC codes for cross-institutional comparability and quality measure computation.",
    clinicianNote:
      "LOINC ensures that a 'hemoglobin A1c' test means the same thing regardless of which lab performed it, enabling reliable comparison of results across systems.",
    category: "Interoperability",
  },
  {
    term: "CPT Code",
    definition:
      "Current Procedural Terminology — a standardized coding system maintained by the AMA for reporting medical procedures and services performed by healthcare providers.",
    systemUsage:
      "Supported as a source vocabulary from billing data and as a mapping target. Cross-referenced with SNOMED CT procedure concepts through the OMOP vocabulary tables.",
    clinicianNote:
      "CPT codes are what appear on your procedure billing. The system maps these to richer clinical vocabularies so procedures can be analyzed in full clinical context.",
    category: "Interoperability",
  },
  {
    term: "HL7 v2 Message",
    definition:
      "A legacy but widely deployed healthcare messaging format used for transmitting clinical data (lab results, admissions, orders) between healthcare systems via structured text segments.",
    systemUsage:
      "The ingestion pipeline can parse HL7 v2 messages (ADT, ORU, ORM) and extract clinical data for normalization. Segment-level parsing maps fields to the internal data model.",
    clinicianNote:
      "HL7 v2 is the format many hospital systems still use to exchange data. The platform can receive and process these messages alongside modern FHIR-based data.",
    category: "Interoperability",
  },
  {
    term: "Terminology Mapping",
    definition:
      "The process of establishing equivalences between concepts in different clinical vocabularies, enabling translation from one coding system to another.",
    systemUsage:
      "The mapping service maintains cross-walks between ICD-10, SNOMED CT, RxNorm, LOINC, and OMOP standard concepts. Mappings are versioned and auditable.",
    clinicianNote:
      "Terminology mapping is how the system translates between the many coding systems used in healthcare, ensuring concepts are correctly represented regardless of their original source.",
    category: "Interoperability",
  },
  // Confidence & Scoring (additional)
  {
    term: "Sensitivity & Specificity",
    definition:
      "Sensitivity measures the ability to correctly identify positive cases (true positive rate); specificity measures the ability to correctly identify negative cases (true negative rate).",
    systemUsage:
      "Reported for binary classification tasks like assertion detection and negation detection. Used alongside precision/recall to evaluate clinical NLP model performance.",
    clinicianNote:
      "High sensitivity means the system rarely misses real findings. High specificity means it rarely creates false alarms. Both matter for clinical trust.",
    category: "Confidence & Scoring",
  },
  {
    term: "Area Under the Curve (AUC)",
    definition:
      "A summary metric representing overall model discrimination ability across all possible classification thresholds, ranging from 0.5 (random) to 1.0 (perfect).",
    systemUsage:
      "Computed during model evaluation for concept classification and risk prediction tasks. AUC values are tracked over time to detect performance degradation.",
    clinicianNote:
      "AUC tells you how well the system can distinguish between positive and negative cases overall. An AUC above 0.90 indicates excellent discrimination ability.",
    category: "Confidence & Scoring",
  },
  {
    term: "Inter-Annotator Agreement",
    definition:
      "A statistical measure of how consistently multiple human experts label the same clinical data, typically expressed as Cohen's kappa or Fleiss' kappa.",
    systemUsage:
      "Computed during gold standard creation to ensure annotation quality. Low agreement areas are flagged for guideline revision or additional expert review.",
    clinicianNote:
      "If experts disagree on how to label clinical text, the system cannot be expected to do better. Agreement scores set the ceiling for expected system performance.",
    category: "Confidence & Scoring",
  },
  // Evidence & Provenance (additional)
  {
    term: "Document Type Classification",
    definition:
      "Automatic identification of the clinical document category (discharge summary, progress note, radiology report, pathology report, etc.) to apply type-specific processing.",
    systemUsage:
      "Applied at ingestion time. Document type informs which NLP models and extraction rules to apply — a radiology report uses different patterns than a discharge summary.",
    clinicianNote:
      "Different note types contain different kinds of information. The system tailors its extraction approach based on document type for better accuracy.",
    category: "Evidence & Provenance",
  },
  {
    term: "Entity Linking",
    definition:
      "The process of resolving an extracted text mention to a specific concept in a knowledge base or terminology, disambiguating between multiple possible meanings.",
    systemUsage:
      "Performed after NER. The mention 'MS' could mean multiple sclerosis, mitral stenosis, or morphine sulfate — entity linking uses context to select the correct OMOP concept.",
    clinicianNote:
      "Medical abbreviations often have multiple meanings. Entity linking is how the system figures out that 'MS' in a neurology note means multiple sclerosis, not morphine sulfate.",
    category: "Evidence & Provenance",
  },
  {
    term: "Relation Extraction",
    definition:
      "The NLP task of identifying meaningful relationships between clinical entities within text, such as a medication treating a condition or a test diagnosing a disease.",
    systemUsage:
      "Feeds the knowledge graph builder. Extracted relations (treats, causes, diagnosed-by, contraindicated-with) become edges connecting nodes in the patient knowledge graph.",
    clinicianNote:
      "Relation extraction captures not just what concepts are mentioned but how they relate — for example, that metformin is prescribed FOR diabetes, not just that both appear in the note.",
    category: "Evidence & Provenance",
  },
  // Safety & Controls (additional)
  {
    term: "Explainability",
    definition:
      "The ability of the system to provide human-understandable explanations for its outputs, including why a particular concept was identified or a recommendation was made.",
    systemUsage:
      "Every extraction and mapping includes an explanation trace — which rules fired, which model features contributed, and what evidence supports the result. Exposed via the provenance API.",
    clinicianNote:
      "You can always ask 'why' the system made a decision. Explainability traces show the reasoning chain, helping you evaluate whether to trust a specific result.",
    category: "Safety & Controls",
  },
  {
    term: "Rollback",
    definition:
      "The ability to revert a processing operation or data change to a previous known-good state, undoing the effects of an incorrect or problematic pipeline run.",
    systemUsage:
      "All pipeline operations are versioned. If a batch extraction produces poor results, the entire run can be rolled back to restore previous ClinicalFacts and graph state.",
    clinicianNote:
      "If a processing error is discovered, the system can undo the damage and restore the previous correct state, rather than requiring manual cleanup.",
    category: "Safety & Controls",
  },
  {
    term: "Rate Limiting",
    definition:
      "Controls that restrict the volume and frequency of system operations to prevent overload, abuse, or runaway processes from consuming excessive resources.",
    systemUsage:
      "Applied to API endpoints, NLP pipeline throughput, and external service calls. Configurable per-user, per-endpoint, and per-resource with burst allowances.",
    clinicianNote:
      "Rate limiting protects the system from being overwhelmed, ensuring consistent performance for all users even during heavy processing periods.",
    category: "Safety & Controls",
  },
  // Data Quality (additional)
  {
    term: "Timeliness",
    definition:
      "The measurement of how current clinical data is — whether records reflect the most recent patient encounters, results, and clinical events.",
    systemUsage:
      "Tracked per data source and per document. Stale data (documents not updated within expected intervals) is flagged in quality dashboards and may affect confidence scoring.",
    clinicianNote:
      "Timely data means the system reflects your patient's current state. Stale data could lead to outdated recommendations, so timeliness alerts are clinically important.",
    category: "Data Quality",
  },
  {
    term: "Uniqueness",
    definition:
      "The verification that each clinical record represents a distinct entity or event, with no unintended duplicate entries that could skew analytics or clinical summaries.",
    systemUsage:
      "Checked across patient records, document ingestion, and ClinicalFact creation. Duplicate detection uses a combination of identifiers, semantic similarity, and temporal overlap.",
    clinicianNote:
      "Duplicate records inflate problem lists and can cause incorrect dosage calculations. Uniqueness checking prevents the same finding from appearing twice.",
    category: "Data Quality",
  },
  {
    term: "Data Lineage",
    definition:
      "The end-to-end record of how a piece of data was created, transformed, and consumed as it moved through the processing pipeline from source to final output.",
    systemUsage:
      "Extends provenance with full pipeline metadata — which extraction version, mapping table version, and graph build generated each data point. Supports reproducibility and debugging.",
    clinicianNote:
      "Data lineage is the full biography of a data point. If a result looks wrong, lineage lets the team trace exactly which step introduced the issue.",
    category: "Data Quality",
  },
  {
    term: "Outlier Detection",
    definition:
      "Statistical methods that identify data values, patterns, or records that deviate significantly from expected norms, potentially indicating errors or unusual clinical situations.",
    systemUsage:
      "Applied to numeric lab values, extraction confidence distributions, and mapping statistics. Outliers are flagged for review — they may be errors or clinically significant.",
    clinicianNote:
      "An outlier might be a data entry error (potassium of 40) or a genuine clinical finding (extremely elevated troponin). The system flags both for your judgment.",
    category: "Data Quality",
  },
  // NLP & Extraction (additional)
  {
    term: "Abbreviation Expansion",
    definition:
      "The resolution of clinical abbreviations and acronyms to their full forms, using context to disambiguate abbreviations that have multiple possible meanings.",
    systemUsage:
      "Applied during preprocessing. A clinical abbreviation dictionary combined with contextual rules expands ambiguous abbreviations (e.g., 'SOB' → 'shortness of breath' vs. other meanings).",
    clinicianNote:
      "Clinical notes are full of abbreviations. The system expands them automatically to ensure 'SOB' is correctly understood as 'shortness of breath' in the right context.",
    category: "NLP & Extraction",
  },
  {
    term: "Coreference Resolution",
    definition:
      "The NLP task of determining when different expressions in text refer to the same entity — for example, recognizing that 'the patient', 'she', and 'Mrs. Smith' are the same person.",
    systemUsage:
      "Used to link mentions across sentences and paragraphs. Ensures that attributes described in one sentence are correctly associated with entities mentioned in another.",
    clinicianNote:
      "Without coreference resolution, the system might not connect 'she was prescribed metformin' back to the patient named earlier in the note. This step ties everything together.",
    category: "NLP & Extraction",
  },
  {
    term: "Pre-trained Language Model",
    definition:
      "A large neural network (such as a transformer) trained on massive text corpora, then fine-tuned on clinical data for domain-specific NLP tasks.",
    systemUsage:
      "The ML extraction pipeline uses clinical transformer models (ClinicalBERT, ModernBERT) fine-tuned for NER, assertion detection, and relation extraction on clinical notes.",
    clinicianNote:
      "Pre-trained models bring general language understanding that is then specialized for clinical text. This combination produces better accuracy than either approach alone.",
    category: "NLP & Extraction",
  },
  {
    term: "Active Learning",
    definition:
      "A machine learning strategy where the model identifies the most informative unlabeled examples and requests human annotation for those specific cases to improve efficiently.",
    systemUsage:
      "When new document types or concept domains are encountered, the system identifies high-uncertainty extractions and routes them to expert annotators for labeling, maximizing training data value.",
    clinicianNote:
      "Active learning means the system gets smarter by asking clinicians to review the cases it is most uncertain about, rather than requiring annotation of everything.",
    category: "NLP & Extraction",
  },
  {
    term: "Post-processing Rules",
    definition:
      "A set of deterministic cleanup and validation rules applied after ML extraction to correct common errors, enforce domain constraints, and normalize output format.",
    systemUsage:
      "Applied after ML NER to fix known error patterns — merging split mentions, removing false positives from headers/footers, and enforcing vocabulary constraints.",
    clinicianNote:
      "Post-processing catches and fixes predictable ML errors. For example, it ensures medication dosages stay attached to their drug names even if the model split them apart.",
    category: "NLP & Extraction",
  },
  // Clinical Workflows
  {
    term: "Clinical Decision Support",
    definition:
      "Technology that provides clinicians with knowledge, person-specific information, and recommendations at the point of care to enhance clinical decision-making.",
    systemUsage:
      "The CDS engine combines knowledge graph queries, clinical calculators, drug interaction checks, and guideline matching to generate context-aware recommendations via API or CDS Hooks.",
    clinicianNote:
      "CDS surfaces relevant information when you need it — drug interaction warnings during prescribing, clinical calculators during assessment, and guideline reminders during treatment planning.",
    category: "Clinical Workflows",
  },
  {
    term: "Clinical Calculator",
    definition:
      "A validated scoring tool that computes risk scores, severity indices, or clinical classifications based on structured patient data inputs.",
    systemUsage:
      "Over 50 validated calculators are available (CHA2DS2-VASc, MELD, Wells Score, etc.). Auto-populated from knowledge graph data when available, with manual input fallback.",
    clinicianNote:
      "Clinical calculators help quantify risk and guide treatment decisions. The system can auto-fill calculator inputs from available patient data, saving you data entry time.",
    category: "Clinical Workflows",
  },
  {
    term: "Cohort Definition",
    definition:
      "A set of inclusion and exclusion criteria that identifies a specific patient population for research, quality measurement, or clinical trial eligibility screening.",
    systemUsage:
      "Built using value sets and concept hierarchies. Cohort queries run against the OMOP-mapped patient data to identify qualifying patients. Supports temporal logic and event sequencing.",
    clinicianNote:
      "Cohort definitions let you find patients matching specific criteria — for example, all patients with heart failure on ACE inhibitors who had an ER visit in the past 90 days.",
    category: "Clinical Workflows",
  },
  {
    term: "Quality Measure",
    definition:
      "A standardized metric (often from CMS, NQF, or HEDIS) that evaluates the quality of healthcare delivery against evidence-based benchmarks.",
    systemUsage:
      "Quality measures are defined using value sets and computed against normalized patient data. Results are tracked over time and exportable for regulatory reporting.",
    clinicianNote:
      "Quality measures tell you how well care meets established standards. The system computes these automatically from your patient data, reducing manual chart abstraction burden.",
    category: "Clinical Workflows",
  },
  {
    term: "Care Gap",
    definition:
      "An identified discrepancy between recommended clinical care (per guidelines or quality measures) and the care a patient has actually received.",
    systemUsage:
      "Detected by comparing patient data against active quality measures and clinical guidelines. Care gaps are surfaced as actionable items in the provider dashboard.",
    clinicianNote:
      "Care gaps highlight opportunities to improve care — for example, a diabetic patient overdue for an A1c test or a patient missing a recommended cancer screening.",
    category: "Clinical Workflows",
  },
  {
    term: "Order Set",
    definition:
      "A pre-defined collection of clinical orders (medications, labs, imaging, referrals) grouped by clinical scenario to standardize and streamline the ordering process.",
    systemUsage:
      "The system can suggest relevant order sets based on diagnoses identified in the knowledge graph, helping clinicians quickly initiate evidence-based care pathways.",
    clinicianNote:
      "Order sets reduce cognitive load and variability by bundling standard orders for common clinical scenarios, so you can initiate comprehensive care with fewer clicks.",
    category: "Clinical Workflows",
  },
  {
    term: "Clinical Pathway",
    definition:
      "A structured, evidence-based plan that maps the expected course of treatment for a specific condition, including timelines, milestones, and decision points.",
    systemUsage:
      "Pathways are modeled in the guideline engine. Patient progress along a pathway is tracked via knowledge graph events, with alerts when patients deviate from expected trajectories.",
    clinicianNote:
      "Clinical pathways give you a roadmap for managing specific conditions. The system tracks where your patient is on the pathway and alerts you to deviations or upcoming milestones.",
    category: "Clinical Workflows",
  },
  // Privacy & Compliance
  {
    term: "De-identification",
    definition:
      "The process of removing or obscuring protected health information (PHI) from clinical data so that individuals cannot be identified from the remaining information.",
    systemUsage:
      "Applied before data is used for research, analytics, or model training. Supports Safe Harbor and Expert Determination methods per HIPAA guidelines. PHI patterns are detected and redacted.",
    clinicianNote:
      "De-identification protects patient privacy when data is used beyond direct care. The system removes names, dates, IDs, and other identifying information automatically.",
    category: "Privacy & Compliance",
  },
  {
    term: "HIPAA",
    definition:
      "The Health Insurance Portability and Accountability Act — U.S. federal law that establishes national standards for protecting the privacy and security of health information.",
    systemUsage:
      "All system components are designed with HIPAA compliance: encryption at rest and in transit, access controls, audit logging, minimum necessary access, and breach notification capabilities.",
    clinicianNote:
      "HIPAA governs how patient data must be protected. The platform enforces these requirements automatically so you can focus on care rather than compliance mechanics.",
    category: "Privacy & Compliance",
  },
  {
    term: "Minimum Necessary",
    definition:
      "The HIPAA principle that access to protected health information should be limited to the minimum amount needed to accomplish the intended purpose.",
    systemUsage:
      "Enforced through role-based access controls and API scoping. Users and services only receive the data elements required for their specific function or query.",
    clinicianNote:
      "You see the patient data relevant to your role and current task. The system automatically filters out information that is not needed for your specific clinical workflow.",
    category: "Privacy & Compliance",
  },
  {
    term: "Access Control List",
    definition:
      "A security mechanism that defines which users, roles, or services are permitted to view, modify, or process specific data resources within the system.",
    systemUsage:
      "Implemented at API, database, and service levels. ACLs combine role-based (RBAC) and attribute-based (ABAC) policies. All access decisions are logged for audit purposes.",
    clinicianNote:
      "Access controls ensure only authorized personnel can see patient data. Your access level is determined by your role and the specific patients in your care.",
    category: "Privacy & Compliance",
  },
  {
    term: "Encryption at Rest",
    definition:
      "The protection of stored data using cryptographic algorithms, ensuring that data on disk, in databases, or in backups cannot be read without the proper decryption keys.",
    systemUsage:
      "All patient data in PostgreSQL, Redis, and Neo4j is encrypted at rest using AES-256. Encryption keys are managed via the infrastructure's key management service.",
    clinicianNote:
      "Even if someone gained physical access to the storage systems, they could not read patient data without the encryption keys. This protects data at every layer.",
    category: "Privacy & Compliance",
  },
  {
    term: "Breach Notification",
    definition:
      "The process and timeline requirements for notifying affected individuals, regulators, and media when a security incident results in unauthorized access to protected health information.",
    systemUsage:
      "The audit and alerting system detects potential breach indicators (unusual access patterns, bulk data exports) and triggers the incident response workflow with configurable escalation rules.",
    clinicianNote:
      "If a potential data breach is detected, the system automatically initiates the notification process required by HIPAA, helping ensure timely and compliant response.",
    category: "Privacy & Compliance",
  },
  {
    term: "Data Use Agreement",
    definition:
      "A legal contract governing how de-identified or limited data sets may be used, shared, and protected by the receiving party.",
    systemUsage:
      "DUA metadata is attached to data exports and research datasets. The system tracks which agreements cover which data and enforces expiration and usage constraints.",
    clinicianNote:
      "Data Use Agreements ensure that when patient data is shared for research or quality improvement, there are clear rules about how it can and cannot be used.",
    category: "Privacy & Compliance",
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

  const allCategories = Object.keys(CATEGORY_META) as Category[];

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const t of GLOSSARY_TERMS) {
      counts[t.category] = (counts[t.category] || 0) + 1;
    }
    return counts;
  }, []);

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
    <div className="space-y-8 p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="rounded-xl border bg-card px-8 py-8">
        <div className="flex items-center gap-3 mb-3">
          <div className="flex items-center justify-center h-10 w-10 rounded-lg bg-primary/10">
            <BookOpen className="h-5 w-5 text-primary" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight">
            Clinical AI Glossary
          </h1>
        </div>
        <p className="text-muted-foreground text-lg max-w-2xl">
          Reference guide for confidence, evidence, safety, and data quality
          concepts used throughout the Sulci platform.
        </p>
        <div className="flex items-center gap-6 mt-5 text-sm text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <BookOpen className="h-4 w-4" />
            {GLOSSARY_TERMS.length} terms
          </span>
          <span className="flex items-center gap-1.5">
            <Database className="h-4 w-4" />
            {allCategories.length} categories
          </span>
        </div>
      </div>

      {/* Category overview cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {allCategories.map((cat) => {
          const meta = CATEGORY_META[cat];
          const Icon = meta.icon;
          const isSelected = selectedCategory === cat;
          return (
            <button
              key={cat}
              onClick={() =>
                setSelectedCategory(isSelected ? "All" : cat)
              }
              className={`group relative flex flex-col items-start gap-2 rounded-lg border p-4 text-left transition-all ${
                isSelected
                  ? `${meta.bg} border-current ring-1 ring-current/20 ${meta.iconColor}`
                  : "border-border hover:border-border/80 hover:shadow-sm"
              }`}
            >
              <div
                className={`flex items-center justify-center h-8 w-8 rounded-md ${
                  isSelected ? meta.bg : "bg-muted"
                }`}
              >
                <Icon
                  className={`h-4 w-4 ${
                    isSelected
                      ? meta.iconColor
                      : "text-muted-foreground group-hover:text-foreground"
                  }`}
                />
              </div>
              <div>
                <p
                  className={`text-sm font-medium leading-tight ${
                    isSelected ? "" : "text-foreground"
                  }`}
                >
                  {cat}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {categoryCounts[cat] || 0} terms
                </p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Search bar */}
      <div className="sticky top-0 z-10 bg-background/95 backdrop-blur-sm pb-4 pt-1 -mx-6 px-6 border-b border-border/50">
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search 80 terms..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-10"
            />
          </div>
          {selectedCategory !== "All" && (
            <Badge
              variant="outline"
              className={`${CATEGORY_META[selectedCategory as Category].badge} cursor-pointer`}
              onClick={() => setSelectedCategory("All")}
            >
              {selectedCategory} &times;
            </Badge>
          )}
          <span className="text-sm text-muted-foreground ml-auto">
            {filteredTerms.length} result{filteredTerms.length !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* Terms by category */}
      <div className="space-y-10">
        {Object.entries(groupedTerms).map(([category, terms]) => {
          const meta = CATEGORY_META[category as Category];
          const Icon = meta.icon;
          return (
            <section key={category}>
              {/* Category header */}
              <div className="flex items-center gap-3 mb-4">
                <div
                  className={`flex items-center justify-center h-9 w-9 rounded-lg ${meta.bg}`}
                >
                  <Icon className={`h-5 w-5 ${meta.iconColor}`} />
                </div>
                <div>
                  <h2 className="text-lg font-semibold leading-none">
                    {category}
                  </h2>
                  <p className="text-xs text-muted-foreground mt-1">
                    {terms.length} term{terms.length !== 1 ? "s" : ""}
                  </p>
                </div>
              </div>

              {/* Term cards */}
              <div className="grid gap-2">
                {terms.map((t) => {
                  const isExpanded = expandedTerms.has(t.term);
                  return (
                    <Card
                      key={t.term}
                      className={`border-l-4 ${meta.border} transition-all ${meta.cardBg} ${
                        isExpanded ? "shadow-md" : "hover:shadow-sm"
                      }`}
                    >
                      <CardHeader
                        className="cursor-pointer py-3.5 px-5"
                        onClick={() => toggleTerm(t.term)}
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex items-start gap-2.5 min-w-0">
                            <div className="mt-0.5 shrink-0">
                              {isExpanded ? (
                                <ChevronDown className="h-4 w-4 text-muted-foreground" />
                              ) : (
                                <ChevronRight className="h-4 w-4 text-muted-foreground" />
                              )}
                            </div>
                            <div className="min-w-0">
                              <CardTitle className="text-[15px] font-semibold leading-snug">
                                {t.term}
                              </CardTitle>
                              <CardDescription className="mt-1 text-[13px] leading-relaxed">
                                {t.definition}
                              </CardDescription>
                            </div>
                          </div>
                          <Badge
                            variant="outline"
                            className={`shrink-0 text-[11px] ${meta.badge}`}
                          >
                            {t.category}
                          </Badge>
                        </div>
                      </CardHeader>
                      {isExpanded && (
                        <CardContent className="pt-0 pb-5 px-5">
                          <Separator className="mb-4" />
                          <div className="ml-6 grid gap-4 sm:grid-cols-2">
                            <div className="rounded-lg bg-muted/50 p-4">
                              <div className="flex items-center gap-2 mb-2">
                                <Monitor className="h-4 w-4 text-muted-foreground" />
                                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                  System Usage
                                </p>
                              </div>
                              <p className="text-sm leading-relaxed">
                                {t.systemUsage}
                              </p>
                            </div>
                            <div className={`rounded-lg ${meta.bg} p-4`}>
                              <div className="flex items-center gap-2 mb-2">
                                <Stethoscope
                                  className={`h-4 w-4 ${meta.iconColor}`}
                                />
                                <p
                                  className={`text-xs font-semibold uppercase tracking-wider ${meta.iconColor}`}
                                >
                                  Clinician Note
                                </p>
                              </div>
                              <p className="text-sm leading-relaxed">
                                {t.clinicianNote}
                              </p>
                            </div>
                          </div>
                        </CardContent>
                      )}
                    </Card>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>

      {filteredTerms.length === 0 && (
        <Card className="border-dashed">
          <CardContent className="py-16 text-center">
            <Search className="h-10 w-10 text-muted-foreground/50 mx-auto mb-4" />
            <p className="text-muted-foreground font-medium">
              No terms match your search
            </p>
            <p className="text-sm text-muted-foreground/70 mt-1">
              Try a different query or clear the category filter.
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={() => {
                setSearch("");
                setSelectedCategory("All");
              }}
            >
              Clear filters
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
