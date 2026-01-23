"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Plus, Pencil, Trash2, AlertTriangle } from "lucide-react";

interface ChangeEntry {
  type: "added" | "changed" | "deprecated" | "removed" | "fixed";
  description: string;
  endpoints?: string[];
}

interface ChangelogVersion {
  version: string;
  date: string;
  summary: string;
  changes: ChangeEntry[];
}

const changelog: ChangelogVersion[] = [
  {
    version: "1.5.0",
    date: "2026-01-22",
    summary: "Clinical terminology enhancements and cross-reference tools",
    changes: [
      {
        type: "added",
        description: "Concept cross-reference page for vocabulary mapping lookups",
        endpoints: ["POST /api/v1/vocabulary-mapping/map"],
      },
      {
        type: "added",
        description: "Terminology statistics dashboard aggregating all clinical service metrics",
        endpoints: [
          "GET /api/v1/icd10-suggestions/stats",
          "GET /api/v1/cpt-suggestions/stats",
          "GET /api/v1/drug-safety/stats",
          "GET /api/v1/hcc-analysis/stats",
          "GET /api/v1/differential-diagnosis/stats",
        ],
      },
      {
        type: "changed",
        description: "Added OpenAPI tags for all clinical services improving API documentation",
      },
      {
        type: "changed",
        description: "Added request/response examples to all clinical API schemas",
        endpoints: [
          "POST /api/v1/icd10-suggestions/suggest",
          "POST /api/v1/hcc-analysis/analyze",
          "POST /api/v1/drug-safety/check",
          "POST /api/v1/differential-diagnosis/generate",
        ],
      },
    ],
  },
  {
    version: "1.4.0",
    date: "2026-01-21",
    summary: "Pagination, code browsers, and HCC analysis interface",
    changes: [
      {
        type: "added",
        description: "ICD-10 code browser with search and pagination",
        endpoints: ["GET /api/v1/icd10-suggestions/search"],
      },
      {
        type: "added",
        description: "CPT code browser with RVU display and category filtering",
        endpoints: ["GET /api/v1/cpt-suggestions/search"],
      },
      {
        type: "added",
        description: "HCC gap analysis interface with RAF score visualization",
        endpoints: ["POST /api/v1/hcc-analysis/analyze"],
      },
      {
        type: "changed",
        description: "Added offset-based pagination (offset, limit, has_more) to search endpoints",
        endpoints: [
          "GET /api/v1/icd10-suggestions/search",
          "GET /api/v1/cpt-suggestions/search",
          "GET /api/v1/drug-safety/search",
        ],
      },
    ],
  },
  {
    version: "1.3.0",
    date: "2026-01-20",
    summary: "Drug interactions, CPT bundling, batch HCC mapping, and input validation",
    changes: [
      {
        type: "added",
        description: "Drug-drug interaction checking with 15 known interaction pairs",
        endpoints: ["POST /api/v1/drug-safety/interactions"],
      },
      {
        type: "added",
        description: "CPT code bundling/unbundling check with 8 bundling rules",
        endpoints: ["POST /api/v1/cpt-suggestions/bundling-check"],
      },
      {
        type: "added",
        description: "Batch ICD-10 to HCC mapping (up to 500 codes per request)",
        endpoints: ["POST /api/v1/hcc-analysis/mapping/batch"],
      },
      {
        type: "changed",
        description: "Standardized error responses across all clinical endpoints using ErrorResponse model with error_code, message, details, request_id, timestamp, path",
      },
      {
        type: "changed",
        description: "Added domain-specific input validation: ICD-10 format regex, confidence levels, E/M settings, gender values",
      },
    ],
  },
  {
    version: "1.2.0",
    date: "2026-01-18",
    summary: "Multi-hop reasoning and ontology-enhanced Graph RAG",
    changes: [
      {
        type: "added",
        description: "Multi-hop reasoning queries across knowledge graph with explanation chains",
        endpoints: ["POST /api/v1/graph-rag/multi-hop"],
      },
      {
        type: "added",
        description: "Ontology-enhanced Graph RAG with semantic enrichment",
        endpoints: ["POST /api/v1/graph-rag/ontology-enhanced"],
      },
      {
        type: "added",
        description: "Vector similarity search across embedded concepts",
        endpoints: ["POST /api/v1/semantic-search/vector"],
      },
      {
        type: "added",
        description: "Query result caching with configurable TTL",
      },
    ],
  },
  {
    version: "1.1.0",
    date: "2026-01-16",
    summary: "Clinical decision support and drug safety APIs",
    changes: [
      {
        type: "added",
        description: "Differential diagnosis generation with CER citations",
        endpoints: ["POST /api/v1/differential-diagnosis/generate"],
      },
      {
        type: "added",
        description: "Drug safety checking with contraindications, black box warnings, dosing guidelines",
        endpoints: [
          "POST /api/v1/drug-safety/check",
          "GET /api/v1/drug-safety/profile/{drug_name}",
        ],
      },
      {
        type: "added",
        description: "ICD-10 code suggestion from clinical text with confidence scoring",
        endpoints: ["POST /api/v1/icd10-suggestions/suggest"],
      },
      {
        type: "added",
        description: "CPT code suggestion for E/M encounters",
        endpoints: ["POST /api/v1/cpt-suggestions/suggest"],
      },
      {
        type: "added",
        description: "HCC gap analysis with RAF score calculation and revenue impact",
        endpoints: ["POST /api/v1/hcc-analysis/analyze"],
      },
    ],
  },
  {
    version: "1.0.0",
    date: "2026-01-14",
    summary: "Initial release with FHIR terminology services and vocabulary mapping",
    changes: [
      {
        type: "added",
        description: "FHIR Terminology Services: $lookup, $validate-code, $translate, $subsumes, $expand, $closure",
        endpoints: [
          "GET /api/v1/fhir/CodeSystem/$lookup",
          "GET /api/v1/fhir/CodeSystem/$validate-code",
          "GET /api/v1/fhir/ConceptMap/$translate",
        ],
      },
      {
        type: "added",
        description: "Vocabulary mapping API for cross-vocabulary translation (ICD-10, CPT, NDC to OMOP)",
        endpoints: [
          "POST /api/v1/vocabulary-mapping/map",
          "POST /api/v1/vocabulary-mapping/batch",
        ],
      },
      {
        type: "added",
        description: "NLP pipeline for clinical text entity extraction",
        endpoints: ["POST /api/v1/nlp/extract"],
      },
      {
        type: "added",
        description: "Knowledge graph operations and concept search",
        endpoints: [
          "GET /api/v1/search/concepts",
          "GET /api/v1/graph/concept/{id}",
        ],
      },
      {
        type: "added",
        description: "Audit logging with export in JSON, CSV, and HIPAA-compliant formats",
        endpoints: [
          "POST /api/v1/audit/export",
          "GET /api/v1/audit/export/{export_id}",
          "GET /api/v1/audit/export/{export_id}/download",
        ],
      },
    ],
  },
];

