/**
 * Shared types and scenario configurations for the P4-018 production demo workspace.
 *
 * Each scenario defines deterministic inputs, sequential steps, and the API
 * endpoints exercised. The DemoScenarioRunner component consumes these configs
 * to execute steps, track endpoint hits, and export evidence manifests.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ScenarioStep {
  /** Short label shown in the step timeline */
  label: string;
  /** API endpoint this step exercises (may be null for client-side checks) */
  endpoint: string | null;
  /** What the step verifies */
  verification: string;
}

export interface DemoScenarioConfig {
  /** Unique scenario identifier */
  id: string;
  /** Human-readable title */
  title: string;
  /** Which page hosts this scenario */
  pageHref: string;
  /** Deterministic inputs for this scenario run */
  inputs: Record<string, unknown>;
  /** Ordered list of steps to execute */
  steps: ScenarioStep[];
  /** All API endpoints this scenario touches */
  endpoints: string[];
}

export interface StepResult {
  stepIndex: number;
  label: string;
  endpoint: string | null;
  status: "pass" | "simulated" | "fail";
  /** ISO timestamp when the step completed */
  completedAt: string;
  /** Milliseconds elapsed for this step */
  durationMs: number;
  detail: string;
}

export interface EvidenceManifest {
  scenarioId: string;
  scenarioTitle: string;
  inputHash: string;
  inputs: Record<string, unknown>;
  stepResults: StepResult[];
  endpointsHit: string[];
  endpointsSimulated: string[];
  operator: string;
  startedAt: string;
  completedAt: string;
  mode: "live" | "simulation" | "mixed";
  exportedAt: string;
}

// ---------------------------------------------------------------------------
// Utility: deterministic hash of scenario inputs
// ---------------------------------------------------------------------------

export function computeInputHash(inputs: Record<string, unknown>): string {
  const json = JSON.stringify(inputs, Object.keys(inputs).sort());
  let hash = 0;
  for (let i = 0; i < json.length; i++) {
    const ch = json.charCodeAt(i);
    hash = ((hash << 5) - hash + ch) | 0;
  }
  return "hash-" + Math.abs(hash).toString(16).padStart(8, "0");
}

// ---------------------------------------------------------------------------
// Scenario 1: Clinical Safety + Provenance
// ---------------------------------------------------------------------------

export const SCENARIO_CLINICAL_SAFETY: DemoScenarioConfig = {
  id: "p4-018-clinical-safety",
  title: "Clinical Safety + Provenance",
  pageHref: "/clinical/intelligence",
  inputs: {
    patientId: "TEST12345",
    question: "Is the patient at risk for medication interactions?",
  },
  steps: [
    {
      label: "Load demo knowledge graph",
      endpoint: "/api/clinical-agent/import",
      verification: "Import endpoint responds or simulation fallback loads mock graph",
    },
    {
      label: "Verify graph structure (17 nodes / 21 edges)",
      endpoint: "/api/clinical-agent/graph/TEST12345",
      verification: "Graph response contains expected node/edge counts",
    },
    {
      label: "Query clinical agent for medication interactions",
      endpoint: "/api/clinical-agent/query/TEST12345",
      verification: "Response includes confidence score and entity list",
    },
    {
      label: "Verify confidence + entities in response",
      endpoint: null,
      verification: "Confidence >= 0.85 and at least 2 entities returned",
    },
    {
      label: "Check simulation guard blocks write actions",
      endpoint: null,
      verification: "useSimulationGuard returns isSimulation=true in demo mode",
    },
    {
      label: "Verify DataSourceModeBanner renders correct mode",
      endpoint: null,
      verification: "Banner shows 'simulation' or 'mixed' mode with escalation text",
    },
  ],
  endpoints: [
    "/api/clinical-agent/import",
    "/api/clinical-agent/graph/TEST12345",
    "/api/clinical-agent/query/TEST12345",
  ],
};

// ---------------------------------------------------------------------------
// Scenario 2: Interop + OpenEHR Dry-Run
// ---------------------------------------------------------------------------

export const SCENARIO_INTEROP_OPENEHR: DemoScenarioConfig = {
  id: "p4-018-interop-openehr",
  title: "Interop + OpenEHR Dry-Run",
  pageHref: "/pipelines/openehr/operations",
  inputs: {
    patientId: "patient-demo-001",
    composition: "<DEMO_COMPOSITION>",
  },
  steps: [
    {
      label: "Load OpenEHR demo composition",
      endpoint: "/api/v1/openehr/dry-run",
      verification: "Dry-run endpoint responds or simulation fallback produces result",
    },
    {
      label: "Execute dry-run import",
      endpoint: "/api/v1/openehr/dry-run",
      verification: "Result shows success=true with parsed domain counts",
    },
    {
      label: "Verify extracted counts (conditions + medications > 0)",
      endpoint: null,
      verification: "Dry-run result contains conditions >= 1 and medications >= 1",
    },
    {
      label: "Run round-trip reconciliation",
      endpoint: "/api/v1/openehr/reconcile/patient-demo-001",
      verification: "Reconciliation returns match=true with matching fingerprints",
    },
    {
      label: "Verify fingerprint parity",
      endpoint: null,
      verification: "import_fingerprint === export_reimport_fingerprint",
    },
    {
      label: "Check rollback guard blocks destructive action in simulation",
      endpoint: "/api/v1/openehr/rollback",
      verification: "Rollback endpoint is listed but blocked by simulation guard",
    },
  ],
  endpoints: [
    "/api/v1/openehr/dry-run",
    "/api/v1/openehr/reconcile/patient-demo-001",
    "/api/v1/openehr/rollback",
  ],
};

// ---------------------------------------------------------------------------
// Scenario 3: Quality / Ops Dashboard
// ---------------------------------------------------------------------------

export const SCENARIO_QUALITY_OPS: DemoScenarioConfig = {
  id: "p4-018-quality-ops",
  title: "Quality / Ops Dashboard",
  pageHref: "/clinical",
  inputs: {
    dashboardEndpoints: ["/api/dashboard/provider", "/api/dashboard/biller"],
  },
  steps: [
    {
      label: "Fetch provider dashboard",
      endpoint: "/api/dashboard/provider",
      verification: "Provider dashboard responds with drug alerts and action items",
    },
    {
      label: "Fetch biller dashboard",
      endpoint: "/api/dashboard/biller",
      verification: "Biller dashboard responds with HCC opportunities and CDI queries",
    },
    {
      label: "Verify drug alerts panel populated",
      endpoint: null,
      verification: "At least one drug alert rendered or empty-state shown",
    },
    {
      label: "Verify HCC panel populated",
      endpoint: null,
      verification: "HCC opportunities table renders with revenue column",
    },
    {
      label: "Verify quality gaps panel",
      endpoint: "/api/v1/kg/completeness/score",
      verification: "Quality gaps or completeness score visible in dashboard",
    },
    {
      label: "Check simulation guard in error state",
      endpoint: null,
      verification: "When API unavailable, guard shows escalation text and blocks actions",
    },
  ],
  endpoints: [
    "/api/dashboard/provider",
    "/api/dashboard/biller",
    "/api/v1/kg/completeness/score",
  ],
};

// ---------------------------------------------------------------------------
// All scenarios (for iteration and cross-referencing)
// ---------------------------------------------------------------------------

export const DEMO_SCENARIOS: DemoScenarioConfig[] = [
  SCENARIO_CLINICAL_SAFETY,
  SCENARIO_INTEROP_OPENEHR,
  SCENARIO_QUALITY_OPS,
];
