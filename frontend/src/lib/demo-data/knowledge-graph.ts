import type { PatientGraph, GraphNode, GraphEdge } from "@/lib/api";

const ts = "2026-02-01T00:00:00Z";

// ---------- pat-001: John Smith (12 nodes, 15 edges) ----------

const pat001Nodes: GraphNode[] = [
  { id: "node-001", patient_id: "pat-001", node_type: "patient", omop_concept_id: null, label: "John Smith", properties: { gender: "male", birth_date: "1962-03-15" }, created_at: ts },
  { id: "node-002", patient_id: "pat-001", node_type: "condition", omop_concept_id: 4193704, label: "Type 2 Diabetes Mellitus", properties: { concept_id: "4193704", vocabulary_id: "SNOMED" }, created_at: ts },
  { id: "node-003", patient_id: "pat-001", node_type: "condition", omop_concept_id: 320128, label: "Essential Hypertension", properties: { concept_id: "320128", vocabulary_id: "SNOMED" }, created_at: ts },
  { id: "node-004", patient_id: "pat-001", node_type: "condition", omop_concept_id: 4271564, label: "Peripheral Neuropathy", properties: { concept_id: "4271564", vocabulary_id: "SNOMED" }, created_at: ts },
  { id: "node-005", patient_id: "pat-001", node_type: "medication", omop_concept_id: 1503297, label: "Metformin 1000mg", properties: { concept_id: "1503297", vocabulary_id: "RxNorm", dose: "1000mg BID" }, created_at: ts },
  { id: "node-006", patient_id: "pat-001", node_type: "medication", omop_concept_id: 1308216, label: "Lisinopril 20mg", properties: { concept_id: "1308216", vocabulary_id: "RxNorm", dose: "20mg daily" }, created_at: ts },
  { id: "node-007", patient_id: "pat-001", node_type: "medication", omop_concept_id: 1596977, label: "Insulin Glargine", properties: { concept_id: "1596977", vocabulary_id: "RxNorm", dose: "18 units nightly" }, created_at: ts },
  { id: "node-008", patient_id: "pat-001", node_type: "lab_result", omop_concept_id: 3004410, label: "A1c 8.2%", properties: { concept_id: "3004410", value: "8.2", unit: "%" }, created_at: ts },
  { id: "node-009", patient_id: "pat-001", node_type: "lab_result", omop_concept_id: 3016723, label: "Creatinine 1.1", properties: { concept_id: "3016723", value: "1.1", unit: "mg/dL" }, created_at: ts },
  { id: "node-010", patient_id: "pat-001", node_type: "lab_result", omop_concept_id: 3030354, label: "GFR 68", properties: { concept_id: "3030354", value: "68", unit: "mL/min" }, created_at: ts },
  { id: "node-011", patient_id: "pat-001", node_type: "lab_result", omop_concept_id: 3004249, label: "BP 142/88", properties: { concept_id: "3004249", value: "142/88", unit: "mmHg" }, created_at: ts },
  { id: "node-012", patient_id: "pat-001", node_type: "lab_result", omop_concept_id: 3023103, label: "K 4.2", properties: { concept_id: "3023103", value: "4.2", unit: "mEq/L" }, created_at: ts },
];

const edgeBase = { fact_id: null, event_date: null, valid_from: null, valid_to: null, recorded_at: null, source_document_date: null, temporality: "current" as const, temporal_order: null, temporal_confidence: null, created_at: ts };