const typeConfig = {
  added: { label: "Added", icon: Plus, color: "bg-green-600 text-white" },
  changed: { label: "Changed", icon: Pencil, color: "bg-blue-600 text-white" },
  deprecated: { label: "Deprecated", icon: AlertTriangle, color: "bg-amber-600 text-white" },
  removed: { label: "Removed", icon: Trash2, color: "bg-red-600 text-white" },
  fixed: { label: "Fixed", icon: Pencil, color: "bg-purple-600 text-white" },
};

export default function APIChangelogPage() {
  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <div className="flex items-center gap-4 mb-6">
        <Link href="/settings">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-1" /> Settings
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">API Changelog</h1>
          <p className="text-muted-foreground">
            Version history and changes for the Clinical Ontology Normalizer API
          </p>
        </div>
      </div>

      <div className="space-y-6">
        {changelog.map((version) => (
          <Card key={version.version}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xl">
                  v{version.version}
                </CardTitle>
                <Badge variant="outline" className="text-sm">
                  {version.date}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">{version.summary}</p>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {version.changes.map((change, idx) => {
                  const config = typeConfig[change.type];
                  return (
                    <div key={idx} className="flex gap-3">
                      <Badge className={`${config.color} text-xs h-5 mt-0.5`}>
                        {config.label}
                      </Badge>
                      <div className="flex-1">
                        <p className="text-sm">{change.description}</p>
                        {change.endpoints && change.endpoints.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {change.endpoints.map((ep) => (
                              <code
                                key={ep}
                                className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono"
                              >
                                {ep}
                              </code>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
