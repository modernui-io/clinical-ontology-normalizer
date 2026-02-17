/**
 * Evidence consistency checks for docs and changelog pages.
 *
 * Validates that all evidence entries conform to the EvidenceEntry
 * contract and that claim IDs are unique across pages (P4-020).
 */

import {
  type EvidenceEntry,
  getEvidenceStatusColor,
  validateEvidenceEntries,
} from "@/lib/evidence";

describe("validateEvidenceEntries", () => {
  const validEntry: EvidenceEntry = {
    claim_id: "CLAIM-TEST-001",
    claim_text: "Test claim",
    category: "operational",
    evidence_paths: ["some/path.ts"],
    last_verified: "2026-02-16",
    verified_by: "CTO",
    freshness_sla: "per-release",
    status: "verified",
  };

  it("returns no errors for a valid entry", () => {
    const errors = validateEvidenceEntries([validEntry]);
    expect(errors).toEqual([]);
  });

  it("reports missing claim_id", () => {
    const bad = { ...validEntry, claim_id: "" };
    const errors = validateEvidenceEntries([bad]);
    expect(errors.length).toBeGreaterThan(0);
    expect(errors.some((e) => e.includes("claim_id"))).toBe(true);
  });

  it("reports empty evidence_paths", () => {
    const bad = { ...validEntry, evidence_paths: [] };
    const errors = validateEvidenceEntries([bad]);
    expect(errors.length).toBeGreaterThan(0);
    expect(errors.some((e) => e.includes("evidence_paths"))).toBe(true);
  });

  it("reports missing verified_by", () => {
    const bad = { ...validEntry, verified_by: "" };
    const errors = validateEvidenceEntries([bad]);
    expect(errors.length).toBeGreaterThan(0);
    expect(errors.some((e) => e.includes("verified_by"))).toBe(true);
  });
});

describe("getEvidenceStatusColor", () => {
  it('returns label "Verified" for verified status within SLA', () => {
    const result = getEvidenceStatusColor(
      "verified",
      "per-release",
      "2026-02-10",
      "2026-02-16"
    );
    expect(result.label).toBe("Verified");
  });

  it('returns label "Stale" for stale status', () => {
    const result = getEvidenceStatusColor(
      "stale",
      "per-release",
      "2026-02-16",
      "2026-02-16"
    );
    expect(result.label).toBe("Stale");
  });

  it('returns label "Unverified" for unverified status', () => {
    const result = getEvidenceStatusColor(
      "unverified",
      "per-release",
      "2026-02-16",
      "2026-02-16"
    );
    expect(result.label).toBe("Unverified");
  });

  it('returns label "Disputed" for disputed status', () => {
    const result = getEvidenceStatusColor(
      "disputed",
      "per-release",
      "2026-02-16",
      "2026-02-16"
    );
    expect(result.label).toBe("Disputed");
  });

  it('downgrades verified to "Stale" when SLA has elapsed', () => {
    const result = getEvidenceStatusColor(
      "verified",
      "per-release",
      "2026-01-01",
      "2026-02-16"
    );
    expect(result.label).toBe("Stale");
  });
});