const pat001Edges: GraphEdge[] = [
  { id: "edge-001", patient_id: "pat-001", source_node_id: "node-001", target_node_id: "node-002", edge_type: "has_condition", properties: {}, ...edgeBase },
  { id: "edge-002", patient_id: "pat-001", source_node_id: "node-001", target_node_id: "node-003", edge_type: "has_condition", properties: {}, ...edgeBase },
  { id: "edge-003", patient_id: "pat-001", source_node_id: "node-001", target_node_id: "node-004", edge_type: "has_condition", properties: {}, ...edgeBase },
  { id: "edge-004", patient_id: "pat-001", source_node_id: "node-001", target_node_id: "node-005", edge_type: "takes_medication", properties: {}, ...edgeBase },
  { id: "edge-005", patient_id: "pat-001", source_node_id: "node-001", target_node_id: "node-006", edge_type: "takes_medication", properties: {}, ...edgeBase },
  { id: "edge-006", patient_id: "pat-001", source_node_id: "node-001", target_node_id: "node-007", edge_type: "takes_medication", properties: {}, ...edgeBase },
  { id: "edge-007", patient_id: "pat-001", source_node_id: "node-001", target_node_id: "node-008", edge_type: "has_lab_result", properties: {}, ...edgeBase },
  { id: "edge-008", patient_id: "pat-001", source_node_id: "node-001", target_node_id: "node-009", edge_type: "has_lab_result", properties: {}, ...edgeBase },
  { id: "edge-009", patient_id: "pat-001", source_node_id: "node-001", target_node_id: "node-010", edge_type: "has_lab_result", properties: {}, ...edgeBase },
  { id: "edge-010", patient_id: "pat-001", source_node_id: "node-001", target_node_id: "node-011", edge_type: "has_lab_result", properties: {}, ...edgeBase },
  { id: "edge-011", patient_id: "pat-001", source_node_id: "node-001", target_node_id: "node-012", edge_type: "has_lab_result", properties: {}, ...edgeBase },
  { id: "edge-012", patient_id: "pat-001", source_node_id: "node-005", target_node_id: "node-002", edge_type: "treats", properties: {}, ...edgeBase },
  { id: "edge-013", patient_id: "pat-001", source_node_id: "node-007", target_node_id: "node-002", edge_type: "treats", properties: {}, ...edgeBase },
  { id: "edge-014", patient_id: "pat-001", source_node_id: "node-006", target_node_id: "node-003", edge_type: "treats", properties: {}, ...edgeBase },
  { id: "edge-015", patient_id: "pat-001", source_node_id: "node-002", target_node_id: "node-004", edge_type: "interacts_with", properties: { relationship: "complication" }, ...edgeBase },
];

// ---------- pat-002: Maria Garcia (6 nodes, 7 edges) ----------

const pat002Nodes: GraphNode[] = [
  { id: "node-020", patient_id: "pat-002", node_type: "patient", omop_concept_id: null, label: "Maria Garcia", properties: { gender: "female", birth_date: "1985-07-22" }, created_at: ts },
  { id: "node-021", patient_id: "pat-002", node_type: "condition", omop_concept_id: 4152280, label: "Major Depressive Disorder", properties: { concept_id: "4152280", vocabulary_id: "SNOMED" }, created_at: ts },
  { id: "node-022", patient_id: "pat-002", node_type: "condition", omop_concept_id: 441542, label: "Generalized Anxiety Disorder", properties: { concept_id: "441542", vocabulary_id: "SNOMED" }, created_at: ts },
  { id: "node-023", patient_id: "pat-002", node_type: "medication", omop_concept_id: 1000048, label: "Sertraline 100mg", properties: { concept_id: "1000048", vocabulary_id: "RxNorm", dose: "100mg daily" }, created_at: ts },
  { id: "node-024", patient_id: "pat-002", node_type: "lab_result", omop_concept_id: 40758891, label: "PHQ-9: 14", properties: { concept_id: "40758891", value: "14" }, created_at: ts },
  { id: "node-025", patient_id: "pat-002", node_type: "lab_result", omop_concept_id: 40758893, label: "GAD-7: 8", properties: { concept_id: "40758893", value: "8" }, created_at: ts },
];

const pat002Edges: GraphEdge[] = [
  { id: "edge-020", patient_id: "pat-002", source_node_id: "node-020", target_node_id: "node-021", edge_type: "has_condition", properties: {}, ...edgeBase },
  { id: "edge-021", patient_id: "pat-002", source_node_id: "node-020", target_node_id: "node-022", edge_type: "has_condition", properties: {}, ...edgeBase },
  { id: "edge-022", patient_id: "pat-002", source_node_id: "node-020", target_node_id: "node-023", edge_type: "takes_medication", properties: {}, ...edgeBase },
  { id: "edge-023", patient_id: "pat-002", source_node_id: "node-020", target_node_id: "node-024", edge_type: "has_lab_result", properties: {}, ...edgeBase },
  { id: "edge-024", patient_id: "pat-002", source_node_id: "node-020", target_node_id: "node-025", edge_type: "has_lab_result", properties: {}, ...edgeBase },
  { id: "edge-025", patient_id: "pat-002", source_node_id: "node-023", target_node_id: "node-021", edge_type: "treats", properties: {}, ...edgeBase },
  { id: "edge-026", patient_id: "pat-002", source_node_id: "node-021", target_node_id: "node-022", edge_type: "interacts_with", properties: { relationship: "comorbid" }, ...edgeBase },
];

