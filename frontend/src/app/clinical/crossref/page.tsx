"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  ArrowLeft,
  Search,
  ArrowRight,
  Loader2,
  Network,
} from "lucide-react";

interface MappingResult {
  source_code: string;
  source_vocabulary: string;
  source_concept_id: number | null;
  source_concept_name: string | null;
  target_concept_id: number | null;
  target_concept_name: string | null;
  target_vocabulary: string | null;
  mapping_type: string;
  confidence: string;
  confidence_score: number;
  relationship_id: string | null;
  is_mapped: boolean;
  unmapped_reason: string | null;
}

interface HCCMapping {
  icd10_code: string;
  hcc_code: string | null;
}

const SOURCE_VOCABULARIES = [
  { value: "ICD10CM", label: "ICD-10-CM" },
  { value: "ICD10PCS", label: "ICD-10-PCS" },
  { value: "CPT4", label: "CPT-4" },
  { value: "NDC", label: "NDC" },
  { value: "LOINC", label: "LOINC" },
];

const TARGET_VOCABULARIES = ["SNOMED", "RxNorm", "LOINC"];

export default function ConceptCrossReferencePage() {
  const [code, setCode] = useState("");
  const [sourceVocab, setSourceVocab] = useState("ICD10CM");
  const [mappings, setMappings] = useState<MappingResult[]>([]);
  const [hccMapping, setHccMapping] = useState<HCCMapping | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const lookupMappings = async () => {
    if (!code.trim()) return;
    setLoading(true);
    setError(null);
    setMappings([]);
    setHccMapping(null);
    setSearched(true);

    try {
      // Fetch mappings to each target vocabulary
      const results: MappingResult[] = [];
      for (const target of TARGET_VOCABULARIES) {
        try {
          const res = await fetch("/api/v1/vocabulary-mapping/map", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              code: code.trim().toUpperCase(),
              source_vocabulary: sourceVocab,
              target_vocabulary: target,
            }),
          });
          if (res.ok) {
            const data = await res.json();
            results.push(data);
          }
        } catch {
          // Skip failed targets
        }
      }

      // Also try without target specified (auto-select)
      try {
        const res = await fetch("/api/v1/vocabulary-mapping/map", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            code: code.trim().toUpperCase(),
            source_vocabulary: sourceVocab,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          // Add if not duplicate
          if (!results.find((r) => r.target_vocabulary === data.target_vocabulary)) {
            results.push(data);
          }
        }
      } catch {
        // Skip
      }

      setMappings(results);

      // If ICD-10, also check HCC mapping
      if (sourceVocab === "ICD10CM") {
        try {
          const hccRes = await fetch(
            `/api/v1/hcc-analysis/mapping/${encodeURIComponent(code.trim().toUpperCase())}`
          );
          if (hccRes.ok) {
            const hccData = await hccRes.json();
            setHccMapping(hccData);
          }
        } catch {
          // Skip
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lookup failed");
    } finally {
      setLoading(false);
    }
  };

  const confidenceColor = (confidence: string) => {
    switch (confidence) {
      case "high":
        return "bg-green-600";
      case "medium":
        return "bg-yellow-600";
      case "low":
        return "bg-red-600";
      default:
        return "bg-gray-500";
    }
  };

  return (
    <div className="container mx-auto p-6 max-w-5xl">
      <div className="flex items-center gap-4 mb-6">
        <Link href="/clinical">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-1" /> Clinical
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Concept Cross-Reference</h1>
          <p className="text-muted-foreground">
            Look up codes and view mappings across terminologies
          </p>
        </div>
      </div>

      {/* Search Form */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="flex gap-3">
            <select
              value={sourceVocab}
              onChange={(e) => setSourceVocab(e.target.value)}
              className="border rounded-md px-3 py-2 text-sm bg-background"
            >
              {SOURCE_VOCABULARIES.map((v) => (
                <option key={v.value} value={v.value}>
                  {v.label}
                </option>
              ))}
            </select>
            <Input
              placeholder="Enter code (e.g., E11.9, 99213, J18.9)"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && lookupMappings()}
              className="flex-1"
            />
            <Button onClick={lookupMappings} disabled={loading || !code.trim()}>
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4 mr-1" />
              )}
              Lookup
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="text-red-500 text-sm mb-4">{error}</div>
      )}

      {/* Results */}
      {searched && !loading && (
        <div className="space-y-4">
          {/* Source concept info */}
          {mappings.length > 0 && mappings[0].source_concept_name && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Network className="h-5 w-5" />
                  Source Concept
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4">
                  <Badge variant="outline" className="text-sm">
                    {mappings[0].source_vocabulary}
                  </Badge>
                  <span className="font-mono font-bold">
                    {mappings[0].source_code}
                  </span>
                  <span className="text-muted-foreground">
                    {mappings[0].source_concept_name}
                  </span>
                  {mappings[0].source_concept_id && (
                    <Badge variant="secondary" className="text-xs">
                      OMOP ID: {mappings[0].source_concept_id}
                    </Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Vocabulary mappings */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">Vocabulary Mappings</CardTitle>
            </CardHeader>
            <CardContent>
              {mappings.length === 0 ? (
                <p className="text-muted-foreground text-sm">
                  No mappings found for {code.toUpperCase()} in {sourceVocab}
                </p>
              ) : (
                <div className="space-y-3">
                  {mappings.map((m, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-3 p-3 rounded-lg border"
                    >
                      <Badge variant="outline" className="min-w-[80px] justify-center">
                        {m.source_vocabulary}
                      </Badge>
                      <span className="font-mono text-sm">{m.source_code}</span>
                      <ArrowRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      {m.is_mapped ? (
                        <>
                          <Badge variant="outline" className="min-w-[80px] justify-center">
                            {m.target_vocabulary}
                          </Badge>
                          <span className="font-mono text-sm">
                            {m.target_concept_id}
                          </span>
                          <span className="text-sm text-muted-foreground flex-1 truncate">
                            {m.target_concept_name}
                          </span>
                          <Badge
                            className={`text-xs text-white ${confidenceColor(m.confidence)}`}
                          >
                            {m.confidence}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {(m.confidence_score * 100).toFixed(0)}%
                          </span>
                        </>
                      ) : (
                        <span className="text-sm text-muted-foreground italic">
                          {m.unmapped_reason || "No mapping available"}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* HCC Mapping (ICD-10 only) */}
          {sourceVocab === "ICD10CM" && hccMapping && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">HCC Mapping</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-3 p-3 rounded-lg border">
                  <Badge variant="outline">ICD-10-CM</Badge>
                  <span className="font-mono text-sm">
                    {hccMapping.icd10_code}
                  </span>
                  <ArrowRight className="h-4 w-4 text-muted-foreground" />
                  {hccMapping.hcc_code ? (
                    <>
                      <Badge variant="outline">HCC</Badge>
                      <span className="font-mono font-bold text-sm">
                        {hccMapping.hcc_code}
                      </span>
                      <Badge className="bg-green-600 text-white text-xs">
                        Mapped
                      </Badge>
                    </>
                  ) : (
                    <span className="text-sm text-muted-foreground italic">
                      No HCC mapping for this code
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Mapping metadata */}
          {mappings.length > 0 && mappings.some((m) => m.mapping_type) && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Mapping Details</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  {mappings
                    .filter((m) => m.is_mapped)
                    .map((m, idx) => (
                      <div key={idx} className="space-y-1">
                        <p className="text-xs text-muted-foreground">
                          {m.target_vocabulary}
                        </p>
                        <p className="text-sm font-medium">
                          Type: {m.mapping_type}
                        </p>
                        {m.relationship_id && (
                          <p className="text-xs text-muted-foreground">
                            Relationship: {m.relationship_id}
                          </p>
                        )}
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