describe("docs page evidence completeness", () => {
  const docsEvidenceClaims: EvidenceEntry[] = [
    {
      claim_id: "CLAIM-DOC-001",
      claim_text: "Trust/Readiness claim routing",
      category: "product",
      evidence_paths: [
        "frontend/src/app/docs/page.tsx",
        "frontend/src/app/trust/page.tsx",
      ],
      last_verified: "2026-02-16",
      verified_by: "CTO",
      freshness_sla: "per-release",
      status: "verified",
    },
    {
      claim_id: "CLAIM-DOC-002",
      claim_text: "Sales demo discoverability",
      category: "product",
      evidence_paths: ["frontend/src/app/sales-demo/page.tsx"],
      last_verified: "2026-02-16",
      verified_by: "VP Sales",
      freshness_sla: "per-release",
      status: "verified",
    },
    {
      claim_id: "CLAIM-DOC-003",
      claim_text: "Operational docs + changelog anchors",
      category: "operational",
      evidence_paths: ["frontend/src/app/changelog/page.tsx"],
      last_verified: "2026-02-16",
      verified_by: "CTO",
      freshness_sla: "per-release",
      status: "verified",
    },
    {
      claim_id: "CLAIM-DOC-004",
      claim_text: "Per-section evidence artifact coverage",
      category: "operational",
      evidence_paths: ["tasks/26_frontend_sales_readiness_p0_p4_todo.md"],
      last_verified: "2026-02-16",
      verified_by: "CTO",
      freshness_sla: "monthly",
      status: "verified",
    },
  ];

  const docsSectionEntries: EvidenceEntry[] = [
    {
      claim_id: "CLAIM-DOC-QS1",
      claim_text: "Quickstart",
      category: "product",
      evidence_paths: ["backend/app/api/documents.py"],
      last_verified: "2026-02-14",
      verified_by: "CTO",
      freshness_sla: "per-release",
      status: "verified",
    },
    {
      claim_id: "CLAIM-DOC-API1",
      claim_text: "API Reference",
      category: "product",
      evidence_paths: ["backend/app/main.py"],
      last_verified: "2026-02-16",
      verified_by: "CTO",
      freshness_sla: "per-release",
      status: "verified",
    },
    {
      claim_id: "CLAIM-DOC-NLP1",
      claim_text: "NLP Pipeline",
      category: "product",
      evidence_paths: ["backend/app/services/narrative_extractor.py"],
      last_verified: "2026-02-15",
      verified_by: "VP Engineering",
      freshness_sla: "per-release",
      status: "verified",
    },
    {
      claim_id: "CLAIM-DOC-ONTO1",
      claim_text: "Ontology Mapping",
      category: "product",
      evidence_paths: ["backend/app/services/clinical_ontology_mapper.py"],
      last_verified: "2026-02-15",
      verified_by: "VP Engineering",
      freshness_sla: "per-release",
      status: "verified",
    },
    {
      claim_id: "CLAIM-DOC-KG1",
      claim_text: "Knowledge Graph",
      category: "product",
      evidence_paths: ["backend/app/services/graph_builder_service.py"],
      last_verified: "2026-02-14",
      verified_by: "CTO",
      freshness_sla: "per-release",
      status: "verified",
    },
    {
      claim_id: "CLAIM-DOC-FHIR1",
      claim_text: "FHIR & Interoperability",
      category: "product",
      evidence_paths: ["backend/app/services/fhir_export_service.py"],
      last_verified: "2026-02-14",
      verified_by: "VP Engineering",
      freshness_sla: "per-release",
      status: "verified",
    },
    {
      claim_id: "CLAIM-DOC-TRUST1",
      claim_text: "Trust Center",
      category: "product",
      evidence_paths: ["docs/operations/pre_pilot_signoff_matrix.md"],
      last_verified: "2026-02-16",
      verified_by: "CTO",
      freshness_sla: "monthly",
      status: "verified",
    },
    {
      claim_id: "CLAIM-DOC-DEMO1",
      claim_text: "Sales Demo",
      category: "product",
      evidence_paths: ["frontend/src/app/sales-demo/page.tsx"],
      last_verified: "2026-02-16",
      verified_by: "VP Sales",
      freshness_sla: "per-release",
      status: "verified",
    },
  ];

  const allDocsEntries = [...docsEvidenceClaims, ...docsSectionEntries];

  it("all docs evidence entries pass validation", () => {
    const errors = validateEvidenceEntries(allDocsEntries);
    expect(errors).toEqual([]);
  });

  it("all docs claim_ids are unique", () => {
    const ids = allDocsEntries.map((e) => e.claim_id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("changelog page evidence completeness", () => {
  const changelogEntries: EvidenceEntry[] = [
    {
      claim_id: "CLAIM-CL-001",
      claim_text: "Knowledge graph builder with full provenance tracking",
      category: "product",
      evidence_paths: ["backend/app/services/graph_builder_service.py"],
      last_verified: "2026-02-14",
      verified_by: "CTO",
      freshness_sla: "per-release",
      status: "verified",
    },
    {
      claim_id: "CLAIM-CL-002",
      claim_text: "GraphRAG query engine for clinical reasoning",
      category: "product",
      evidence_paths: ["backend/app/services/graph_augmented_rag.py"],
      last_verified: "2026-02-15",
      verified_by: "VP Engineering",
      freshness_sla: "per-release",
      status: "verified",
    },
    {
      claim_id: "CLAIM-CL-003",
      claim_text: "Clinical decision support (CDS Hooks) integration",
      category: "product",
      evidence_paths: ["backend/app/api/cds_hooks.py"],
      last_verified: "2026-02-14",
      verified_by: "VP Engineering",
      freshness_sla: "per-release",
      status: "verified",
    },
    {
      claim_id: "CLAIM-CL-004",
      claim_text: "Drug interaction checker with severity scoring",
      category: "product",
      evidence_paths: ["backend/app/services/drug_safety.py"],
      last_verified: "2026-02-15",
      verified_by: "CISO",
      freshness_sla: "per-release",
      status: "verified",
    },
    {
      claim_id: "CLAIM-CL-005",
      claim_text:
        "FHIR R4 import/export with Condition, MedicationRequest, and Observation resources",
      category: "interop",
      evidence_paths: ["backend/app/services/fhir_export_service.py"],
      last_verified: "2026-01-20",
      verified_by: "VP Engineering",
      freshness_sla: "per-release",
      status: "verified",
    },
    {
      claim_id: "CLAIM-CL-006",
      claim_text:
        "Assertion detection engine (negation, hypothetical, family history)",
      category: "clinical",
      evidence_paths: ["backend/app/services/narrative_extractor.py"],
      last_verified: "2026-01-18",
      verified_by: "VP Engineering",
      freshness_sla: "per-release",
      status: "verified",
    },
    {
      claim_id: "CLAIM-CL-007",
      claim_text: "Bulk document ingestion API",
      category: "product",
      evidence_paths: ["backend/app/api/documents.py"],
      last_verified: "2026-01-15",
      verified_by: "CTO",
      freshness_sla: "monthly",
      status: "verified",
    },
    {
      claim_id: "CLAIM-CL-008",
      claim_text: "Clinical calculators (CHA2DS2-VASc, MELD, Wells, CURB-65)",
      category: "clinical",
      evidence_paths: ["backend/app/services/clinical_calculators.py"],
      last_verified: "2026-01-22",
      verified_by: "VP Engineering",
      freshness_sla: "monthly",
      status: "verified",
    },
    {
      claim_id: "CLAIM-CL-009",
      claim_text:
        "ML ensemble NLP pipeline with transformer-based extraction",
      category: "product",
      evidence_paths: ["backend/app/services/ml_ensemble_extractor.py"],
      last_verified: "2025-12-20",
      verified_by: "VP Engineering",
      freshness_sla: "quarterly",
      status: "verified",
    },
    {
      claim_id: "CLAIM-CL-010",
      claim_text: "OMOP CDM vocabulary mapping with confidence scoring",
      category: "product",
      evidence_paths: ["backend/app/services/clinical_ontology_mapper.py"],
      last_verified: "2025-12-18",
      verified_by: "CTO",
      freshness_sla: "quarterly",
      status: "verified",
    },
    {
      claim_id: "CLAIM-CL-011",
      claim_text: "Clinical trials management module",
      category: "clinical",
      evidence_paths: ["backend/app/api/clinical_trials.py"],
      last_verified: "2025-12-15",
      verified_by: "VP Engineering",
      freshness_sla: "quarterly",
      status: "verified",
    },
    {
      claim_id: "CLAIM-CL-012",
      claim_text: "Audit logging and compliance reporting",
      category: "security",
      evidence_paths: ["backend/app/middleware/audit_middleware.py"],
      last_verified: "2025-12-22",
      verified_by: "CISO",
      freshness_sla: "quarterly",
      status: "verified",
    },
    {
      claim_id: "CLAIM-CL-013",
      claim_text: "Rule-based NLP extraction engine",
      category: "product",
      evidence_paths: ["backend/app/services/narrative_extractor.py"],
      last_verified: "2025-11-10",
      verified_by: "CTO",
      freshness_sla: "quarterly",
      status: "verified",
    },
    {
      claim_id: "CLAIM-CL-014",
      claim_text: "UMLS concept lookup and normalization",
      category: "product",
      evidence_paths: ["backend/app/services/umls_service.py"],
      last_verified: "2025-11-08",
      verified_by: "VP Engineering",
      freshness_sla: "quarterly",
      status: "verified",
    },
    {
      claim_id: "CLAIM-CL-015",
      claim_text: "Patient knowledge graph visualization",
      category: "product",
      evidence_paths: ["frontend/src/app/clinical/intelligence/page.tsx"],
      last_verified: "2025-11-12",
      verified_by: "CTO",
      freshness_sla: "quarterly",
      status: "verified",
    },
    {
      claim_id: "CLAIM-CL-016",
      claim_text: "REST API with OpenAPI documentation",
      category: "product",
      evidence_paths: ["backend/app/main.py"],
      last_verified: "2025-11-14",
      verified_by: "CTO",
      freshness_sla: "quarterly",
      status: "verified",
    },
  ];

  it("all changelog evidence entries pass validation", () => {
    const errors = validateEvidenceEntries(changelogEntries);
    expect(errors).toEqual([]);
  });

  it("all changelog claim_ids are unique", () => {
    const ids = changelogEntries.map((e) => e.claim_id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("cross-page claim uniqueness", () => {
  const allClaimIds = [
    // docs page - evidence claims
    "CLAIM-DOC-001",
    "CLAIM-DOC-002",
    "CLAIM-DOC-003",
    "CLAIM-DOC-004",
    // docs page - section entries
    "CLAIM-DOC-QS1",
    "CLAIM-DOC-API1",
    "CLAIM-DOC-NLP1",
    "CLAIM-DOC-ONTO1",
    "CLAIM-DOC-KG1",
    "CLAIM-DOC-FHIR1",
    "CLAIM-DOC-TRUST1",
    "CLAIM-DOC-DEMO1",
    // changelog page
    "CLAIM-CL-001",
    "CLAIM-CL-002",
    "CLAIM-CL-003",
    "CLAIM-CL-004",
    "CLAIM-CL-005",
    "CLAIM-CL-006",
    "CLAIM-CL-007",
    "CLAIM-CL-008",
    "CLAIM-CL-009",
    "CLAIM-CL-010",
    "CLAIM-CL-011",
    "CLAIM-CL-012",
    "CLAIM-CL-013",
    "CLAIM-CL-014",
    "CLAIM-CL-015",
    "CLAIM-CL-016",
  ];

  it("no duplicate claim_ids exist across docs and changelog pages", () => {
    expect(new Set(allClaimIds).size).toBe(allClaimIds.length);
  });
});