// ---------- pat-003: Mary Johnson (10 nodes, 13 edges) ----------

const pat003Nodes: GraphNode[] = [
  { id: "node-030", patient_id: "pat-003", node_type: "patient", omop_concept_id: null, label: "Mary Johnson", properties: { gender: "female", birth_date: "1950-11-08" }, created_at: ts },
  { id: "node-031", patient_id: "pat-003", node_type: "condition", omop_concept_id: 316139, label: "Heart Failure", properties: { concept_id: "316139", vocabulary_id: "SNOMED", nyha_class: "III" }, created_at: ts },
  { id: "node-032", patient_id: "pat-003", node_type: "condition", omop_concept_id: 313217, label: "Atrial Fibrillation", properties: { concept_id: "313217", vocabulary_id: "SNOMED" }, created_at: ts },
  { id: "node-033", patient_id: "pat-003", node_type: "condition", omop_concept_id: 314378, label: "Mitral Regurgitation", properties: { concept_id: "314378", vocabulary_id: "SNOMED", severity: "moderate" }, created_at: ts },
  { id: "node-034", patient_id: "pat-003", node_type: "medication", omop_concept_id: 1395058, label: "Furosemide 40mg", properties: { concept_id: "1395058", vocabulary_id: "RxNorm", dose: "40mg daily" }, created_at: ts },
  { id: "node-035", patient_id: "pat-003", node_type: "medication", omop_concept_id: 1310149, label: "Warfarin 5mg", properties: { concept_id: "1310149", vocabulary_id: "RxNorm", dose: "5mg daily" }, created_at: ts },
  { id: "node-036", patient_id: "pat-003", node_type: "medication", omop_concept_id: 1307046, label: "Metoprolol 50mg", properties: { concept_id: "1307046", vocabulary_id: "RxNorm", dose: "50mg BID" }, created_at: ts },
  { id: "node-037", patient_id: "pat-003", node_type: "lab_result", omop_concept_id: 3037121, label: "EF 35%", properties: { concept_id: "3037121", value: "35", unit: "%" }, created_at: ts },
  { id: "node-038", patient_id: "pat-003", node_type: "lab_result", omop_concept_id: 3022217, label: "BNP 1847", properties: { concept_id: "3022217", value: "1847", unit: "pg/mL" }, created_at: ts },
  { id: "node-039", patient_id: "pat-003", node_type: "lab_result", omop_concept_id: 3010813, label: "INR 2.3", properties: { concept_id: "3010813", value: "2.3" }, created_at: ts },
];

const pat003Edges: GraphEdge[] = [
  { id: "edge-030", patient_id: "pat-003", source_node_id: "node-030", target_node_id: "node-031", edge_type: "has_condition", properties: {}, ...edgeBase },
  { id: "edge-031", patient_id: "pat-003", source_node_id: "node-030", target_node_id: "node-032", edge_type: "has_condition", properties: {}, ...edgeBase },
  { id: "edge-032", patient_id: "pat-003", source_node_id: "node-030", target_node_id: "node-033", edge_type: "has_condition", properties: {}, ...edgeBase },
  { id: "edge-033", patient_id: "pat-003", source_node_id: "node-030", target_node_id: "node-034", edge_type: "takes_medication", properties: {}, ...edgeBase },
  { id: "edge-034", patient_id: "pat-003", source_node_id: "node-030", target_node_id: "node-035", edge_type: "takes_medication", properties: {}, ...edgeBase },
  { id: "edge-035", patient_id: "pat-003", source_node_id: "node-030", target_node_id: "node-036", edge_type: "takes_medication", properties: {}, ...edgeBase },
  { id: "edge-036", patient_id: "pat-003", source_node_id: "node-030", target_node_id: "node-037", edge_type: "has_lab_result", properties: {}, ...edgeBase },
  { id: "edge-037", patient_id: "pat-003", source_node_id: "node-030", target_node_id: "node-038", edge_type: "has_lab_result", properties: {}, ...edgeBase },
  { id: "edge-038", patient_id: "pat-003", source_node_id: "node-030", target_node_id: "node-039", edge_type: "has_lab_result", properties: {}, ...edgeBase },
  { id: "edge-039", patient_id: "pat-003", source_node_id: "node-034", target_node_id: "node-031", edge_type: "treats", properties: {}, ...edgeBase },
  { id: "edge-040", patient_id: "pat-003", source_node_id: "node-036", target_node_id: "node-032", edge_type: "treats", properties: {}, ...edgeBase },
  { id: "edge-041", patient_id: "pat-003", source_node_id: "node-035", target_node_id: "node-032", edge_type: "treats", properties: { indication: "anticoagulation" }, ...edgeBase },
  { id: "edge-042", patient_id: "pat-003", source_node_id: "node-031", target_node_id: "node-033", edge_type: "interacts_with", properties: { relationship: "structural" }, ...edgeBase },
];

