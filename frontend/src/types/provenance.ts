/**
 * TypeScript types for provenance tracking, reasoning chains,
 * and citation data structures.
 */

export interface ReasoningStep {
  step: number;
  type: "kg_retrieval" | "rag_search" | "llm_inference" | "guideline_match" | "policy_check";
  summary: string;
  duration_ms: number;
  confidence_contribution?: number;
  details: Record<string, unknown>;
}

export interface EntityProvenance {
  text: string;
  entity_type: string;
  confidence: number;
  note_id: string;
  extraction_method?: string;
  source_document_id?: string;
  extracted_text?: string;
  confidence_level?: "high" | "medium" | "low" | "uncertain";
}

export interface GuidelineCitation {
  guideline_number: number;
  section_id: string;
  guideline: string;
  section_title: string;
  recommendation_text: string;
  evidence_grade: string;
  recommendation_level: string;
  relevance_score: number;
  match_reasons: string[];
}

export interface PolicyCitation {
  policy_number: number;
  policy_id: string;
  policy_name: string;
  section_id: string;
  section_title: string;
  relevance_score: number;
}

export interface ProvenanceChain {
  query_id: string;
  patient_id: string | null;
  steps: ReasoningStep[];
  total_steps: number;
  total_duration_ms: number;
  total_confidence: number;
}

export interface ConfidenceBreakdown {
  overall: number;
  kg_contribution: number;
  rag_contribution: number;
  llm_contribution: number;
  evidence_contribution: number;
  guideline_boost: number;
}

export interface HybridQueryResponseWithProvenance {
  question: string;
  answer: string;
  confidence: number;
  sources: string[];
  entities_found: EntityProvenance[];
  evidence: EvidenceSource[];
  knowledge_graph_paths: Record<string, unknown>[];
  reasoning: string | null;
  guideline_citations: GuidelineCitation[];
  query_id: string | null;
  reasoning_chain: ReasoningStep[];
  entity_provenance: EntityProvenance[];
  policy_citations: PolicyCitation[];
  provenance_url: string | null;
}

export interface EvidenceSource {
  note_id: string;
  note_type: string;
  note_date: string;
  excerpt: string;
  relevance_score: number;
}

export interface FactLineage {
  patient_id: string;
  node: {
    id: string;
    label: string;
    node_type: string;
    omop_concept_id: number | null;
  };
  provenance_chain: {
    entity_type: string;
    entity_id: string;
    provenance_records: ProvenanceRecordDetail[];
  };
  hop_decay: number;
}

export interface ProvenanceRecordDetail {
  id: string;
  extraction_method: string;
  confidence_level: string;
  confidence_score: number | null;
  effective_confidence?: number;
  extracted_text: string | null;
  source_document_id: string | null;
  source_section: string | null;
  source_span_start: number | null;
  source_span_end: number | null;
  extraction_model: string | null;
  extraction_timestamp: string | null;
  metadata: Record<string, unknown> | null;
  source_document?: {
    id: string;
    note_type: string;
    note_date: string;
    text_length: number;
  };
}