// ---------- pat-004: Robert Williams (8 nodes, 10 edges) ----------

const pat004Nodes: GraphNode[] = [
  { id: "node-040", patient_id: "pat-004", node_type: "patient", omop_concept_id: null, label: "Robert Williams", properties: { gender: "male", birth_date: "1958-01-30" }, created_at: ts },
  { id: "node-041", patient_id: "pat-004", node_type: "condition", omop_concept_id: 443611, label: "CKD Stage 4", properties: { concept_id: "443611", vocabulary_id: "SNOMED" }, created_at: ts },
  { id: "node-042", patient_id: "pat-004", node_type: "condition", omop_concept_id: 4144746, label: "Anemia of Chronic Disease", properties: { concept_id: "4144746", vocabulary_id: "SNOMED" }, created_at: ts },
  { id: "node-043", patient_id: "pat-004", node_type: "medication", omop_concept_id: 1304919, label: "Epoetin Alfa", properties: { concept_id: "1304919", vocabulary_id: "RxNorm" }, created_at: ts },
  { id: "node-044", patient_id: "pat-004", node_type: "medication", omop_concept_id: 1305058, label: "Sodium Bicarbonate", properties: { concept_id: "1305058", vocabulary_id: "RxNorm" }, created_at: ts },
  { id: "node-045", patient_id: "pat-004", node_type: "medication", omop_concept_id: 1305455, label: "Calcitriol", properties: { concept_id: "1305455", vocabulary_id: "RxNorm" }, created_at: ts },
  { id: "node-046", patient_id: "pat-004", node_type: "lab_result", omop_concept_id: 3030354, label: "GFR 22", properties: { concept_id: "3030354", value: "22", unit: "mL/min" }, created_at: ts },
  { id: "node-047", patient_id: "pat-004", node_type: "lab_result", omop_concept_id: 3000963, label: "Hgb 9.8", properties: { concept_id: "3000963", value: "9.8", unit: "g/dL" }, created_at: ts },
];

const pat004Edges: GraphEdge[] = [
  { id: "edge-040", patient_id: "pat-004", source_node_id: "node-040", target_node_id: "node-041", edge_type: "has_condition", properties: {}, ...edgeBase },
  { id: "edge-041", patient_id: "pat-004", source_node_id: "node-040", target_node_id: "node-042", edge_type: "has_condition", properties: {}, ...edgeBase },
  { id: "edge-042", patient_id: "pat-004", source_node_id: "node-040", target_node_id: "node-043", edge_type: "takes_medication", properties: {}, ...edgeBase },
  { id: "edge-043", patient_id: "pat-004", source_node_id: "node-040", target_node_id: "node-044", edge_type: "takes_medication", properties: {}, ...edgeBase },
  { id: "edge-044", patient_id: "pat-004", source_node_id: "node-040", target_node_id: "node-045", edge_type: "takes_medication", properties: {}, ...edgeBase },
  { id: "edge-045", patient_id: "pat-004", source_node_id: "node-040", target_node_id: "node-046", edge_type: "has_lab_result", properties: {}, ...edgeBase },
  { id: "edge-046", patient_id: "pat-004", source_node_id: "node-040", target_node_id: "node-047", edge_type: "has_lab_result", properties: {}, ...edgeBase },
  { id: "edge-047", patient_id: "pat-004", source_node_id: "node-043", target_node_id: "node-042", edge_type: "treats", properties: {}, ...edgeBase },
  { id: "edge-048", patient_id: "pat-004", source_node_id: "node-044", target_node_id: "node-041", edge_type: "treats", properties: { indication: "metabolic acidosis" }, ...edgeBase },
  { id: "edge-049", patient_id: "pat-004", source_node_id: "node-041", target_node_id: "node-042", edge_type: "interacts_with", properties: { relationship: "complication" }, ...edgeBase },
];

// ---------- pat-005: Sarah Chen (5 nodes, 6 edges) ----------

const pat005Nodes: GraphNode[] = [
  { id: "node-050", patient_id: "pat-005", node_type: "patient", omop_concept_id: null, label: "Sarah Chen", properties: { gender: "female", birth_date: "1992-09-12" }, created_at: ts },
  { id: "node-051", patient_id: "pat-005", node_type: "condition", omop_concept_id: 4145356, label: "Persistent Asthma, Moderate", properties: { concept_id: "4145356", vocabulary_id: "SNOMED" }, created_at: ts },
  { id: "node-052", patient_id: "pat-005", node_type: "medication", omop_concept_id: 1154343, label: "Albuterol HFA", properties: { concept_id: "1154343", vocabulary_id: "RxNorm", role: "rescue" }, created_at: ts },
  { id: "node-053", patient_id: "pat-005", node_type: "medication", omop_concept_id: 1149196, label: "Fluticasone/Salmeterol", properties: { concept_id: "1149196", vocabulary_id: "RxNorm", role: "maintenance" }, created_at: ts },
  { id: "node-054", patient_id: "pat-005", node_type: "lab_result", omop_concept_id: 3024653, label: "FEV1 78%", properties: { concept_id: "3024653", value: "78", unit: "%" }, created_at: ts },
];

const pat005Edges: GraphEdge[] = [
  { id: "edge-050", patient_id: "pat-005", source_node_id: "node-050", target_node_id: "node-051", edge_type: "has_condition", properties: {}, ...edgeBase },
  { id: "edge-051", patient_id: "pat-005", source_node_id: "node-050", target_node_id: "node-052", edge_type: "takes_medication", properties: {}, ...edgeBase },
  { id: "edge-052", patient_id: "pat-005", source_node_id: "node-050", target_node_id: "node-053", edge_type: "takes_medication", properties: {}, ...edgeBase },
  { id: "edge-053", patient_id: "pat-005", source_node_id: "node-050", target_node_id: "node-054", edge_type: "has_lab_result", properties: {}, ...edgeBase },
  { id: "edge-054", patient_id: "pat-005", source_node_id: "node-052", target_node_id: "node-051", edge_type: "treats", properties: { role: "rescue" }, ...edgeBase },
  { id: "edge-055", patient_id: "pat-005", source_node_id: "node-053", target_node_id: "node-051", edge_type: "treats", properties: { role: "maintenance" }, ...edgeBase },
];

// ---------- Exported per-patient graphs ----------

export const DEMO_PATIENT_GRAPHS: Record<string, PatientGraph> = {
  "pat-001": { patient_id: "pat-001", nodes: pat001Nodes, edges: pat001Edges, node_count: pat001Nodes.length, edge_count: pat001Edges.length },
  "pat-002": { patient_id: "pat-002", nodes: pat002Nodes, edges: pat002Edges, node_count: pat002Nodes.length, edge_count: pat002Edges.length },
  "pat-003": { patient_id: "pat-003", nodes: pat003Nodes, edges: pat003Edges, node_count: pat003Nodes.length, edge_count: pat003Edges.length },
  "pat-004": { patient_id: "pat-004", nodes: pat004Nodes, edges: pat004Edges, node_count: pat004Nodes.length, edge_count: pat004Edges.length },
  "pat-005": { patient_id: "pat-005", nodes: pat005Nodes, edges: pat005Edges, node_count: pat005Nodes.length, edge_count: pat005Edges.length },
};

// ---------- Global graph (all patients combined) ----------

const allNodes: GraphNode[] = [
  ...pat001Nodes,
  ...pat002Nodes,
  ...pat003Nodes,
  ...pat004Nodes,
  ...pat005Nodes,
];

const allEdges: GraphEdge[] = [
  ...pat001Edges,
  ...pat002Edges,
  ...pat003Edges,
  ...pat004Edges,
  ...pat005Edges,
  // Cross-patient edges for shared concepts
  { id: "edge-global-001", patient_id: null, source_node_id: "node-002", target_node_id: "node-041", edge_type: "interacts_with", properties: { relationship: "T2DM contributes to CKD progression" }, ...edgeBase },
  { id: "edge-global-002", patient_id: null, source_node_id: "node-003", target_node_id: "node-041", edge_type: "interacts_with", properties: { relationship: "HTN contributes to CKD progression" }, ...edgeBase },
];

export const DEMO_GLOBAL_GRAPH: PatientGraph = {
  patient_id: "global",
  nodes: allNodes,
  edges: allEdges,
  node_count: allNodes.length,
  edge_count: allEdges.length,
};
